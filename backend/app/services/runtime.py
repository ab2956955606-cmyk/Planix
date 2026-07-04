from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as date_type
import json
import re
import time
from typing import Any, Iterator
from uuid import uuid4

from ..db import get_conn, load_memory
from ..schemas import AgentRunRequest, GoalPlanRequest, StructuredGoalPlan
from .plans import list_plans
from .planning import PlanningService
from .rag import RagService
from .structured_goal_plan import build_local_structured_plan, derive_planner_tasks, render_goal_plan_markdown


NodeType = str
NodeStatus = str


@dataclass(frozen=True)
class RuntimeStep:
    id: str
    node_type: NodeType
    title: str
    content: str = ""
    tool_name: str = ""
    tool_input: dict[str, object] | None = None


@dataclass
class RuntimePreferenceMemory:
    learning_style: str = "项目驱动"
    daily_available_minutes: int = 120
    planning_style: str = "具体可执行"
    output_language: str = "zh"
    difficulty_preference: str = "practical"
    career_direction: str = ""
    project_preference: str = ""
    raw_preference_text: str = ""

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "learningStyle": self.learning_style,
            "dailyAvailableMinutes": self.daily_available_minutes,
            "planningStyle": self.planning_style,
            "outputLanguage": self.output_language,
            "difficultyPreference": self.difficulty_preference,
        }
        if self.career_direction:
            result["careerDirection"] = self.career_direction
        if self.project_preference:
            result["projectPreference"] = self.project_preference
        if self.raw_preference_text:
            result["rawPreferenceText"] = self.raw_preference_text
        return result


@dataclass
class RuntimeRecentProgress:
    title: str
    summary: str
    relevance_to_goal: str = "low"

    def to_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "summary": self.summary,
            "relevanceToGoal": self.relevance_to_goal,
        }


@dataclass
class RuntimeHistoryMemory:
    long_term_goals: list[str] = field(default_factory=list)
    active_projects: list[str] = field(default_factory=list)
    recent_progress: list[RuntimeRecentProgress | str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "longTermGoals": self.long_term_goals,
            "activeProjects": self.active_projects,
            "recentProgress": [
                item.to_dict() if isinstance(item, RuntimeRecentProgress) else _recent_progress_from_text("", str(item)).to_dict()
                for item in self.recent_progress
            ],
            "constraints": self.constraints,
        }


@dataclass
class RuntimeContextPack:
    goal: str
    date: str
    explicit_constraints: list[str]
    preference_memory: RuntimePreferenceMemory
    history_memory: RuntimeHistoryMemory
    today_plans: list[dict[str, object]]
    materials: list[dict[str, object]]
    output_language: str
    raw_materials: str
    payload_data: dict[str, Any]

    def memory_output(self) -> dict[str, object]:
        return {
            "preferenceMemory": self.preference_memory.to_dict(),
            "historyMemory": self.history_memory.to_dict(),
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "goal": self.goal,
            "explicitConstraints": self.explicit_constraints,
            "preferenceMemory": self.preference_memory.to_dict(),
            "historyMemory": self.history_memory.to_dict(),
            "todayPlans": self.today_plans,
            "materials": self.materials,
            "outputLanguage": self.output_language,
        }


class AgentRunRepository:
    def create_run(self, user_input: str) -> str:
        run_id = str(uuid4())
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO agent_runs(id, input, status)
                VALUES (?, ?, 'running')
                """,
                (run_id, user_input[:4000]),
            )
        return run_id

    def record_event(self, run_id: str, event: dict[str, object]) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO agent_events(id, run_id, sequence, event_type, node_id, payload)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    run_id,
                    int(event.get("sequence") or 0),
                    str(event.get("type") or ""),
                    str(event.get("nodeId") or ""),
                    json.dumps(event, ensure_ascii=False),
                ),
            )

    def finish_run(self, run_id: str, status: str, output_summary: str = "", error: str = "") -> None:
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE agent_runs
                SET status = ?, output_summary = ?, error = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, output_summary[:4000], error[:1000], run_id),
            )

    def recent_summaries(self, limit: int = 3) -> list[str]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT output_summary
                FROM agent_runs
                WHERE output_summary != ''
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [str(row["output_summary"]) for row in rows]


class StreamEngine:
    def __init__(self, run_id: str, repository: AgentRunRepository):
        self.run_id = run_id
        self.repository = repository
        self.sequence = 0

    def make_event(self, event_type: str, **payload: object) -> dict[str, object]:
        self.sequence += 1
        event: dict[str, object] = {
            "runId": self.run_id,
            "sequence": self.sequence,
            "type": event_type,
            **payload,
        }
        self.repository.record_event(self.run_id, event)
        return event

    def encode(self, event: dict[str, object]) -> str:
        return json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"


class MemorySystem:
    def __init__(self, repository: AgentRunRepository):
        self.repository = repository

    def get_context(self, payload: AgentRunRequest) -> RuntimeContextPack:
        saved_preferences = load_memory()
        preference_memory = _merge_preference_memory(payload.preferences, saved_preferences)
        output_language = str(preference_memory.output_language or "zh")
        explicit_constraints = _extract_constraints(" ".join([payload.input, payload.preferences]))
        history_memory = _build_history_memory(
            goal=payload.input,
            payload_preferences=payload.preferences,
            saved_preferences=saved_preferences,
            recent_runs=self.repository.recent_summaries(),
            explicit_constraints=explicit_constraints,
        )
        return RuntimeContextPack(
            goal=payload.input.strip() or "Planix agent task",
            date=payload.date,
            explicit_constraints=explicit_constraints,
            preference_memory=preference_memory,
            history_memory=history_memory,
            today_plans=[],
            materials=[],
            output_language=output_language if output_language in {"zh", "en"} else "zh",
            raw_materials=payload.materials[:3000],
            payload_data=payload.data,
        )


class RuntimePlanner:
    def plan(self, payload: AgentRunRequest, context: RuntimeContextPack) -> list[RuntimeStep]:
        focus = payload.input.strip() or "Planix agent task"
        plan_content = (
            f"Plan for: {focus}\n"
            "1. Read preference memory and history memory as separate context layers.\n"
            "2. Read today's plans, then retrieve local materials with the context pack.\n"
            "3. Generate a structured planning preview without writing user data."
        )
        return [
            RuntimeStep(id="plan", node_type="reasoning", title="Execution Plan", content=plan_content),
            RuntimeStep(
                id="tool-memory",
                node_type="tool",
                title="get_memory",
                tool_name="get_memory",
                tool_input={"date": payload.date},
            ),
            RuntimeStep(
                id="tool-plans",
                node_type="tool",
                title="get_today_plans",
                tool_name="get_today_plans",
                tool_input={"date": payload.date},
            ),
            RuntimeStep(
                id="tool-materials",
                node_type="tool",
                title="search_materials",
                tool_name="search_materials",
                tool_input={"query": build_material_search_query(context), "topK": 3},
            ),
            RuntimeStep(
                id="tool-propose",
                node_type="tool",
                title="propose_tasks",
                tool_name="propose_tasks",
                tool_input={"goal": payload.input, "date": payload.date},
            ),
        ]


class ToolRouter:
    allowed_tools = {"search_materials", "get_today_plans", "get_memory", "propose_tasks"}

    def route(self, step: RuntimeStep) -> dict[str, object] | None:
        if not step.tool_name or step.tool_name not in self.allowed_tools:
            return None
        return {
            "name": step.tool_name,
            "input": step.tool_input or {},
            "writeMode": "preview" if step.tool_name == "propose_tasks" else "readonly",
        }


class RuntimeToolExecutor:
    def __init__(self):
        self.rag = RagService()
        self.planning = PlanningService()

    def execute(self, tool_call: dict[str, object], context: RuntimeContextPack) -> object:
        name = str(tool_call["name"])
        tool_input = tool_call.get("input")
        params = tool_input if isinstance(tool_input, dict) else {}
        if name == "get_memory":
            tool_call["input"] = {"date": context.date}
            return context.memory_output()
        if name == "get_today_plans":
            context.today_plans = _today_plans_from_context(context)
            tool_call["input"] = {"date": context.date}
            return context.today_plans
        if name == "search_materials":
            limit = _int_param(params.get("topK"), 3, minimum=1, maximum=8)
            query = build_material_search_query(context)
            context.materials = [source.model_dump(by_alias=True) for source in self.rag.retrieve(query, limit=limit)]
            tool_call["input"] = {"query": query, "topK": limit}
            return context.materials
        if name == "propose_tasks":
            summary = build_memory_context_summary(
                context.goal,
                context.preference_memory,
                context.history_memory,
                context.today_plans,
            )
            daily_hours = max(context.preference_memory.daily_available_minutes, 30) / 60
            plan = self.planning.create_goal_plan(
                GoalPlanRequest(
                    goal=context.goal,
                    date=context.date,
                    dailyHours=daily_hours,
                    materials=_planning_materials(context),
                    preferences=_planning_preferences(context, summary),
                    outputLanguage="zh-CN" if context.output_language == "zh" else "en-US",
                )
            )
            structured_plan = plan.structured_plan or build_local_structured_plan(
                context.goal,
                date=context.date,
                daily_hours=daily_hours,
                source_count=len(context.materials),
            )
            tasks = [task.model_dump(by_alias=True) for task in plan.tasks] or [
                task.model_dump(by_alias=True) for task in derive_planner_tasks(structured_plan)
            ]
            sources = [source.model_dump(by_alias=True) for source in plan.sources] or context.materials
            tool_call["input"] = {
                "goal": context.goal,
                "date": context.date,
                "memoryContextSummary": summary,
                "outputLanguage": context.output_language,
            }
            return {
                "notice": "Preview only; no user data was modified.",
                "mode": "llm" if plan.mode == "llm" else "local_fallback",
                "structuredPlan": structured_plan.model_dump(by_alias=True),
                "tasks": tasks,
                "sources": sources,
                "memoryContextSummary": summary,
                "fallbackReason": _runtime_fallback_reason(plan.fallback_reason),
                "errorType": plan.error_type,
                "baseUrlHost": plan.base_url_host,
            }
        return {"error": f"Tool {name} is not available."}


class RuntimeOrchestrator:
    def __init__(self):
        self.repository = AgentRunRepository()
        self.memory_system = MemorySystem(self.repository)
        self.planner = RuntimePlanner()
        self.router = ToolRouter()
        self.tool_executor = RuntimeToolExecutor()

    def run(self, payload: AgentRunRequest) -> Iterator[str]:
        run_id = self.repository.create_run(payload.input)
        stream = StreamEngine(run_id, self.repository)
        final_output = ""
        try:
            context = self.memory_system.get_context(payload)
            steps = self.planner.plan(payload, context)

            yield stream.encode(
                stream.make_event(
                    "node",
                    nodeId="input",
                    nodeType="input",
                    title="Input",
                    content=payload.input,
                    status="done",
                )
            )

            plan_step = steps[0]
            yield stream.encode(
                stream.make_event(
                    "node",
                    nodeId=plan_step.id,
                    nodeType=plan_step.node_type,
                    title=plan_step.title,
                    content="",
                    status="running",
                )
            )
            yield stream.encode(stream.make_event("delta", nodeId=plan_step.id, delta=plan_step.content))
            yield stream.encode(stream.make_event("status", nodeId=plan_step.id, status="done"))

            tool_outputs: list[dict[str, object]] = []
            for step in steps[1:]:
                routed = self.router.route(step)
                if not routed:
                    continue
                yield stream.encode(
                    stream.make_event(
                        "node",
                        nodeId=step.id,
                        nodeType="tool",
                        title=step.title,
                        content="",
                        status="running",
                    )
                )
                start = time.perf_counter()
                output = self.tool_executor.execute(routed, context)
                latency_ms = max(1, int((time.perf_counter() - start) * 1000))
                tool_call = {
                    **routed,
                    "output": output,
                    "latencyMs": latency_ms,
                }
                tool_outputs.append(tool_call)
                yield stream.encode(
                    stream.make_event(
                        "tool",
                        nodeId=step.id,
                        nodeType="tool",
                        title=step.title,
                        status="done",
                        toolCall=tool_call,
                    )
                )
                yield stream.encode(stream.make_event("status", nodeId=step.id, status="done"))

            observation = self._observation(tool_outputs)
            yield stream.encode(
                stream.make_event(
                    "node",
                    nodeId="observation",
                    nodeType="observation",
                    title="Observation",
                    content="",
                    status="running",
                )
            )
            yield stream.encode(stream.make_event("delta", nodeId="observation", delta=observation))
            yield stream.encode(stream.make_event("status", nodeId="observation", status="done"))

            yield stream.encode(
                stream.make_event(
                    "node",
                    nodeId="output",
                    nodeType="output",
                    title="Output",
                    content="",
                    status="running",
                )
            )
            for chunk in self._stream_output(payload, tool_outputs):
                final_output += chunk
                yield stream.encode(stream.make_event("delta", nodeId="output", delta=chunk))
            yield stream.encode(stream.make_event("status", nodeId="output", status="done"))
            yield stream.encode(stream.make_event("final", nodeId="output", content=final_output))
            self.repository.finish_run(run_id, "done", output_summary=final_output)
        except Exception as exc:
            message = f"Runtime failed: {exc}"
            yield stream.encode(stream.make_event("error", nodeId="output", error=message, status="error"))
            self.repository.finish_run(run_id, "error", output_summary=final_output, error=message)

    def _stream_output(
        self,
        payload: AgentRunRequest,
        tool_outputs: list[dict[str, object]],
    ) -> Iterator[str]:
        proposal = _proposal_from_tool_outputs(tool_outputs)
        if proposal:
            try:
                structured_plan = StructuredGoalPlan.model_validate(proposal["structuredPlan"])
            except (KeyError, ValueError, TypeError):
                structured_plan = build_local_structured_plan(payload.input, date=payload.date)
            sources = proposal.get("sources")
            source_items = sources if isinstance(sources, list) else _sources_from_tool_outputs(tool_outputs)
            today_plan_count = len(_tool_output_list(tool_outputs, "get_today_plans"))
            rendered = render_goal_plan_markdown(
                structured_plan,
                source_items,
                local_template=proposal.get("mode") == "local_fallback",
                today_plan_count=today_plan_count,
            )
            for chunk in _chunk_text(rendered):
                yield chunk
            return

        rendered = render_goal_plan_markdown(
            build_local_structured_plan(payload.input, date=payload.date),
            _sources_from_tool_outputs(tool_outputs),
            local_template=True,
            today_plan_count=len(_tool_output_list(tool_outputs, "get_today_plans")),
        )
        for chunk in _chunk_text(rendered):
            yield chunk

    def _observation(self, tool_outputs: list[dict[str, object]]) -> str:
        readonly = len([item for item in tool_outputs if item.get("writeMode") == "readonly"])
        preview = len([item for item in tool_outputs if item.get("writeMode") == "preview"])
        source_count = len(_sources_from_tool_outputs(tool_outputs))
        return (
            f"Executed {readonly} read-only tool(s) and {preview} preview tool(s). "
            f"Retrieved {source_count} material source(s). No user data was modified."
        )


def build_memory_context_summary(
    goal: str,
    preference_memory: RuntimePreferenceMemory,
    history_memory: RuntimeHistoryMemory,
    today_plans: list[dict[str, object]],
) -> str:
    parts = [
        (
            f"偏好：{preference_memory.learning_style}，每天约 "
            f"{preference_memory.daily_available_minutes} 分钟，计划风格为 {preference_memory.planning_style}，"
            f"输出语言 {preference_memory.output_language}。"
        )
    ]
    if preference_memory.career_direction:
        parts.append(f"职业方向：{preference_memory.career_direction}。")
    if preference_memory.project_preference:
        parts.append(f"项目偏好：{preference_memory.project_preference}。")
    if history_memory.long_term_goals:
        parts.append(f"长期目标：{'；'.join(history_memory.long_term_goals[:3])}。")
    if history_memory.active_projects:
        parts.append(f"活跃项目：{'；'.join(history_memory.active_projects[:3])}。")
    if history_memory.recent_progress:
        relevant = [
            _ensure_recent_progress_item(item, goal)
            for item in history_memory.recent_progress
        ]
        high_items = [item.title for item in relevant if item.relevance_to_goal == "high"]
        medium_items = [item.title for item in relevant if item.relevance_to_goal == "medium"]
        if high_items:
            parts.append(f"相关历史：{'；'.join(high_items[:2])}。")
        elif medium_items:
            parts.append("近期有同类学习记录，可参考分阶段练习方式。")
        else:
            parts.append("近期历史与当前目标相关性较低。")
    if history_memory.constraints:
        parts.append(f"约束：{'；'.join(history_memory.constraints[:3])}。")
    parts.append(f"今日已有 {len(today_plans)} 项计划。")
    return _truncate_text("".join(parts), 500)


def _merge_preference_memory(payload_preferences: str, saved_preferences: str) -> RuntimePreferenceMemory:
    merged: dict[str, object] = {
        "learningStyle": "项目驱动",
        "dailyAvailableMinutes": 120,
        "planningStyle": "具体可执行",
        "outputLanguage": "zh",
        "difficultyPreference": "practical",
    }
    for source in (_extract_preference_fields(saved_preferences), _extract_preference_fields(payload_preferences)):
        for key, value in source.items():
            if value in (None, ""):
                continue
            merged[key] = value

    daily_minutes = _int_param(merged.get("dailyAvailableMinutes"), 120, minimum=15, maximum=1440)
    output_language = str(merged.get("outputLanguage") or "zh")
    if output_language not in {"zh", "en"}:
        output_language = "zh"
    difficulty = str(merged.get("difficultyPreference") or "practical")
    if difficulty not in {"beginner", "practical", "advanced"}:
        difficulty = "practical"
    return RuntimePreferenceMemory(
        learning_style=str(merged.get("learningStyle") or "项目驱动"),
        daily_available_minutes=daily_minutes,
        planning_style=str(merged.get("planningStyle") or "具体可执行"),
        output_language=output_language,
        difficulty_preference=difficulty,
        career_direction=str(merged.get("careerDirection") or ""),
        project_preference=str(merged.get("projectPreference") or ""),
        raw_preference_text=str(merged.get("rawPreferenceText") or ""),
    )


def _extract_preference_fields(raw_text: str) -> dict[str, object]:
    text = (raw_text or "").strip()
    if not text:
        return {}
    parsed = _json_dict(text)
    if parsed:
        source = parsed.get("preferenceMemory") if isinstance(parsed.get("preferenceMemory"), dict) else parsed
        return _preference_fields_from_dict(source if isinstance(source, dict) else {})
    return _preference_fields_from_text(text)


def _preference_fields_from_dict(raw: dict[str, Any]) -> dict[str, object]:
    result: dict[str, object] = {}
    mapping = {
        "learningStyle": "learningStyle",
        "learning_style": "learningStyle",
        "dailyAvailableMinutes": "dailyAvailableMinutes",
        "daily_available_minutes": "dailyAvailableMinutes",
        "dailyMinutes": "dailyAvailableMinutes",
        "planningStyle": "planningStyle",
        "planning_style": "planningStyle",
        "outputLanguage": "outputLanguage",
        "output_language": "outputLanguage",
        "difficultyPreference": "difficultyPreference",
        "difficulty_preference": "difficultyPreference",
        "careerDirection": "careerDirection",
        "career_direction": "careerDirection",
        "projectPreference": "projectPreference",
        "project_preference": "projectPreference",
        "rawPreferenceText": "rawPreferenceText",
        "raw_preference_text": "rawPreferenceText",
    }
    for old_key, new_key in mapping.items():
        if old_key not in raw:
            continue
        value = raw.get(old_key)
        if new_key == "dailyAvailableMinutes":
            value = _minutes_from_value(value)
        if new_key == "outputLanguage":
            value = _normalize_output_language(value)
        if value not in (None, ""):
            result[new_key] = value
    return result


def _preference_fields_from_text(text: str) -> dict[str, object]:
    result: dict[str, object] = {"rawPreferenceText": text}
    minutes = _minutes_from_text(text)
    if minutes:
        result["dailyAvailableMinutes"] = minutes
    lower = text.lower()
    if "项目" in text or "project" in lower:
        result["learningStyle"] = "项目驱动"
    elif "课程" in text or "course" in lower:
        result["learningStyle"] = "课程驱动"
    elif "刷题" in text or "leetcode" in lower or "算法题" in text:
        result["learningStyle"] = "刷题驱动"
    if "强执行" in text:
        result["planningStyle"] = "强执行"
    elif "详细" in text or "detailed" in lower:
        result["planningStyle"] = "详细"
    elif "简洁" in text or "concise" in lower or "short" in lower:
        result["planningStyle"] = "简洁"
    if "英文" in text or "english" in lower:
        result["outputLanguage"] = "en"
    elif "中文" in text or "chinese" in lower:
        result["outputLanguage"] = "zh"
    if "入门" in text or "beginner" in lower:
        result["difficultyPreference"] = "beginner"
    elif "进阶" in text or "advanced" in lower:
        result["difficultyPreference"] = "advanced"
    return result


def _build_history_memory(
    *,
    goal: str,
    payload_preferences: str,
    saved_preferences: str,
    recent_runs: list[str],
    explicit_constraints: list[str],
) -> RuntimeHistoryMemory:
    merged = RuntimeHistoryMemory(
        recent_progress=[_recent_progress_from_text(goal, item) for item in recent_runs[:3]]
    )
    for raw_text in (saved_preferences, payload_preferences):
        parsed = _json_dict(raw_text)
        if not parsed:
            continue
        source = parsed.get("historyMemory") if isinstance(parsed.get("historyMemory"), dict) else parsed
        if not isinstance(source, dict):
            continue
        merged.long_term_goals.extend(_string_list(source.get("longTermGoals") or source.get("long_term_goals")))
        merged.active_projects.extend(_string_list(source.get("activeProjects") or source.get("active_projects")))
        merged.recent_progress.extend(
            _recent_progress_list(goal, source.get("recentProgress") or source.get("recent_progress"))
        )
        merged.constraints.extend(_string_list(source.get("constraints")))
    merged.constraints.extend(item for item in explicit_constraints if item not in merged.constraints)
    merged.long_term_goals = _dedupe(merged.long_term_goals)[:5]
    merged.active_projects = _dedupe(merged.active_projects)[:5]
    merged.recent_progress = _dedupe_recent_progress(merged.recent_progress)[:5]
    merged.constraints = _dedupe(merged.constraints)[:6]
    return merged


def _today_plans_from_context(context: RuntimeContextPack) -> list[dict[str, object]]:
    day = context.payload_data.get(context.date, {}) if isinstance(context.payload_data, dict) else {}
    frontend_plans = day.get("plans", []) if isinstance(day, dict) else []
    if isinstance(frontend_plans, list) and frontend_plans:
        return [dict(plan) for plan in frontend_plans if isinstance(plan, dict)]
    return [plan.model_dump(by_alias=True) for plan in list_plans(context.date)]


def build_material_search_query(context: RuntimeContextPack) -> str:
    preference = context.preference_memory
    history = context.history_memory
    recent = [_ensure_recent_progress_item(item, context.goal) for item in history.recent_progress]
    high_titles = [item.title for item in recent if item.relevance_to_goal == "high"]
    parts = [
        context.goal,
        *_goal_search_terms(context.goal),
        *context.explicit_constraints,
        preference.learning_style,
        preference.planning_style,
        preference.career_direction,
        preference.project_preference,
        preference.raw_preference_text,
        *history.long_term_goals,
        *history.active_projects,
        *high_titles,
        *history.constraints,
        _truncate_text(_clean_text(context.raw_materials), 80),
    ]
    return _truncate_by_priority(parts, 300, hard_limit=500)


def _recent_progress_list(goal: str, value: object) -> list[RuntimeRecentProgress]:
    if not isinstance(value, list):
        return []
    result: list[RuntimeRecentProgress] = []
    for item in value:
        if isinstance(item, dict):
            text = " ".join(
                str(item.get(key) or "")
                for key in ("title", "summary", "content", "output", "description")
            )
            title = str(item.get("title") or _extract_title(text)).strip()
            summary = str(item.get("summary") or _summarize_text(text)).strip()
            relevance = str(item.get("relevanceToGoal") or item.get("relevance_to_goal") or "").strip()
            if relevance not in {"high", "medium", "low"}:
                relevance = _relevance_to_goal(goal, title, summary)
            if title or summary:
                result.append(
                    RuntimeRecentProgress(
                        title=_truncate_text(title or summary, 48),
                        summary=_truncate_text(summary or title, 120),
                        relevance_to_goal=relevance,
                    )
                )
            continue
        text = str(item).strip()
        if text:
            result.append(_recent_progress_from_text(goal, text))
    return result


def _recent_progress_from_text(goal: str, text: str) -> RuntimeRecentProgress:
    title = _extract_title(text)
    summary = _summarize_text(text)
    return RuntimeRecentProgress(
        title=title,
        summary=summary,
        relevance_to_goal=_relevance_to_goal(goal, title, summary),
    )


def _ensure_recent_progress_item(item: RuntimeRecentProgress | str, goal: str) -> RuntimeRecentProgress:
    if isinstance(item, RuntimeRecentProgress):
        if item.relevance_to_goal in {"high", "medium", "low"}:
            return item
        return RuntimeRecentProgress(
            title=item.title,
            summary=item.summary,
            relevance_to_goal=_relevance_to_goal(goal, item.title, item.summary),
        )
    return _recent_progress_from_text(goal, str(item))


def _dedupe_recent_progress(items: list[RuntimeRecentProgress | str]) -> list[RuntimeRecentProgress]:
    seen: set[str] = set()
    result: list[RuntimeRecentProgress] = []
    for item in items:
        current = _ensure_recent_progress_item(item, "")
        key = f"{current.title}|{current.summary}"
        if key in seen:
            continue
        seen.add(key)
        result.append(current)
    return result


def _extract_title(text: str) -> str:
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            line = line.lstrip("#").strip()
        return _truncate_text(_clean_text(line), 48)
    return "历史记录"


def _summarize_text(text: str) -> str:
    cleaned = _clean_text(text)
    if not cleaned:
        return ""
    title = _extract_title(text)
    if cleaned.startswith(title):
        cleaned = cleaned[len(title):].strip(" ：:-")
    return _truncate_text(cleaned or title, 120)


def _clean_text(text: str) -> str:
    cleaned = re.sub(r"```.*?```", " ", str(text or ""), flags=re.S)
    cleaned = re.sub(r"[#>*_`\[\]{}()]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _truncate_text(text: str, limit: int) -> str:
    cleaned = _clean_text(text)
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 1)].rstrip() + "…"


def _relevance_to_goal(goal: str, title: str, summary: str) -> str:
    target = f"{title} {summary}".lower()
    direct_terms = [term.lower() for term in _goal_direct_terms(goal)]
    if any(term and term in target for term in direct_terms):
        return "high"
    goal_domain = _goal_domain(goal)
    target_domain = _goal_domain(target)
    if goal_domain and target_domain == goal_domain:
        return "medium"
    return "low"


def _goal_direct_terms(goal: str) -> list[str]:
    text = str(goal or "")
    lower = text.lower()
    terms = [item for item in re.findall(r"[a-zA-Z][a-zA-Z0-9_+-]{1,}", lower) if len(item) >= 2]
    domain_terms: list[str] = []
    if any(token in text for token in ("游泳", "蛙泳", "漂浮", "换气", "水性")):
        domain_terms.extend(["游泳", "蛙泳", "漂浮", "换气", "水性"])
    if any(token in text for token in ("滑雪", "雪板", "犁式", "平行转弯")):
        domain_terms.extend(["滑雪", "雪板", "犁式", "平行转弯"])
    if "python" in lower or "编程" in text:
        domain_terms.extend(["python", "编程"])
    if "ai" in lower or "人工智能" in text or "实习" in text:
        domain_terms.extend(["ai", "人工智能", "实习"])
    if not domain_terms and text.strip():
        domain_terms.append(_truncate_text(text, 24))
    return _dedupe([*domain_terms, *terms])


def _goal_search_terms(goal: str) -> list[str]:
    text = str(goal or "")
    lower = text.lower()
    if any(token in text for token in ("游泳", "蛙泳", "漂浮", "换气", "水性")):
        return ["游泳入门", "蛙泳", "漂浮", "换气", "水性练习"]
    if "python" in lower:
        return ["Python", "语法", "项目实战", "数据处理"]
    if "ai" in lower or "人工智能" in text or "实习" in text:
        return ["AI 应用", "实习准备", "项目作品集"]
    return []


def _goal_domain(text: str) -> str:
    value = str(text or "").lower()
    if any(token in value for token in ("游泳", "蛙泳", "漂浮", "换气", "水性", "滑雪", "雪板", "犁式", "平行转弯")):
        return "sport_skill"
    if any(token in value for token in ("python", "编程", "代码", "fastapi", "javascript", "react")):
        return "programming"
    if any(token in value for token in ("ai", "人工智能", "大模型", "实习", "rag", "agent")):
        return "career_ai"
    return ""


def _truncate_by_priority(parts: list[object], limit: int, *, hard_limit: int) -> str:
    tokens: list[str] = []
    seen: set[str] = set()
    for part in parts:
        cleaned = _clean_text(str(part or ""))
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        candidate = " ".join([*tokens, cleaned]).strip()
        if len(candidate) <= limit:
            tokens.append(cleaned)
            continue
        if not tokens:
            tokens.append(_truncate_text(cleaned, limit))
        break
    query = " ".join(tokens).strip()
    return _truncate_text(query, hard_limit)


def _planning_preferences(context: RuntimeContextPack, summary: str) -> str:
    return json.dumps(
        {
            "preferenceMemory": context.preference_memory.to_dict(),
            "historyMemory": context.history_memory.to_dict(),
            "explicitConstraints": context.explicit_constraints,
            "todayPlans": context.today_plans,
            "memoryContextSummary": summary,
            "priorityOrder": [
                "current user goal",
                "explicit constraints",
                "preferenceMemory",
                "todayPlans",
                "historyMemory",
                "RAG materials",
                "safe defaults",
            ],
        },
        ensure_ascii=False,
    )


def _planning_materials(context: RuntimeContextPack) -> str:
    return json.dumps(
        {
            "rawMaterials": context.raw_materials,
            "retrievedSources": context.materials,
            "contextPack": context.to_dict(),
        },
        ensure_ascii=False,
    )


def _runtime_fallback_reason(value: str | None) -> str | None:
    if value == "mock_provider":
        return "local_provider"
    return value


def _tool_output_list(tool_outputs: list[dict[str, object]], name: str) -> list[Any]:
    for item in tool_outputs:
        if item.get("name") != name:
            continue
        output = item.get("output")
        return output if isinstance(output, list) else []
    return []


def _sources_from_tool_outputs(tool_outputs: list[dict[str, object]]) -> list[dict[str, Any]]:
    sources = _tool_output_list(tool_outputs, "search_materials")
    return [source for source in sources if isinstance(source, dict)]


def _proposal_from_tool_outputs(tool_outputs: list[dict[str, object]]) -> dict[str, Any] | None:
    for item in tool_outputs:
        if item.get("name") != "propose_tasks":
            continue
        output = item.get("output")
        if isinstance(output, dict) and isinstance(output.get("structuredPlan"), dict):
            return output
    return None


def _chunk_text(text: str) -> Iterator[str]:
    lines = text.splitlines(keepends=True)
    for line in lines:
        yield line


def _json_dict(text: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(text or "")
    except (TypeError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _minutes_from_value(value: object) -> int | None:
    if isinstance(value, (int, float)):
        return max(15, min(int(value), 1440))
    return _minutes_from_text(str(value or ""))


def _minutes_from_text(text: str) -> int | None:
    normalized = text.strip().lower()
    if not normalized:
        return None
    hour_match = re.search(r"(\d+(?:\.\d+)?)\s*(小时|小時|hour|hours|h)(?:\b|$)", normalized)
    if hour_match:
        return max(15, min(int(float(hour_match.group(1)) * 60), 1440))
    minute_match = re.search(r"(\d+)\s*(分钟|分鐘|min|mins|minute|minutes)(?:\b|$)", normalized)
    if minute_match:
        return max(15, min(int(minute_match.group(1)), 1440))
    try:
        return max(15, min(int(float(normalized)), 1440))
    except ValueError:
        return None


def _normalize_output_language(value: object) -> str | None:
    normalized = str(value or "").strip().lower()
    if normalized in {"zh", "zh-cn", "chinese", "中文"}:
        return "zh"
    if normalized in {"en", "en-us", "english", "英文"}:
        return "en"
    return None


def _extract_constraints(text: str) -> list[str]:
    constraints: list[str] = []
    for part in re.split(r"[\n。.!?；;]", text or ""):
        cleaned = part.strip()
        if not cleaned:
            continue
        lower = cleaned.lower()
        if any(token in cleaned for token in ("必须", "不能", "不要", "最多", "至少", "截止", "每天", "预算")) or any(
            token in lower for token in ("must", "cannot", "deadline", "budget", "only", "at most", "at least")
        ):
            constraints.append(cleaned[:160])
    return _dedupe(constraints)[:6]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _int_param(value: object, default: int, *, minimum: int, maximum: int) -> int:
    try:
        parsed = int(float(str(value)))
    except (TypeError, ValueError):
        return default
    return max(minimum, min(parsed, maximum))
