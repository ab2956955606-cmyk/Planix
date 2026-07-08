from __future__ import annotations

import json
import re
from collections.abc import Iterator
from datetime import UTC, date as date_type, datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

from fastapi import HTTPException

from ..db import get_conn
from ..schemas import (
    AgentRunRequest,
    CommandApproveRequest,
    CommandChatRequest,
    CommandDraftOut,
    CommandMessageOut,
    CommandPermission,
    CommandThreadSummaryOut,
    PlanCreate,
    PlanRefinedTaskUpdate,
    PlanUpdate,
    RefinedTask,
    RefineTaskRequest,
)
from .llm import LlmClient
from .permission_gate import command_action_requires_approval
from .plans import create_plan, delete_plan, save_plan_refined_task, update_plan
from .planning import PlanningService, build_refine_plan_context
from .rag import RagService
from .runtime import RuntimeOrchestrator

CommandIntent = Literal[
    "normal_chat",
    "planning_request",
    "regenerate_draft",
    "modify_current_draft",
    "show_current_plan",
    "sync_to_calendar",
    "refine_current_plan",
    "query_plan",
    "patch_calendar_plan",
    "navigate_ui",
    "unsupported_command",
]

KEY_RUNTIME_TOOLS = {
    "get_memory",
    "get_today_plans",
    "search_materials",
    "enrich_with_model_knowledge",
    "propose_tasks",
}

CALENDAR_WRITE_ERROR_MESSAGE = "写入日历失败，请检查后端服务或计划数据。"
DRAFT_SAVE_ERROR_MESSAGE = "计划草稿保存失败，请重启后端或检查数据库迁移。"
COMMAND_STREAM_ERROR_MESSAGE = "Command 执行流中断，请重启后端服务后重试。"


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _today() -> str:
    return datetime.now().date().isoformat()


def _ndjson(event: dict[str, Any]) -> str:
    return f"{json.dumps(event, ensure_ascii=False, separators=(',', ':'))}\n"


def _json_object(text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(text or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _row_to_message(row) -> CommandMessageOut:
    return CommandMessageOut(
        id=row["id"],
        threadId=row["thread_id"],
        role=row["role"],
        content=row["content"],
        kind=row["kind"] if "kind" in row.keys() else "text",
        payload=_json_object(row["payload_json"] if "payload_json" in row.keys() else "{}"),
        createdAt=row["created_at"],
    )


def _row_to_draft(row) -> CommandDraftOut | None:
    if not row:
        return None
    return CommandDraftOut(
        id=row["id"],
        threadId=row["thread_id"],
        kind=row["kind"],
        version=int(row["version"] or 1),
        status=row["status"],
        title=row["title"],
        summary=row["summary"],
        payload=_json_object(row["payload_json"]),
        sourceRunId=row["source_run_id"],
        createdAt=row["created_at"],
        updatedAt=row["updated_at"],
    )


def _looks_english(text: str) -> bool:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return False
    ascii_letters = [char for char in letters if ord(char) < 128]
    return len(ascii_letters) / max(1, len(letters)) > 0.8


def detect_command_intent(message: str) -> CommandIntent:
    text = message.strip().lower()
    if not text:
        return "normal_chat"

    if re.search(r"(确认写入|confirm write|confirm .{0,16}write)", text):
        return "sync_to_calendar"
    if re.search(
        r"(写进|写入|加入|同步|保存).{0,12}(日历|日程|calendar|schedule)",
        text,
    ) or re.search(
        r"write .{0,24}calendar|sync .{0,24}calendar|save .{0,24}(calendar|schedule)|confirm .{0,16}write",
        text,
    ):
        return "sync_to_calendar"
    if re.search(
        r"(写进|写入|同步|保存).{0,12}(计划|规划|草稿|plan|draft)",
        text,
    ) or re.search(
        r"(计划|规划|草稿|this plan|current plan|draft).{0,12}(写进|写入|同步|保存|write|sync|save)",
        text,
    ) or re.search(
        r"(write|sync|save) .{0,16}(this|current|the) .{0,8}(plan|draft)",
        text,
    ):
        return "sync_to_calendar"
    if re.search(r"(细化|細化|拆细|一键细化|refine|refinement).{0,16}(任务|计划|全部|all|task|plan)?", text):
        return "refine_current_plan"
    if re.search(r"(重新生成|再生成|换个版本|另一个版本|更轻松|更激进|regenerate|another version)", text):
        return "regenerate_draft"
    if re.search(r"(展开|完整计划|查看计划|计划详情|show.*plan|full.*plan|detail)", text):
        return "show_current_plan"
    if _looks_like_query(text):
        return "query_plan"
    if _looks_like_calendar_patch(text):
        return "patch_calendar_plan"
    if re.search(r"(减少|增加|修改|调整|压缩|保留|删除|改成|revise|modify|adjust|reduce|compress)", text):
        return "modify_current_draft"
    if re.search(
        r"(规划|计划|安排|制定|拆解|帮我学|我要学|准备|路线|日程|\bplan\b|\bplanning\b|\bschedule\b|\broadmap\b|break down)",
        text,
    ):
        return "planning_request"
    if re.search(r"(打开|跳转|进入|去到|navigate|open|go to)", text):
        return "navigate_ui"
    if re.search(r"(执行|删除|清空|设置|保存|execute|delete|clear|save|setting)", text):
        return "unsupported_command"
    return "normal_chat"


def _looks_like_current_draft_write(message: str) -> bool:
    text = message.strip().lower()
    if not text:
        return False
    if re.fullmatch(
        r"(写入|写进|保存|同步|确认|确认写入|执行写入|写入计划|保存计划|同步计划|write|save|sync|confirm|apply)",
        text,
    ):
        return True
    if re.search(
        r"(写入|写进|保存|同步|确认|执行写入).{0,10}(计划|规划|草稿|当前|这个|这份|刚才|上面|它|plan|draft)",
        text,
    ):
        return True
    return bool(
        re.search(
            r"(计划|规划|草稿|当前|这个|这份|刚才|上面|它|this plan|current plan|draft).{0,10}(写入|写进|保存|同步|确认|执行写入|write|save|sync|confirm|apply)",
            text,
        )
    )


def resolve_command_intent(
    message: str,
    intent: CommandIntent | None = None,
    *,
    has_current_draft: bool = False,
) -> CommandIntent:
    resolved = intent or detect_command_intent(message)
    if has_current_draft and resolved in {"normal_chat", "planning_request", "unsupported_command"}:
        if _looks_like_current_draft_write(message):
            return "sync_to_calendar"
    return resolved


def _intent_reply(intent: CommandIntent, message: str) -> str:
    english = _looks_english(message)
    if english:
        replies = {
            "regenerate_draft": "I recognize this as a regeneration request. Phase 4.4 now uses the current hidden draft to regenerate a new version when a draft exists.",
            "modify_current_draft": "I recognize this as a draft modification request. If a current draft exists, Planix will regenerate it with your new instruction.",
            "show_current_plan": "I recognize this as a request to show the current plan. If a draft exists, I can expand it inline in this thread.",
            "sync_to_calendar": "I recognize this as a calendar write instruction. If a current draft exists, I can prepare a Calendar write request and apply the permission rule.",
            "refine_current_plan": "I recognize this as a task refinement request. If a current draft exists, I can refine the selected task or all draft tasks inline.",
            "query_plan": "I recognize this as a plan lookup. I can search calendar plans, materials, notes, and planning history from this thread.",
            "patch_calendar_plan": "I recognize this as a calendar plan change. I will preview the change before applying it.",
            "navigate_ui": "I recognize this as a navigation request. This phase keeps navigation as text only.",
            "unsupported_command": "I recognize this as an operation request, but this phase only supports calendar-plan draft control from P Mode.",
        }
        return replies.get(intent, "")
    replies = {
        "regenerate_draft": "我识别到这是重新生成计划的指令。如果当前线程已有计划草稿，Planix 会基于它生成一个新版本。",
        "modify_current_draft": "我识别到这是修改计划草稿的指令。如果当前线程已有计划草稿，Planix 会结合你的要求重新生成新版本。",
        "show_current_plan": "我识别到这是展开完整计划的指令。如果当前线程已有计划草稿，我会在对话里以内联卡片展示。",
        "sync_to_calendar": "我识别到这是写入日历的指令。如果当前线程已有计划草稿，我会生成日历写入请求并按权限处理。",
        "refine_current_plan": "我识别到这是细化任务的指令。如果当前线程已有计划草稿，我会细化指定任务；没有明确指定时会细化全部任务。",
        "query_plan": "我识别到这是查询计划的指令。我会从日历计划、资料、月笔记和历史规划里查找。",
        "patch_calendar_plan": "我识别到这是修改日历计划的指令。我会先生成修改预览，再按权限确认或执行。",
        "navigate_ui": "我识别到这是页面导航指令。本阶段仍只返回文字说明，不控制界面跳转。",
        "unsupported_command": "我识别到这是操作类指令。本阶段只支持 P Mode 的日历计划草稿控制闭环。",
    }
    return replies.get(intent, "")


def _chat_lock_reply(intent: CommandIntent, message: str) -> str:
    if intent == "normal_chat":
        return ""
    if _looks_english(message):
        return "Chat mode is on, so I will not execute instructions. Turn off chat mode to let Planix handle this as an agent command."
    return "当前是普通聊天模式，我不会执行规划、写入或其它操作。关闭聊天模式后，可以让 Planix 按指令处理。"


def _fallback_reply(message: str) -> str:
    if _looks_english(message):
        return "The model is temporarily unavailable. I can still discuss the request, but I will not execute actions or write data."
    return "模型暂时不可用。我可以先用本地回复继续讨论，但不会执行操作或写入数据。"


def _stream_failure_message(payload: CommandChatRequest, intent: CommandIntent | None = None) -> str:
    intent = intent or detect_command_intent(payload.message)
    if payload.mode == "auto" and intent == "sync_to_calendar":
        return CALENDAR_WRITE_ERROR_MESSAGE
    if payload.mode == "auto" and intent == "refine_current_plan":
        return "任务细化失败，请检查后端服务或计划数据。"
    if payload.mode == "auto" and intent == "show_current_plan":
        return "展开计划失败，请重启后端服务后重试。"
    if payload.mode == "auto" and intent == "query_plan":
        return "查询计划失败，请检查后端服务或本地数据。"
    if payload.mode == "auto" and intent == "patch_calendar_plan":
        return "修改日历计划失败，请检查后端服务或计划数据。"
    if payload.mode == "auto" and intent in {"regenerate_draft", "modify_current_draft"}:
        return "重新生成计划失败，请重启后端服务后重试。"
    if payload.mode == "workbench":
        return DRAFT_SAVE_ERROR_MESSAGE
    return COMMAND_STREAM_ERROR_MESSAGE


def _approval_failure_message(action: Any | None) -> str:
    if action and action["target"] == "calendar":
        return CALENDAR_WRITE_ERROR_MESSAGE
    return COMMAND_STREAM_ERROR_MESSAGE


def _context_date(payload: CommandChatRequest) -> str:
    value = payload.context.get("date") if isinstance(payload.context, dict) else None
    if isinstance(value, str) and re.match(r"^\d{4}-\d{2}-\d{2}$", value):
        return value
    return _today()


WEEKDAY_INDEX = {
    "一": 0,
    "1": 0,
    "二": 1,
    "2": 1,
    "三": 2,
    "3": 2,
    "四": 3,
    "4": 3,
    "五": 4,
    "5": 4,
    "六": 5,
    "6": 5,
    "日": 6,
    "天": 6,
    "7": 6,
}

QUERY_FILLERS = [
    "帮我",
    "找一下",
    "查一下",
    "查询",
    "查",
    "找",
    "我",
    "我的",
    "把",
    "的",
    "这个",
    "这条",
    "当前",
    "今天",
    "明天",
    "后天",
    "大后天",
    "本周",
    "这周",
    "下周",
    "本月",
    "这个月",
    "有什么",
    "有哪些",
    "哪里",
    "在哪",
    "安排",
    "计划",
    "规划",
    "任务",
    "日历",
    "资料",
    "材料",
    "文档",
    "笔记",
    "之前",
    "上次",
    "最近",
    "未完成",
    "完成",
    "相关",
    "和",
    "有关",
    "改到",
    "改为",
    "改成",
    "调整到",
    "移到",
    "挪到",
    "推到",
    "删除",
    "删掉",
    "取消",
    "移除",
    "时长",
    "时间",
    "分钟",
    "小时",
]


def _parse_date(value: str) -> date_type:
    match = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", value.strip())
    if match:
        year, month, day = (int(part) for part in match.groups())
        return date_type(year, month, day)
    return date_type.fromisoformat(value.strip()[:10])


def _base_date(base_iso: str) -> date_type:
    try:
        return _parse_date(base_iso)
    except (TypeError, ValueError):
        return date_type.today()


def _month_end(value: date_type) -> date_type:
    if value.month == 12:
        return date_type(value.year, 12, 31)
    return date_type(value.year, value.month + 1, 1) - timedelta(days=1)


def _weekday_date(prefix: str, day_token: str, base: date_type) -> date_type:
    monday = base - timedelta(days=base.weekday())
    offset = 7 if prefix in {"下周", "下星期", "next"} else 0
    return monday + timedelta(days=offset + WEEKDAY_INDEX.get(day_token, 0))


def _date_candidates(text: str, base: date_type) -> list[tuple[int, date_type, str]]:
    candidates: list[tuple[int, date_type, str]] = []
    for match in re.finditer(r"\b(\d{4}-\d{1,2}-\d{1,2})\b", text):
        try:
            candidates.append((match.start(), _parse_date(match.group(1)), match.group(1)))
        except ValueError:
            pass
    phrase_offsets = [
        ("day after tomorrow", 2),
        ("tomorrow", 1),
        ("today", 0),
        ("大后天", 3),
        ("后天", 2),
        ("明天", 1),
        ("今日", 0),
        ("今天", 0),
    ]
    lower = text.lower()
    for phrase, offset in phrase_offsets:
        start = lower.find(phrase)
        if start >= 0:
            candidates.append((start, base + timedelta(days=offset), phrase))
    for match in re.finditer(r"(下周|本周|这周|下星期|星期|周)([一二三四五六日天1-7])", text):
        candidates.append((match.start(), _weekday_date(match.group(1), match.group(2), base), match.group(0)))
    for match in re.finditer(r"\b(next)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", lower):
        weekday_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        candidates.append((match.start(), _weekday_date("next", str(weekday_names.index(match.group(2)) + 1), base), match.group(0)))
    return sorted(candidates, key=lambda item: item[0])


def _first_date_expression(text: str, base_iso: str) -> tuple[date_type, str] | None:
    base = _base_date(base_iso)
    candidates = _date_candidates(text, base)
    if not candidates:
        return None
    _, value, label = candidates[0]
    return value, label


def _date_range_from_text(text: str, base_iso: str) -> dict[str, str] | None:
    base = _base_date(base_iso)
    lowered = text.lower()
    direct = _first_date_expression(text, base.isoformat())
    if direct:
        value, label = direct
        return {"startDate": value.isoformat(), "endDate": value.isoformat(), "label": label}
    if re.search(r"(本周|这周|this week)", lowered):
        start = base - timedelta(days=base.weekday())
        end = start + timedelta(days=6)
        return {"startDate": start.isoformat(), "endDate": end.isoformat(), "label": "本周"}
    if re.search(r"(下周|next week)", lowered):
        start = base - timedelta(days=base.weekday()) + timedelta(days=7)
        end = start + timedelta(days=6)
        return {"startDate": start.isoformat(), "endDate": end.isoformat(), "label": "下周"}
    if re.search(r"(本月|这个月|this month)", lowered):
        start = date_type(base.year, base.month, 1)
        return {"startDate": start.isoformat(), "endDate": _month_end(base).isoformat(), "label": "本月"}
    if re.search(r"(最近|recent|recently)", lowered):
        return {
            "startDate": (base - timedelta(days=30)).isoformat(),
            "endDate": (base + timedelta(days=30)).isoformat(),
            "label": "最近",
        }
    return None


def _query_terms(message: str) -> list[str]:
    text = message.lower()
    text = re.sub(r"\d{4}-\d{1,2}-\d{1,2}", " ", text)
    text = re.sub(r"\d{1,2}[:：]\d{2}", " ", text)
    text = re.sub(r"\d+(?:\.\d+)?\s*(分钟|分鐘|min|mins|minutes?|小时|小時|hours?|h)", " ", text)
    for filler in QUERY_FILLERS:
        text = text.replace(filler.lower(), " ")
    text = re.sub(r"(周|星期)[一二三四五六日天1-7]", " ", text)
    tokens = re.findall(r"[a-z0-9+#.-]+|[\u4e00-\u9fff]{2,}", text)
    return [token.strip(".-") for token in tokens if token.strip(".-")]


def _contains_any(text: str, words: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in words)


def _plan_card_from_row(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "date": row["date"],
        "time": row["time"],
        "title": row["content"],
        "done": bool(row["done"]),
        "completion": row["result"],
        "priority": row["priority"],
        "estimatedMinutes": int(row["estimated_minutes"] or 0),
        "source": row["source"],
        "sourceKey": row["source_key"] if "source_key" in row.keys() else "",
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def _plan_matches_terms(plan: dict[str, Any], terms: list[str]) -> bool:
    if not terms:
        return True
    haystack = " ".join(
        str(plan.get(key) or "")
        for key in ("title", "completion", "date", "time", "source", "sourceKey")
    ).lower()
    return all(term.lower() in haystack for term in terms)


def _search_calendar_plans(message: str, base_iso: str, *, limit: int = 12) -> tuple[list[dict[str, Any]], dict[str, str] | None]:
    date_range = _date_range_from_text(message, base_iso)
    terms = _query_terms(message)
    unfinished_only = _contains_any(message, ("未完成", "没完成", "unfinished", "pending"))
    params: tuple[Any, ...]
    where = []
    if date_range:
        where.append("date >= ? AND date <= ?")
        params = (date_range["startDate"], date_range["endDate"])
    else:
        params = ()
    if unfinished_only:
        where.append("done = 0")
    sql = "SELECT * FROM plans"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY date ASC, time ASC, created_at ASC"
    if not date_range:
        sql += " LIMIT 200"
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    plans = [_plan_card_from_row(row) for row in rows]
    if terms:
        plans = [plan for plan in plans if _plan_matches_terms(plan, terms)]
    return plans[:limit], date_range


def _search_goal_history(message: str, *, limit: int = 5) -> list[dict[str, Any]]:
    terms = _query_terms(message)
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, goal, deadline, summary, structured_plan_json, created_at, updated_at
            FROM planning_goals
            ORDER BY created_at DESC
            LIMIT 100
            """
        ).fetchall()
    results = []
    for row in rows:
        structured = _json_object(row["structured_plan_json"])
        haystack = " ".join(
            [
                row["goal"],
                row["summary"],
                str(structured.get("goalTitle") or ""),
                str(structured.get("goalDescription") or ""),
            ]
        ).lower()
        if terms and not any(term.lower() in haystack for term in terms):
            continue
        results.append(
            {
                "id": row["id"],
                "goal": row["goal"],
                "title": structured.get("goalTitle") or row["goal"],
                "summary": row["summary"],
                "deadline": row["deadline"],
                "createdAt": row["created_at"],
                "updatedAt": row["updated_at"],
            }
        )
        if len(results) >= limit:
            break
    return results


def _search_month_notes(message: str, *, limit: int = 5) -> list[dict[str, Any]]:
    terms = _query_terms(message)
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT year, month, content, updated_at
            FROM month_notes
            WHERE content != ''
            ORDER BY year DESC, month DESC
            LIMIT 120
            """
        ).fetchall()
    results = []
    for row in rows:
        content = row["content"]
        haystack = content.lower()
        if terms and not any(term.lower() in haystack for term in terms):
            continue
        results.append(
            {
                "year": row["year"],
                "month": row["month"],
                "content": content[:360],
                "updatedAt": row["updated_at"],
            }
        )
        if len(results) >= limit:
            break
    return results


def _query_result_text(result: dict[str, Any]) -> str:
    calendar_count = len(result.get("calendarPlans") or [])
    material_count = len(result.get("materials") or [])
    history_count = len(result.get("goalHistory") or [])
    note_count = len(result.get("monthNotes") or [])
    parts = []
    if calendar_count:
        parts.append(f"日历计划 {calendar_count} 个")
    if material_count:
        parts.append(f"资料 {material_count} 条")
    if history_count:
        parts.append(f"历史规划 {history_count} 条")
    if note_count:
        parts.append(f"月笔记 {note_count} 条")
    return "找到" + "、".join(parts) + "。" if parts else "没有找到匹配的计划、资料或笔记。"


def _looks_like_query(text: str) -> bool:
    lowered = text.lower()
    if re.search(r"(今天|明天|后天|本周|这周|下周|本月|最近).{0,12}(什么|哪些|安排|计划|任务|日程)", lowered):
        return True
    return bool(
        re.search(
            r"(查|查询|找|搜索|在哪|哪里|有什么|有哪些|未完成|history|search|find|what.*(plan|schedule|task)|where.*plan)",
            lowered,
        )
    )


def _looks_like_calendar_patch(text: str) -> bool:
    lowered = text.lower()
    if re.search(r"(重新生成|再生成|换个版本|更轻松|更激进|regenerate)", lowered):
        return False
    if re.search(r"(删除|删掉|取消|移除|delete|remove|cancel).{0,20}(计划|任务|日程|安排|plan|task|schedule)?", lowered):
        return True
    patch_words = r"(改到|改为|改成|调整到|移到|挪到|推到|改名|标题|名称|时长|时间|分钟|小时|reschedule|move|rename|change|update)"
    if re.search(patch_words, lowered) and (
        _first_date_expression(text, _today()) is not None
        or re.search(r"(第\s*\d+|第[一二三四五六七八九十]+|first|second|third|这个|这条|this)", lowered)
    ):
        return True
    return False


def _is_record(value: Any) -> bool:
    return isinstance(value, dict)


def _valid_structured_plan(value: Any) -> bool:
    if not _is_record(value):
        return False
    milestones = value.get("milestones")
    if not isinstance(milestones, list):
        return False
    for milestone in milestones:
        if not _is_record(milestone):
            continue
        tasks = milestone.get("tasks")
        if not isinstance(tasks, list):
            continue
        for task in tasks:
            if _is_record(task) and isinstance(task.get("title"), str) and task["title"].strip():
                return True
    return False


def _task_count(structured_plan: dict[str, Any]) -> int:
    count = 0
    for milestone in structured_plan.get("milestones") or []:
        if not _is_record(milestone):
            continue
        for task in milestone.get("tasks") or []:
            if _is_record(task) and isinstance(task.get("title"), str) and task["title"].strip():
                count += 1
    return count


def _milestone_count(structured_plan: dict[str, Any]) -> int:
    return len([item for item in structured_plan.get("milestones") or [] if _is_record(item)])


def _duration_days(structured_plan: dict[str, Any]) -> int:
    value = structured_plan.get("durationDays")
    try:
        parsed = int(value)
        if parsed > 0:
            return parsed
    except (TypeError, ValueError):
        pass
    dates: set[str] = set()
    for milestone in structured_plan.get("milestones") or []:
        if not _is_record(milestone):
            continue
        for task in milestone.get("tasks") or []:
            if _is_record(task) and isinstance(task.get("dueDate"), str) and re.match(r"^\d{4}-\d{2}-\d{2}", task["dueDate"]):
                dates.add(task["dueDate"][:10])
    return max(1, len(dates))


def _plan_title(structured_plan: dict[str, Any], fallback: str) -> str:
    for key in ("goalTitle", "title", "goal"):
        value = structured_plan.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback.strip()[:80] or "Planix 计划草稿"


def _task_key(milestone_index: int, task_index: int) -> str:
    return f"m{milestone_index}:t{task_index}"


def _refined_task_from_payload(value: Any) -> RefinedTask | None:
    if isinstance(value, RefinedTask):
        return value
    if isinstance(value, dict):
        try:
            return RefinedTask.model_validate(value)
        except Exception:
            return None
    return None


def _compact_summary(
    structured_plan: dict[str, Any],
    *,
    title: str,
    quality_status: str | None = None,
    plan_horizon: dict[str, Any] | None = None,
) -> str:
    milestones = _milestone_count(structured_plan)
    tasks = _task_count(structured_plan)
    days = _duration_days(structured_plan)
    quality_label = {
        "passed": "良好",
        "repaired": "已自动补全",
        "local_fallback": "本地模板兜底",
    }.get(str(quality_status or ""), "已生成")
    horizon_days = plan_horizon.get("durationDays") if isinstance(plan_horizon, dict) else days
    return (
        "已生成计划草稿。\n\n"
        "摘要：\n"
        f"- 计划：{title}\n"
        f"- {milestones} 个阶段\n"
        f"- {tasks} 个任务\n"
        f"- 覆盖 {horizon_days} 天\n"
        f"- 计划质量：{quality_label}\n"
        "- 可写入日历\n\n"
        "你可以继续说：\n"
        "“展开看看完整计划”\n"
        "“重新生成一个更轻松的版本”\n"
        "“把这个计划写进日历”"
    )


def _runtime_tool_summary(name: str) -> str:
    labels = {
        "get_memory": "读取记忆",
        "get_today_plans": "读取今日计划",
        "search_materials": "检索本地资料",
        "enrich_with_model_knowledge": "大模型知识补全",
        "propose_tasks": "生成任务提案",
    }
    return labels.get(name, name)


def _normalize_task_date(value: Any, fallback: str) -> str:
    if isinstance(value, str):
        if re.match(r"^\d{4}-\d{2}-\d{2}$", value):
            return value
        if re.match(r"^\d{4}-\d{2}-\d{2}T", value):
            return value[:10]
    return fallback


def _default_task_time(sequence: int) -> str:
    hour = min(21, 9 + (sequence % 9))
    return f"{hour:02d}:00"


def _task_priority(value: Any) -> str:
    return value if value in {"low", "medium", "high"} else "medium"


def _task_minutes(value: Any) -> int:
    try:
        parsed = int(value)
        if 1 <= parsed <= 1440:
            return parsed
    except (TypeError, ValueError):
        pass
    return 60


def _write_result_text(result: dict[str, Any]) -> str:
    created = int(result.get("created") or 0)
    updated = int(result.get("updated") or 0)
    failed = int(result.get("failed") or 0)
    if failed and (created or updated):
        return f"部分计划写入成功，失败 {failed} 个。"
    if failed:
        return "写入日历失败，请检查后端服务或计划数据。"
    return f"已写入日历：创建 {created} 个，更新 {updated} 个，失败 {failed} 个。"


def _patch_result_text(result: dict[str, Any]) -> str:
    if result.get("status") == "failed":
        return str(result.get("error") or "修改日历计划失败。")
    operation = result.get("operation")
    if operation == "delete":
        return "已删除日历计划。"
    return "已更新日历计划。"


def _extract_ordinal(message: str) -> int | None:
    lowered = message.lower()
    number_match = re.search(r"(?:第\s*)?(\d+)(?:\s*(?:个|项|条|号|task))", lowered)
    if number_match:
        value = int(number_match.group(1))
        return value if value > 0 else None
    zh_numbers = {
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
    }
    zh_match = re.search(r"第\s*([一二两三四五六七八九十])\s*(?:个|项|条|号)?", message)
    if zh_match:
        return zh_numbers.get(zh_match.group(1))
    english = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5}
    for word, value in english.items():
        if re.search(rf"\b{word}\b", lowered):
            return value
    return None


def _target_date_after_patch_verb(message: str, base_iso: str) -> str | None:
    for match in re.finditer(r"(改到|改为|改成|调整到|移到|挪到|推到|reschedule\s+to|move\s+to|change\s+to)", message, re.I):
        tail = message[match.end(): match.end() + 40]
        resolved = _first_date_expression(tail, base_iso)
        if resolved:
            return resolved[0].isoformat()
    return None


def _target_time_from_message(message: str) -> str | None:
    match = re.search(r"(\d{1,2})[:：](\d{2})", message)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"
    match = re.search(r"(上午|早上|下午|晚上)?\s*(\d{1,2})\s*点(?:\s*(半|(\d{1,2})\s*分?))?", message)
    if match:
        hour = int(match.group(2))
        if match.group(1) in {"下午", "晚上"} and hour < 12:
            hour += 12
        minute = 30 if match.group(3) == "半" else int(match.group(4) or 0)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"
    return None


def _target_minutes_from_message(message: str) -> int | None:
    minute_match = re.search(r"(\d{1,4})\s*(分钟|分鐘|min|mins|minutes?)", message, re.I)
    if minute_match:
        value = int(minute_match.group(1))
        return min(max(value, 1), 1440)
    hour_match = re.search(r"(\d+(?:\.\d+)?)\s*(小时|小時|hours?|h)(?:\b|$)", message, re.I)
    if hour_match:
        value = round(float(hour_match.group(1)) * 60)
        return min(max(value, 1), 1440)
    return None


def _target_title_from_message(message: str) -> str | None:
    if not re.search(r"(标题|名称|名字|改名|rename|title)", message, re.I):
        return None
    match = re.search(r"(?:改成|改为|叫|命名为|rename\s+to|title\s+to)\s*[“\"']?(.+?)[”\"']?$", message, re.I)
    if not match:
        return None
    title = re.sub(r"[。.!！]+$", "", match.group(1).strip())
    return title[:160] if title else None


def _patch_changes_from_message(message: str, base_iso: str) -> dict[str, Any]:
    changes: dict[str, Any] = {}
    target_date = _target_date_after_patch_verb(message, base_iso)
    target_time = _target_time_from_message(message)
    target_minutes = _target_minutes_from_message(message)
    target_title = _target_title_from_message(message)
    if target_date:
        changes["date"] = target_date
    if target_time:
        changes["time"] = target_time
    if target_minutes:
        changes["estimatedMinutes"] = target_minutes
    if target_title:
        changes["content"] = target_title
    return changes


def _is_delete_request(message: str) -> bool:
    return bool(re.search(r"(删除|删掉|取消|移除|delete|remove|cancel)", message, re.I))


def _truncate_context_line(value: str, limit: int = 220) -> str:
    cleaned = re.sub(r"\s+", " ", value or "").strip()
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[:limit].rstrip()}..."


def _runtime_input_with_thread_context(message: str, context_summary: str) -> str:
    if not context_summary.strip():
        return message
    return (
        "当前用户请求：\n"
        f"{message}\n\n"
        "当前对话上下文（仅来自当前 thread，用于承接指代、地点、主题和约束；不要使用其它对话的内容）：\n"
        f"{context_summary}"
    )


class CommandAgentService:
    def ensure_thread(self, thread_id: str | None = None, title: str = "") -> str:
        if thread_id:
            with get_conn() as conn:
                row = conn.execute("SELECT id FROM command_threads WHERE id = ?", (thread_id,)).fetchone()
                if row:
                    conn.execute("UPDATE command_threads SET updated_at = ? WHERE id = ?", (_now(), thread_id))
                    return thread_id

        new_id = thread_id or str(uuid4())
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO command_threads(id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (new_id, (title or "Planix Command").strip()[:160], _now(), _now()),
            )
        return new_id

    def add_message(
        self,
        thread_id: str,
        role: str,
        content: str,
        *,
        kind: str = "text",
        payload: dict[str, Any] | None = None,
    ) -> CommandMessageOut:
        message_id = str(uuid4())
        created_at = _now()
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO command_messages(id, thread_id, role, content, kind, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    thread_id,
                    role,
                    content,
                    kind,
                    json.dumps(payload or {}, ensure_ascii=False),
                    created_at,
                ),
            )
            conn.execute("UPDATE command_threads SET updated_at = ? WHERE id = ?", (created_at, thread_id))
        return CommandMessageOut(
            id=message_id,
            threadId=thread_id,
            role=role,
            content=content,
            kind=kind,
            payload=payload or {},
            createdAt=created_at,
        )

    def list_threads(self, limit: int = 50) -> list[CommandThreadSummaryOut]:
        safe_limit = min(max(int(limit or 50), 1), 100)
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT
                  t.id,
                  t.title,
                  t.created_at,
                  t.updated_at,
                  COUNT(m.id) AS message_count,
                  COALESCE(cd.title, '') AS current_draft_title
                FROM command_threads t
                LEFT JOIN command_messages m ON m.thread_id = t.id
                LEFT JOIN command_drafts cd
                  ON cd.thread_id = t.id
                 AND cd.kind = 'calendar_plan'
                 AND cd.status = 'current'
                GROUP BY t.id
                ORDER BY t.updated_at DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        return [
            CommandThreadSummaryOut(
                id=row["id"],
                title=row["title"],
                messageCount=int(row["message_count"] or 0),
                currentDraftTitle=row["current_draft_title"] or "",
                createdAt=row["created_at"],
                updatedAt=row["updated_at"],
            )
            for row in rows
        ]

    def delete_thread(self, thread_id: str) -> dict[str, int]:
        with get_conn() as conn:
            existing = conn.execute("SELECT id FROM command_threads WHERE id = ?", (thread_id,)).fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail="Thread not found")
            conn.execute("DELETE FROM command_approvals WHERE thread_id = ?", (thread_id,))
            conn.execute("DELETE FROM command_actions WHERE thread_id = ?", (thread_id,))
            conn.execute("DELETE FROM command_drafts WHERE thread_id = ?", (thread_id,))
            conn.execute("DELETE FROM command_messages WHERE thread_id = ?", (thread_id,))
            conn.execute("DELETE FROM command_threads WHERE id = ?", (thread_id,))
        return {"deleted": 1}

    def get_thread(self, thread_id: str):
        from ..schemas import CommandThreadOut

        with get_conn() as conn:
            thread = conn.execute("SELECT * FROM command_threads WHERE id = ?", (thread_id,)).fetchone()
            if not thread:
                raise HTTPException(status_code=404, detail="Thread not found")
            messages = [
                _row_to_message(row)
                for row in conn.execute(
                    "SELECT * FROM command_messages WHERE thread_id = ? ORDER BY created_at ASC",
                    (thread_id,),
                ).fetchall()
            ]
            current_draft = self._current_draft(conn, thread_id)
        return CommandThreadOut(
            id=thread["id"],
            title=thread["title"],
            messages=messages,
            currentDraft=current_draft,
            createdAt=thread["created_at"],
            updatedAt=thread["updated_at"],
        )

    def _thread_context_summary(self, thread_id: str, exclude_message_id: str = "", limit: int = 8) -> str:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT id, role, content
                FROM command_messages
                WHERE thread_id = ?
                  AND role IN ('user', 'assistant')
                  AND kind = 'text'
                  AND content != ''
                  AND id != ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (thread_id, exclude_message_id, limit),
            ).fetchall()
        lines: list[str] = []
        for row in reversed(rows):
            role = "用户" if row["role"] == "user" else "Planix"
            content = _truncate_context_line(row["content"])
            if content:
                lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def stream_chat(self, payload: CommandChatRequest) -> Iterator[str]:
        thread_id = ""
        intent = detect_command_intent(payload.message)
        try:
            thread_id = self.ensure_thread(payload.thread_id, title=payload.message)
            intent = resolve_command_intent(
                payload.message,
                intent,
                has_current_draft=self._get_current_draft(thread_id) is not None,
            )
            yield from self._stream_chat_impl(thread_id, payload, intent=intent)
        except AssertionError:
            raise
        except Exception as exc:
            yield from self._stream_failure(
                thread_id,
                _stream_failure_message(payload, intent),
                exc,
            )

    def _stream_chat_impl(self, thread_id: str, payload: CommandChatRequest, *, intent: CommandIntent) -> Iterator[str]:
        user_message = self.add_message(thread_id, "user", payload.message)
        yield _ndjson({"type": "thread", "threadId": thread_id})

        if payload.mode == "chat":
            content = self._chat_locked_or_normal(thread_id, payload, intent, exclude_message_id=user_message.id)
            self.add_message(thread_id, "assistant", content)
            yield _ndjson({"type": "assistant_delta", "text": content})
            yield _ndjson({"type": "done", "threadId": thread_id})
            return

        if payload.mode == "workbench":
            yield from self._stream_runtime_handoff(thread_id, payload, exclude_message_id=user_message.id, auto_detail=True)
            yield _ndjson({"type": "done", "threadId": thread_id})
            return

        if payload.mode == "auto" and intent == "show_current_plan":
            yield from self._stream_plan_detail(thread_id)
            yield _ndjson({"type": "done", "threadId": thread_id})
            return

        if payload.mode == "auto" and intent in {"regenerate_draft", "modify_current_draft"}:
            yield from self._stream_regenerate_draft(thread_id, payload, exclude_message_id=user_message.id)
            yield _ndjson({"type": "done", "threadId": thread_id})
            return

        if payload.mode == "auto" and intent == "refine_current_plan":
            yield from self._stream_refine_current_plan(thread_id, payload)
            yield _ndjson({"type": "done", "threadId": thread_id})
            return

        if payload.mode == "auto" and intent == "sync_to_calendar":
            yield from self._stream_calendar_write(thread_id, payload)
            yield _ndjson({"type": "done", "threadId": thread_id})
            return

        if payload.mode == "auto" and intent == "query_plan":
            yield from self._stream_query_plan(thread_id, payload)
            yield _ndjson({"type": "done", "threadId": thread_id})
            return

        if payload.mode == "auto" and intent == "patch_calendar_plan":
            yield from self._stream_patch_calendar_plan(thread_id, payload)
            yield _ndjson({"type": "done", "threadId": thread_id})
            return

        if payload.mode == "auto" and intent not in {"normal_chat", "planning_request"}:
            content = _intent_reply(intent, payload.message)
        else:
            content = self._llm_chat(payload, thread_id=thread_id, exclude_message_id=user_message.id)
        self.add_message(thread_id, "assistant", content)
        yield _ndjson({"type": "assistant_delta", "text": content})
        yield _ndjson({"type": "done", "threadId": thread_id})

    def stream_approve(self, payload: CommandApproveRequest) -> Iterator[str]:
        thread_id = payload.thread_id or ""
        action = None
        try:
            action = self._load_action(payload.action_id)
            if action and not thread_id:
                thread_id = action["thread_id"]
            yield from self._stream_approve_impl(payload, action=action)
        except AssertionError:
            raise
        except Exception as exc:
            yield from self._stream_failure(
                thread_id,
                _approval_failure_message(action),
                exc,
            )

    def _stream_approve_impl(self, payload: CommandApproveRequest, *, action=None) -> Iterator[str]:
        action = action or self._load_action(payload.action_id)
        if not action:
            yield _ndjson({"type": "error", "error": "找不到待审批的操作。"})
            return
        thread_id = payload.thread_id or action["thread_id"]
        yield _ndjson({"type": "thread", "threadId": thread_id})

        decision = payload.decision
        if payload.approved is not None:
            decision = "approve" if payload.approved else "reject"
        self._record_approval(thread_id, payload.action_id, payload.permission, decision)

        if decision == "reject":
            self._update_action(payload.action_id, status="rejected", result={"decision": "reject"})
            content = "已取消操作，未修改日历。" if action["operation"] in {"update", "delete"} else "已取消写入日历。"
            self.add_message(
                thread_id,
                "card",
                content,
                kind="execution_result",
                payload={"status": "rejected", "actionId": payload.action_id},
            )
            yield _ndjson({"type": "execution_result", "status": "rejected", "text": content, "actionId": payload.action_id})
            yield _ndjson({"type": "done", "threadId": thread_id})
            return

        result = self._execute_calendar_action(payload.action_id)
        if action["operation"] in {"update", "delete"}:
            text = _patch_result_text(result)
            self.add_message(thread_id, "card", text, kind="plan_patch_result", payload=result)
            yield _ndjson({"type": "plan_patch_result", **result})
            yield _ndjson({"type": "execution_result", "status": "success" if result.get("status") == "success" else "failed", "text": text})
            yield _ndjson({"type": "done", "threadId": thread_id})
            return
        text = _write_result_text(result)
        self.add_message(thread_id, "card", text, kind="calendar_write_result", payload=result)
        yield _ndjson({"type": "calendar_write_result", **result})
        yield _ndjson({"type": "execution_result", "status": "success" if not result.get("failed") else "failed", "text": text})
        yield _ndjson({"type": "done", "threadId": thread_id})

    def _stream_failure(self, thread_id: str, message: str, exc: Exception) -> Iterator[str]:
        if thread_id:
            try:
                self.add_message(thread_id, "assistant", message)
            except Exception:
                pass
        yield _ndjson({"type": "error", "error": message, "detail": str(exc)})
        if thread_id:
            yield _ndjson({"type": "done", "threadId": thread_id})

    def _chat_locked_or_normal(
        self,
        thread_id: str,
        payload: CommandChatRequest,
        intent: CommandIntent,
        *,
        exclude_message_id: str = "",
    ) -> str:
        locked = _chat_lock_reply(intent, payload.message)
        if locked:
            return locked
        return self._llm_chat(payload, thread_id=thread_id, exclude_message_id=exclude_message_id)

    def _stream_query_plan(self, thread_id: str, payload: CommandChatRequest) -> Iterator[str]:
        base_iso = _context_date(payload)
        calendar_plans, date_range = _search_calendar_plans(payload.message, base_iso)
        terms = _query_terms(payload.message)
        material_query = " ".join(terms) or payload.message
        materials = []
        if terms or _contains_any(payload.message, ("资料", "材料", "文档", "笔记", "material", "note", "doc")):
            materials = [source.model_dump(by_alias=True) for source in RagService().retrieve(material_query, limit=4)]
        goal_history = _search_goal_history(payload.message)
        month_notes = _search_month_notes(payload.message)
        result = {
            "query": payload.message,
            "dateRange": date_range,
            "calendarPlans": calendar_plans,
            "materials": materials,
            "goalHistory": goal_history,
            "monthNotes": month_notes,
        }
        result["summary"] = _query_result_text(result)
        self.add_message(thread_id, "card", result["summary"], kind="plan_search_results", payload=result)
        yield _ndjson({"type": "plan_search_results", **result})

    def _last_plan_search_results(self, thread_id: str) -> list[dict[str, Any]]:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT payload_json
                FROM command_messages
                WHERE thread_id = ? AND kind = 'plan_search_results'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (thread_id,),
            ).fetchone()
        if not row:
            return []
        payload = _json_object(row["payload_json"])
        plans = payload.get("calendarPlans")
        return [plan for plan in plans if _is_record(plan)] if isinstance(plans, list) else []

    def _load_plan_payload(self, plan_id: str) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
        return _plan_card_from_row(row) if row else None

    def _select_patch_candidates(self, thread_id: str, message: str, base_iso: str) -> list[dict[str, Any]]:
        ordinal = _extract_ordinal(message)
        last_results = self._last_plan_search_results(thread_id)
        if ordinal and 1 <= ordinal <= len(last_results):
            plan = self._load_plan_payload(str(last_results[ordinal - 1].get("id") or ""))
            return [plan] if plan else []
        if not ordinal and len(last_results) == 1 and not _first_date_expression(message, base_iso):
            plan = self._load_plan_payload(str(last_results[0].get("id") or ""))
            return [plan] if plan else []

        source_date = _first_date_expression(message, base_iso)
        terms = _query_terms(message)
        where = []
        params: list[Any] = []
        if source_date:
            where.append("date = ?")
            params.append(source_date[0].isoformat())
        sql = "SELECT * FROM plans"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY date ASC, time ASC, created_at ASC LIMIT 100"
        with get_conn() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        candidates = [_plan_card_from_row(row) for row in rows]
        if terms:
            candidates = [plan for plan in candidates if _plan_matches_terms(plan, terms)]
        return candidates[:12]

    def _stream_patch_calendar_plan(self, thread_id: str, payload: CommandChatRequest) -> Iterator[str]:
        base_iso = _context_date(payload)
        candidates = self._select_patch_candidates(thread_id, payload.message, base_iso)
        if not candidates:
            content = "没有找到要修改的日历计划。你可以先问“今天有什么安排”，再说“把第一个改到后天”。"
            self.add_message(thread_id, "assistant", content)
            yield _ndjson({"type": "assistant_delta", "text": content})
            return
        if len(candidates) > 1:
            result = {
                "query": payload.message,
                "dateRange": _date_range_from_text(payload.message, base_iso),
                "calendarPlans": candidates,
                "materials": [],
                "goalHistory": [],
                "monthNotes": [],
                "summary": "找到多个可能的计划，请说明要修改第几个。",
            }
            self.add_message(thread_id, "card", result["summary"], kind="plan_search_results", payload=result)
            yield _ndjson({"type": "plan_search_results", **result})
            return

        before = candidates[0]
        operation = "delete" if _is_delete_request(payload.message) else "update"
        changes = {} if operation == "delete" else _patch_changes_from_message(payload.message, base_iso)
        if operation == "update" and not changes:
            content = "我找到了计划，但没有识别到要改的字段。第一版支持改标题、日期、时间和预计时长。"
            self.add_message(thread_id, "assistant", content)
            yield _ndjson({"type": "assistant_delta", "text": content})
            return

        after = {**before, **changes}
        action_id = self._create_calendar_patch_action(thread_id, operation, before, after, changes)
        risk = "delete" if operation == "delete" else "write"
        preview = {
            "actionId": action_id,
            "operation": operation,
            "risk": risk,
            "before": before,
            "after": after,
            "changes": changes,
        }
        self.add_message(thread_id, "card", "准备修改日历计划", kind="plan_patch_preview", payload=preview)
        yield _ndjson({"type": "plan_patch_preview", **preview})

        requires_approval = command_action_requires_approval(payload.permission, risk) or (
            operation == "delete" and before.get("source") == "manual"
        )
        if requires_approval:
            self._update_action(action_id, status="waiting_approval")
            self._record_approval(thread_id, action_id, payload.permission, "pending")
            summary = "准备删除日历计划，需要确认。" if operation == "delete" else "准备修改日历计划，需要确认。"
            approval = {
                "actionId": action_id,
                "draftId": "",
                "permission": payload.permission,
                "risk": risk,
                "summary": summary,
            }
            self.add_message(thread_id, "card", summary, kind="approval_request", payload=approval)
            yield _ndjson({"type": "approval_required", **approval})
            return

        result = self._execute_calendar_action(action_id)
        text = _patch_result_text(result)
        self.add_message(thread_id, "card", text, kind="plan_patch_result", payload=result)
        yield _ndjson({"type": "plan_patch_result", **result})

    def _current_draft(self, conn, thread_id: str) -> CommandDraftOut | None:
        return _row_to_draft(
            conn.execute(
                """
                SELECT * FROM command_drafts
                WHERE thread_id = ? AND kind = 'calendar_plan' AND status = 'current'
                ORDER BY version DESC
                LIMIT 1
                """,
                (thread_id,),
            ).fetchone()
        )

    def _get_current_draft(self, thread_id: str) -> CommandDraftOut | None:
        with get_conn() as conn:
            return self._current_draft(conn, thread_id)

    def _stream_plan_detail(self, thread_id: str) -> Iterator[str]:
        draft = self._get_current_draft(thread_id)
        if not draft:
            content = "当前线程还没有可展开的计划草稿。你可以先说“帮我规划本周安排”。"
            self.add_message(thread_id, "assistant", content)
            yield _ndjson({"type": "assistant_delta", "text": content})
            return
        structured_plan = draft.payload.get("structuredPlan")
        if not _valid_structured_plan(structured_plan):
            content = "当前计划草稿结构不完整，无法展开。请重新生成一个计划草稿。"
            self.add_message(thread_id, "assistant", content)
            yield _ndjson({"type": "assistant_delta", "text": content})
            return
        payload = {
            "draftId": draft.id,
            "version": draft.version,
            "title": draft.title,
            "structuredPlan": structured_plan,
            "planHorizon": draft.payload.get("planHorizon") if isinstance(draft.payload.get("planHorizon"), dict) else None,
            "qualityReport": draft.payload.get("qualityReport") if isinstance(draft.payload.get("qualityReport"), dict) else None,
            "qualityStatus": draft.payload.get("qualityStatus"),
            "sourceType": draft.payload.get("sourceType"),
            "localRelevance": draft.payload.get("localRelevance"),
        }
        self.add_message(thread_id, "card", draft.title, kind="plan_detail", payload=payload)
        yield _ndjson({"type": "plan_detail", **payload})

    def _stream_regenerate_draft(
        self,
        thread_id: str,
        payload: CommandChatRequest,
        *,
        exclude_message_id: str = "",
    ) -> Iterator[str]:
        draft = self._get_current_draft(thread_id)
        if not draft:
            content = "当前线程还没有可重新生成的计划草稿。你可以先说“帮我规划本周安排”。"
            self.add_message(thread_id, "assistant", content)
            yield _ndjson({"type": "assistant_delta", "text": content})
            return
        structured_plan = draft.payload.get("structuredPlan")
        if not _valid_structured_plan(structured_plan):
            content = "当前计划草稿结构不完整，无法继续修改。请先重新生成一个计划草稿。"
            self.add_message(thread_id, "assistant", content)
            yield _ndjson({"type": "assistant_delta", "text": content})
            return
        instruction = (
            f"请基于当前计划草稿重新生成一个完整计划。\n\n"
            f"用户新要求：{payload.message}\n\n"
            f"当前计划草稿 JSON：\n{json.dumps(structured_plan, ensure_ascii=False)}"
        )
        regenerate_payload = payload.model_copy(update={"message": instruction})
        yield from self._stream_runtime_handoff(
            thread_id,
            regenerate_payload,
            exclude_message_id=exclude_message_id,
            auto_detail=True,
        )

    def _draft_task_records(self, draft: CommandDraftOut) -> list[dict[str, Any]]:
        structured_plan = draft.payload.get("structuredPlan")
        if not _valid_structured_plan(structured_plan):
            return []
        records: list[dict[str, Any]] = []
        for milestone_index, milestone in enumerate(structured_plan.get("milestones") or []):
            if not _is_record(milestone):
                continue
            milestone_title = str(milestone.get("title") or "").strip()
            for task_index, task in enumerate(milestone.get("tasks") or []):
                if not _is_record(task):
                    continue
                title = str(task.get("title") or "").strip()
                if not title:
                    continue
                records.append({
                    "key": _task_key(milestone_index, task_index),
                    "milestoneIndex": milestone_index,
                    "taskIndex": task_index,
                    "milestoneTitle": milestone_title,
                    "title": title,
                    "description": str(task.get("description") or "").strip(),
                    "dueDate": task.get("dueDate"),
                    "estimatedMinutes": task.get("estimatedMinutes"),
                    "priority": task.get("priority"),
                })
        return records

    def _selected_refine_tasks(self, draft: CommandDraftOut, message: str) -> list[dict[str, Any]]:
        records = self._draft_task_records(draft)
        if not records:
            return []
        text = message.strip().lower()
        if re.search(r"(全部|所有|一键|all|every)", text):
            first_milestone = records[0]["milestoneIndex"]
            return [record for record in records if record["milestoneIndex"] == first_milestone][:5]

        number_match = re.search(r"(?:第|task\s*)?(\d+)(?:\s*(?:个|项|条|号|task))?", text)
        if number_match:
            index = int(number_match.group(1)) - 1
            if 0 <= index < len(records):
                return [records[index]]

        matched = []
        for record in records:
            title = str(record["title"]).strip()
            if title and title.lower() in text:
                matched.append(record)
        return (matched[:5] if matched else records[:1])

    def _save_draft_refinements(
        self,
        draft: CommandDraftOut,
        refinements: dict[str, dict[str, Any]],
    ) -> None:
        payload = dict(draft.payload)
        existing = payload.get("refinements")
        if not isinstance(existing, dict):
            existing = {}
        existing.update(refinements)
        payload["refinements"] = existing
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE command_drafts
                SET payload_json = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (json.dumps(payload, ensure_ascii=False), _now(), draft.id),
            )
            conn.execute("UPDATE command_threads SET updated_at = ? WHERE id = ?", (_now(), draft.thread_id))

    def _stream_refine_current_plan(self, thread_id: str, payload: CommandChatRequest) -> Iterator[str]:
        draft = self._get_current_draft(thread_id)
        if not draft:
            content = "当前线程还没有可细化的计划草稿。你可以先说“帮我做个规划”。"
            self.add_message(thread_id, "assistant", content)
            yield _ndjson({"type": "assistant_delta", "text": content})
            return

        tasks = self._selected_refine_tasks(draft, payload.message)
        if not tasks:
            content = "当前计划草稿里没有可细化的任务。请重新生成计划后再试。"
            self.add_message(thread_id, "assistant", content)
            yield _ndjson({"type": "assistant_delta", "text": content})
            return

        yield _ndjson({"type": "refinement_started", "draftId": draft.id, "total": len(tasks)})
        service = PlanningService()
        output_language = "en" if _looks_english(payload.message) else "zh"
        new_refinements: dict[str, dict[str, Any]] = {}
        items: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        goal = str(draft.payload.get("goal") or draft.title)

        for record in tasks:
            key = str(record["key"])
            try:
                refined = service.refine_task(
                    RefineTaskRequest(
                        goal=goal,
                        taskTitle=str(record["title"]),
                        taskDescription="\n".join(
                            value for value in [
                                f"Milestone: {record.get('milestoneTitle')}",
                                str(record.get("description") or ""),
                            ] if value
                        ),
                        date=_normalize_task_date(record.get("dueDate"), _today()),
                        availableMinutes=_task_minutes(record.get("estimatedMinutes")),
                        planContext=build_refine_plan_context(
                            draft.payload.get("structuredPlan"),
                            milestone_index=int(record["milestoneIndex"]),
                            task_index=int(record["taskIndex"]),
                            sources=draft.payload.get("sources") if isinstance(draft.payload.get("sources"), list) else [],
                            plan_horizon=draft.payload.get("planHorizon") if isinstance(draft.payload.get("planHorizon"), dict) else None,
                            quality_status=str(draft.payload.get("qualityStatus") or ""),
                            daily_learning_minutes=_task_minutes(record.get("estimatedMinutes")),
                        ),
                        retrievedSources=draft.payload.get("sources") if isinstance(draft.payload.get("sources"), list) else [],
                        outputLanguage=output_language,
                        refinementInstruction=payload.message,
                    )
                )
                refined_payload = refined.model_dump(by_alias=True)
                new_refinements[key] = refined_payload
                items.append({
                    "taskKey": key,
                    "taskTitle": record["title"],
                    "milestoneTitle": record.get("milestoneTitle") or "",
                    "milestoneIndex": record["milestoneIndex"],
                    "taskIndex": record["taskIndex"],
                    "refinedTask": refined_payload,
                })
            except Exception as exc:
                errors.append({"taskKey": key, "taskTitle": str(record["title"]), "error": str(exc)})

        if new_refinements:
            self._save_draft_refinements(draft, new_refinements)

        result = {
            "draftId": draft.id,
            "total": len(tasks),
            "succeeded": len(items),
            "failed": len(errors),
            "items": items,
            "errors": errors,
        }
        content = f"已细化 {len(items)} 个任务，失败 {len(errors)} 个。"
        self.add_message(thread_id, "card", content, kind="refined_tasks_result", payload=result)
        yield _ndjson({"type": "refined_tasks_result", **result})

    def _stream_calendar_write(self, thread_id: str, payload: CommandChatRequest) -> Iterator[str]:
        try:
            yield from self._stream_calendar_write_impl(thread_id, payload)
        except AssertionError:
            raise
        except Exception as exc:
            yield from self._stream_failure(thread_id, CALENDAR_WRITE_ERROR_MESSAGE, exc)

    def _stream_calendar_write_impl(self, thread_id: str, payload: CommandChatRequest) -> Iterator[str]:
        draft = self._get_current_draft(thread_id)
        if not draft:
            content = "当前线程还没有可写入日历的计划草稿。你可以先生成一个计划草稿。"
            self.add_message(thread_id, "assistant", content)
            yield _ndjson({"type": "assistant_delta", "text": content})
            return
        items = self._calendar_items_from_draft(draft)
        if not items:
            content = "当前计划草稿里没有可写入日历的任务。请重新生成计划后再试。"
            self.add_message(thread_id, "assistant", content)
            yield _ndjson({"type": "assistant_delta", "text": content})
            return

        action_id = self._create_calendar_action(thread_id, draft, items)
        preview = {
            "actionId": action_id,
            "draftId": draft.id,
            "title": draft.title,
            "plans": items,
        }
        self.add_message(thread_id, "card", "准备写入日历", kind="calendar_plan_preview", payload=preview)
        yield _ndjson({"type": "calendar_plan_preview", **preview})

        if command_action_requires_approval(payload.permission, "write"):
            self._update_action(action_id, status="waiting_approval")
            self._record_approval(thread_id, action_id, payload.permission, "pending")
            approval = {
                "actionId": action_id,
                "draftId": draft.id,
                "permission": payload.permission,
                "risk": "write",
                "summary": f"准备写入 {len(items)} 个日历计划，需要确认。",
            }
            self.add_message(thread_id, "card", approval["summary"], kind="approval_request", payload=approval)
            yield _ndjson({"type": "approval_required", **approval})
            return

        result = self._execute_calendar_action(action_id)
        text = _write_result_text(result)
        self.add_message(thread_id, "card", text, kind="calendar_write_result", payload=result)
        yield _ndjson({"type": "calendar_write_result", **result})

    def _stream_runtime_handoff(
        self,
        thread_id: str,
        payload: CommandChatRequest,
        *,
        exclude_message_id: str = "",
        auto_detail: bool = False,
    ) -> Iterator[str]:
        yield _ndjson({"type": "runtime_started", "message": "开始运行 Dashboard Runtime"})
        context = payload.context if isinstance(payload.context, dict) else {}
        preferences = context.get("preferences", "")
        if not isinstance(preferences, (str, dict)):
            preferences = ""
        materials = context.get("materials", "")
        if not isinstance(materials, str):
            materials = ""
        data = context.get("data", {})
        if not isinstance(data, dict):
            data = {}
        thread_context = self._thread_context_summary(thread_id, exclude_message_id=exclude_message_id)
        runtime_input = _runtime_input_with_thread_context(payload.message, thread_context)
        runtime_payload = AgentRunRequest(
            input=runtime_input,
            date=_context_date(payload),
            preferences=preferences,
            materials=materials,
            data=data,
        )

        proposal_output: dict[str, Any] | None = None
        proposal_input: dict[str, Any] = {}
        source_run_id = ""
        runtime_failed = ""
        seen_tools: set[tuple[str, str]] = set()

        try:
            for chunk in RuntimeOrchestrator().run(runtime_payload):
                for line in str(chunk).splitlines():
                    if not line.strip():
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(event.get("runId"), str):
                        source_run_id = event["runId"]
                    event_type = event.get("type")
                    if event_type == "node" and isinstance(event.get("title"), str) and event.get("title") in KEY_RUNTIME_TOOLS:
                        name = str(event["title"])
                        key = (name, "running")
                        if key not in seen_tools:
                            seen_tools.add(key)
                            yield _ndjson({
                                "type": "runtime_event",
                                "name": name,
                                "status": "running",
                                "summary": _runtime_tool_summary(name),
                            })
                    if event_type == "tool":
                        tool_call = event.get("toolCall")
                        if isinstance(tool_call, dict):
                            name = str(tool_call.get("name") or "")
                            if name in KEY_RUNTIME_TOOLS:
                                yield _ndjson({
                                    "type": "runtime_event",
                                    "name": name,
                                    "status": "success",
                                    "summary": _runtime_tool_summary(name),
                                })
                            if name == "propose_tasks" and isinstance(tool_call.get("output"), dict):
                                proposal_output = tool_call["output"]
                                if isinstance(tool_call.get("input"), dict):
                                    proposal_input = tool_call["input"]
                    if event_type == "error":
                        runtime_failed = str(event.get("error") or "Runtime failed")
                        yield _ndjson({"type": "runtime_event", "name": "runtime", "status": "error", "summary": runtime_failed})
        except AssertionError:
            raise
        except Exception as exc:
            runtime_failed = f"Runtime handoff failed: {exc}"

        if runtime_failed:
            content = f"计划草稿生成失败：{runtime_failed}。没有创建 draft，也没有写入日历。"
            self.add_message(thread_id, "assistant", content)
            yield _ndjson({"type": "assistant_delta", "text": content})
            return

        if not proposal_output or not _valid_structured_plan(proposal_output.get("structuredPlan")):
            content = "计划草稿生成失败：Runtime 没有返回合法的 structuredPlan。没有创建 draft，也没有写入日历。"
            self.add_message(thread_id, "assistant", content)
            yield _ndjson({"type": "assistant_delta", "text": content})
            return

        structured_plan = proposal_output["structuredPlan"]
        title = _plan_title(structured_plan, proposal_input.get("goal") or payload.message)
        plan_horizon = proposal_output.get("planHorizon") if isinstance(proposal_output.get("planHorizon"), dict) else None
        quality_report = proposal_output.get("qualityReport") if isinstance(proposal_output.get("qualityReport"), dict) else None
        summary = _compact_summary(
            structured_plan,
            title=title,
            quality_status=str(proposal_output.get("qualityStatus") or ""),
            plan_horizon=plan_horizon,
        )
        draft = self._create_calendar_draft(
            thread_id=thread_id,
            title=title,
            summary=summary,
            source_run_id=source_run_id,
            payload={
                "structuredPlan": structured_plan,
                "runtimeRunId": source_run_id,
                "goal": proposal_input.get("goal") or payload.message,
                "threadContextSummary": thread_context,
                "tasks": proposal_output.get("tasks") if isinstance(proposal_output.get("tasks"), list) else [],
                "sources": proposal_output.get("sources") if isinstance(proposal_output.get("sources"), list) else [],
                "mode": proposal_output.get("mode") or "local_fallback",
                "fallbackReason": proposal_output.get("fallbackReason"),
                "errorType": proposal_output.get("errorType"),
                "baseUrlHost": proposal_output.get("baseUrlHost"),
                "planHorizon": plan_horizon,
                "qualityReport": quality_report,
                "qualityStatus": proposal_output.get("qualityStatus"),
                "sourceType": proposal_output.get("sourceType"),
                "localRelevance": proposal_output.get("localRelevance"),
                "summary": summary,
            },
        )
        self.add_message(thread_id, "card", summary, kind="summary", payload={"draftId": draft.id, "text": summary})
        yield _ndjson({"type": "draft_created", "draftId": draft.id, "kind": draft.kind, "version": draft.version})
        yield _ndjson({"type": "summary", "text": summary, "draftId": draft.id})
        if auto_detail:
            yield from self._stream_plan_detail(thread_id)

    def _create_calendar_draft(
        self,
        *,
        thread_id: str,
        title: str,
        summary: str,
        payload: dict[str, Any],
        source_run_id: str,
    ) -> CommandDraftOut:
        draft_id = str(uuid4())
        now = _now()
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(MAX(version), 0) + 1 AS next_version
                FROM command_drafts
                WHERE thread_id = ? AND kind = 'calendar_plan'
                """,
                (thread_id,),
            ).fetchone()
            version = int(row["next_version"] or 1)
            conn.execute(
                """
                UPDATE command_drafts
                SET status = 'superseded', updated_at = ?
                WHERE thread_id = ? AND kind = 'calendar_plan' AND status = 'current'
                """,
                (now, thread_id),
            )
            conn.execute(
                """
                INSERT INTO command_drafts(
                  id, thread_id, kind, version, status, title, summary, payload_json,
                  source_run_id, created_at, updated_at
                )
                VALUES (?, ?, 'calendar_plan', ?, 'current', ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft_id,
                    thread_id,
                    version,
                    title[:200],
                    summary[:4000],
                    json.dumps(payload, ensure_ascii=False),
                    source_run_id,
                    now,
                    now,
                ),
            )
            conn.execute("UPDATE command_threads SET updated_at = ? WHERE id = ?", (now, thread_id))
            draft_row = conn.execute("SELECT * FROM command_drafts WHERE id = ?", (draft_id,)).fetchone()
        draft = _row_to_draft(draft_row)
        if draft is None:
            raise RuntimeError("Failed to create command draft")
        return draft

    def _calendar_items_from_draft(self, draft: CommandDraftOut) -> list[dict[str, Any]]:
        structured_plan = draft.payload.get("structuredPlan")
        if not _valid_structured_plan(structured_plan):
            return []
        refinements = draft.payload.get("refinements")
        if not isinstance(refinements, dict):
            refinements = {}
        items: list[dict[str, Any]] = []
        sequence = 0
        for milestone_index, milestone in enumerate(structured_plan.get("milestones") or []):
            if not _is_record(milestone):
                continue
            for task_index, task in enumerate(milestone.get("tasks") or []):
                if not _is_record(task):
                    continue
                title = str(task.get("title") or "").strip()
                if not title:
                    continue
                target_date = _normalize_task_date(task.get("dueDate"), _today())
                task_key = _task_key(milestone_index, task_index)
                source_key = f"command-draft:{draft.id}:m{milestone_index}:t{task_index}"
                item = {
                    "title": title,
                    "date": target_date,
                    "time": _default_task_time(sequence),
                    "estimatedMinutes": _task_minutes(task.get("estimatedMinutes")),
                    "priority": _task_priority(task.get("priority")),
                    "sourceKey": source_key,
                    "taskKey": task_key,
                    "milestoneTitle": str(milestone.get("title") or ""),
                    "description": str(task.get("description") or ""),
                }
                refined_task = refinements.get(task_key)
                if isinstance(refined_task, dict):
                    item["refinedTask"] = refined_task
                items.append(item)
                sequence += 1
        return items

    def _create_calendar_action(self, thread_id: str, draft: CommandDraftOut, items: list[dict[str, Any]]) -> str:
        action_id = str(uuid4())
        now = _now()
        payload = {"draftId": draft.id, "plans": items}
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO command_actions(
                  id, thread_id, draft_id, target, operation, risk, status, reason,
                  payload_json, result_json, error_message, created_at, updated_at
                )
                VALUES (?, ?, ?, 'calendar', 'create_or_update_plans', 'write', 'proposed', ?, ?, '{}', '', ?, ?)
                """,
                (
                    action_id,
                    thread_id,
                    draft.id,
                    f"Write {len(items)} draft tasks to Calendar",
                    json.dumps(payload, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            conn.execute("UPDATE command_threads SET updated_at = ? WHERE id = ?", (now, thread_id))
        return action_id

    def _create_calendar_patch_action(
        self,
        thread_id: str,
        operation: str,
        before: dict[str, Any],
        after: dict[str, Any],
        changes: dict[str, Any],
    ) -> str:
        action_id = str(uuid4())
        anchor_draft_id = str(uuid4())
        now = _now()
        risk = "delete" if operation == "delete" else "write"
        payload = {
            "planId": before.get("id"),
            "operation": operation,
            "before": before,
            "after": after,
            "changes": changes,
        }
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO command_drafts(
                  id, thread_id, kind, version, status, title, summary,
                  payload_json, source_run_id, created_at, updated_at
                )
                VALUES (?, ?, 'calendar_plan', 0, 'dismissed', ?, ?, ?, '', ?, ?)
                """,
                (
                    anchor_draft_id,
                    thread_id,
                    "Calendar patch action",
                    f"{operation} calendar plan",
                    json.dumps({"kind": "calendar_patch_anchor", "planId": before.get("id")}, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO command_actions(
                  id, thread_id, draft_id, target, operation, risk, status, reason,
                  payload_json, result_json, error_message, created_at, updated_at
                )
                VALUES (?, ?, ?, 'calendar', ?, ?, 'proposed', ?, ?, '{}', '', ?, ?)
                """,
                (
                    action_id,
                    thread_id,
                    anchor_draft_id,
                    operation,
                    risk,
                    f"{operation} calendar plan {before.get('id') or ''}",
                    json.dumps(payload, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            conn.execute("UPDATE command_threads SET updated_at = ? WHERE id = ?", (now, thread_id))
        return action_id

    def _load_action(self, action_id: str):
        with get_conn() as conn:
            return conn.execute("SELECT * FROM command_actions WHERE id = ?", (action_id,)).fetchone()

    def _update_action(
        self,
        action_id: str,
        *,
        status: str,
        result: dict[str, Any] | None = None,
        error: str = "",
    ) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE command_actions
                SET status = ?,
                    result_json = COALESCE(?, result_json),
                    error_message = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    json.dumps(result, ensure_ascii=False) if result is not None else None,
                    error,
                    _now(),
                    action_id,
                ),
            )

    def _record_approval(self, thread_id: str, action_id: str, permission: CommandPermission, decision: str) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO command_approvals(id, thread_id, action_id, permission, decision, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (str(uuid4()), thread_id, action_id, permission, decision, _now()),
            )

    def _execute_calendar_patch_action(self, action_id: str, action) -> dict[str, Any]:
        self._update_action(action_id, status="running")
        payload = _json_object(action["payload_json"])
        operation = str(payload.get("operation") or action["operation"])
        plan_id = str(payload.get("planId") or "")
        before = payload.get("before") if _is_record(payload.get("before")) else {}
        after = payload.get("after") if _is_record(payload.get("after")) else {}
        changes = payload.get("changes") if _is_record(payload.get("changes")) else {}
        try:
            if operation == "delete":
                delete_plan(plan_id)
                result = {
                    "actionId": action_id,
                    "operation": "delete",
                    "status": "success",
                    "before": before,
                    "after": None,
                    "changes": {},
                }
            else:
                safe_changes: dict[str, Any] = {}
                for key in ("date", "time", "content", "estimatedMinutes"):
                    if key in changes:
                        safe_changes[key] = changes[key]
                if not safe_changes:
                    raise ValueError("no supported plan changes")
                updated = update_plan(plan_id, PlanUpdate(**safe_changes))
                result = {
                    "actionId": action_id,
                    "operation": "update",
                    "status": "success",
                    "before": before,
                    "after": {
                        "id": updated.id,
                        "date": updated.date,
                        "time": updated.time,
                        "title": updated.content,
                        "done": updated.done,
                        "completion": updated.result,
                        "priority": updated.priority,
                        "estimatedMinutes": updated.estimated_minutes,
                        "source": updated.source,
                        "sourceKey": updated.source_key,
                        "createdAt": updated.created_at,
                        "updatedAt": updated.updated_at,
                    },
                    "changes": safe_changes,
                }
            self._update_action(action_id, status="success", result=result)
            return result
        except Exception as exc:
            result = {
                "actionId": action_id,
                "operation": operation,
                "status": "failed",
                "before": before,
                "after": after,
                "changes": changes,
                "error": str(exc),
            }
            self._update_action(action_id, status="failed", result=result, error=str(exc))
            return result

    def _execute_calendar_action(self, action_id: str) -> dict[str, Any]:
        action = self._load_action(action_id)
        if not action:
            return {"created": 0, "updated": 0, "failed": 1, "affectedDates": [], "errors": ["action not found"], "plans": []}
        if action["operation"] in {"update", "delete"}:
            return self._execute_calendar_patch_action(action_id, action)
        self._update_action(action_id, status="running")
        payload = _json_object(action["payload_json"])
        items = payload.get("plans") if isinstance(payload.get("plans"), list) else []
        created = 0
        updated = 0
        failed = 0
        affected_dates: set[str] = set()
        errors: list[str] = []
        written_plans: list[dict[str, Any]] = []
        for item in items:
            if not _is_record(item):
                continue
            try:
                state, plan = self._upsert_calendar_plan(item)
                if state == "created":
                    created += 1
                else:
                    updated += 1
                affected_dates.add(str(item.get("date") or ""))
                written_plans.append({
                    "id": plan.id,
                    "date": plan.date,
                    "time": plan.time,
                    "title": plan.content,
                    "sourceKey": plan.source_key,
                    "state": state,
                })
            except Exception as exc:
                failed += 1
                errors.append(str(exc))
        result = {
            "actionId": action_id,
            "created": created,
            "updated": updated,
            "failed": failed,
            "affectedDates": sorted(date for date in affected_dates if date),
            "errors": errors,
            "plans": written_plans,
        }
        self._update_action(action_id, status="success" if failed == 0 else "failed", result=result, error="; ".join(errors))
        return result

    def _upsert_calendar_plan(self, item: dict[str, Any]):
        title = str(item.get("title") or "").strip()
        if not title:
            raise ValueError("plan title is empty")
        date = _normalize_task_date(item.get("date"), _today())
        time = str(item.get("time") or "09:00")
        source_key = str(item.get("sourceKey") or "").strip()
        description = str(item.get("description") or "").strip()
        priority = _task_priority(item.get("priority"))
        estimated_minutes = _task_minutes(item.get("estimatedMinutes"))
        row_data: dict[str, Any] | None = None
        with get_conn() as conn:
            row = None
            if source_key:
                row = conn.execute("SELECT * FROM plans WHERE source_key = ? LIMIT 1", (source_key,)).fetchone()
            if not row:
                row = conn.execute(
                    """
                    SELECT * FROM plans
                    WHERE date = ? AND content = ? AND source = 'ai'
                    ORDER BY created_at ASC
                    LIMIT 1
                    """,
                    (date, title),
                ).fetchone()
            if row:
                if row["source"] != "ai":
                    row = None
            if row:
                row_data = dict(row)
        if row_data:
            updates: dict[str, Any] = {}
            if source_key and row_data["source_key"] != source_key:
                updates["sourceKey"] = source_key
            if description and not str(row_data["result"] or "").strip():
                updates["result"] = description
            if row_data["priority"] != priority:
                updates["priority"] = priority
            if int(row_data["estimated_minutes"] or 0) != estimated_minutes:
                updates["estimatedMinutes"] = estimated_minutes
            plan = update_plan(row_data["id"], PlanUpdate(**updates))
            refined_task = _refined_task_from_payload(item.get("refinedTask"))
            if refined_task:
                plan = save_plan_refined_task(plan.id, PlanRefinedTaskUpdate(refinedTask=refined_task))
            return "updated", plan
        refined_task = _refined_task_from_payload(item.get("refinedTask"))
        plan = create_plan(
            PlanCreate(
                date=date,
                time=time,
                content=title,
                done=False,
                result=description,
                priority=priority,
                estimatedMinutes=estimated_minutes,
                source="ai",
                sourceKey=source_key,
                refinedTask=refined_task,
            )
        )
        return "created", plan

    def _llm_chat(self, payload: CommandChatRequest, *, thread_id: str = "", exclude_message_id: str = "") -> str:
        thread_context = self._thread_context_summary(thread_id, exclude_message_id=exclude_message_id) if thread_id else ""
        system = (
            "You are Planix P Mode in Phase 4.4. Reply in the user's language. "
            "Normal chat is allowed. Calendar writes are handled only by explicit draft commands and PermissionGate. "
            "Do not claim to write Notes, Materials, Goals, Settings, or any data outside Calendar plans."
        )
        user = (
            "Current thread context, if any:\n"
            f"{thread_context or '(none)'}\n\n"
            "User message:\n"
            f"{payload.message}\n\n"
            "Answer conversationally and concisely. If the user asks for unsupported execution, explain the current P Mode boundary."
        )
        result, _error = LlmClient().complete(
            "command_chat",
            system,
            user,
            max_tokens=700,
            temperature=0.3,
            timeout_seconds=30,
        )
        if result and result.content.strip():
            return result.content.strip()
        return _fallback_reply(payload.message)
