import json
from datetime import date as date_type
from datetime import timedelta
from uuid import uuid4

from ..db import get_conn, load_memory
from ..errors import bad_request, not_found
from ..schemas import (
    DailyReviewOut,
    DailyReviewRequest,
    GoalPlanOut,
    GoalPlanRequest,
    PhaseItem,
    PlanCreate,
    PlanOut,
    PlannerTask,
    ReplanApplyRequest,
    ReplanTask,
)
from .llm import LlmClient
from .planner import _json_object
from .plans import create_plan, list_plans


def _parse_date(value: str) -> date_type:
    try:
        return date_type.fromisoformat(value)
    except ValueError as exc:
        raise bad_request("date must use YYYY-MM-DD format") from exc


def _next_day(value: str) -> str:
    return (_parse_date(value) + timedelta(days=1)).isoformat()


def _dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def _load_list(raw: str) -> list:
    try:
        value = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []


def _normalize_phase_items(items: object) -> list[PhaseItem]:
    if not isinstance(items, list):
        return []
    phases = []
    for item in items[:6]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        detail = str(item.get("detail") or "").strip()
        if title:
            phases.append(PhaseItem(title=title, detail=detail))
    return phases


def _normalize_planner_tasks(items: object) -> list[PlannerTask]:
    if not isinstance(items, list):
        return []
    tasks = []
    for item in items[:8]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("text") or "").strip()
        if not title:
            continue
        tasks.append(
            PlannerTask(
                time=str(item.get("time") or "09:00")[:5],
                title=title,
                reason=str(item.get("reason") or "支持当前目标的可执行任务。"),
            )
        )
    return tasks


def _normalize_suggestions(items: object) -> list[str]:
    if not isinstance(items, list):
        return []
    return [str(item).strip() for item in items[:6] if str(item).strip()]


def _normalize_replan_tasks(items: object, target_date: str) -> list[ReplanTask]:
    if not isinstance(items, list):
        return []
    tasks = []
    for item in items[:8]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("text") or "").strip()
        if not title:
            continue
        tasks.append(
            ReplanTask(
                targetDate=str(item.get("targetDate") or item.get("target_date") or target_date),
                time=str(item.get("time") or "09:00")[:5],
                title=title,
                reason=str(item.get("reason") or "根据未完成任务自动重排。"),
                sourcePlanId=item.get("sourcePlanId") or item.get("source_plan_id"),
            )
        )
    return tasks


def _plan_to_dict(plan: PlanOut) -> dict[str, object]:
    return plan.model_dump(by_alias=True)


class PlanningService:
    def create_goal_plan(self, payload: GoalPlanRequest) -> GoalPlanOut:
        _parse_date(payload.date)
        preferences = payload.preferences or load_memory()
        llm_result = LlmClient().complete(
            "planning_goal_plan",
            (
                "You are an AI planning agent. Return strict JSON only with keys "
                "summary, phases and tasks. phases is [{title, detail}], "
                "tasks is [{time, title, reason}] for the given date."
            ),
            _dump(
                {
                    "goal": payload.goal,
                    "deadline": payload.deadline,
                    "dailyHours": payload.daily_hours,
                    "materials": payload.materials[:3000],
                    "preferences": preferences,
                    "date": payload.date,
                }
            ),
        )

        mode = "mock"
        provider = None
        model = None
        parsed = _json_object(llm_result.content) if llm_result else None
        if parsed:
            mode = "llm"
            provider = llm_result.provider if llm_result else None
            model = llm_result.model if llm_result else None
            summary = str(parsed.get("summary") or f"已为“{payload.goal}”生成目标规划。")
            phases = _normalize_phase_items(parsed.get("phases"))
            tasks = _normalize_planner_tasks(parsed.get("tasks"))
        else:
            summary, phases, tasks = self._mock_goal_plan(payload)

        if not phases or not tasks:
            fallback_summary, fallback_phases, fallback_tasks = self._mock_goal_plan(payload)
            summary = summary or fallback_summary
            phases = phases or fallback_phases
            tasks = tasks or fallback_tasks

        plan_id = str(uuid4())
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO planning_goals(
                  id, goal, deadline, daily_hours, materials, preferences,
                  summary, phases_json, tasks_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan_id,
                    payload.goal,
                    payload.deadline,
                    payload.daily_hours,
                    payload.materials,
                    preferences,
                    summary,
                    _dump([phase.model_dump() for phase in phases]),
                    _dump([task.model_dump() for task in tasks]),
                ),
            )

        return GoalPlanOut(id=plan_id, mode=mode, summary=summary, phases=phases, tasks=tasks, provider=provider, model=model)

    def create_daily_review(self, payload: DailyReviewRequest) -> DailyReviewOut:
        review_date = _parse_date(payload.date).isoformat()
        target_date = _next_day(review_date)
        plans = self._plans_for_review(payload)
        done_count = len([plan for plan in plans if plan.get("done")])
        total_count = len(plans)
        unfinished = [plan for plan in plans if not plan.get("done")]
        llm_result = LlmClient().complete(
            "planning_daily_review",
            (
                "You are an AI daily review and replanning assistant. Return strict JSON only "
                "with keys summary, suggestions, replanTasks. replanTasks is "
                "[{targetDate, time, title, reason, sourcePlanId}] and should not modify data directly."
            ),
            _dump(
                {
                    "date": review_date,
                    "targetDate": target_date,
                    "goal": payload.goal,
                    "plans": plans,
                    "doneCount": done_count,
                    "totalCount": total_count,
                    "unfinished": unfinished,
                    "preferences": payload.preferences or load_memory(),
                }
            ),
        )

        mode = "mock"
        provider = None
        model = None
        parsed = _json_object(llm_result.content) if llm_result else None
        if parsed:
            mode = "llm"
            provider = llm_result.provider if llm_result else None
            model = llm_result.model if llm_result else None
            summary = str(parsed.get("summary") or f"今天完成 {done_count}/{total_count} 项。")
            suggestions = _normalize_suggestions(parsed.get("suggestions"))
            replan_tasks = _normalize_replan_tasks(parsed.get("replanTasks") or parsed.get("replan_tasks"), target_date)
        else:
            summary, suggestions, replan_tasks = self._mock_daily_review(done_count, total_count, unfinished, target_date)

        if not suggestions:
            suggestions = ["保留今日有效产出，把未完成任务拆成更小的下一步。"]

        review_id = str(uuid4())
        with get_conn() as conn:
            row = conn.execute(
                """
                INSERT INTO daily_reviews(
                  id, date, summary, suggestions, done_count, total_count,
                  suggestions_json, replan_tasks_json, target_date, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(date)
                DO UPDATE SET
                  summary = excluded.summary,
                  suggestions = excluded.suggestions,
                  done_count = excluded.done_count,
                  total_count = excluded.total_count,
                  suggestions_json = excluded.suggestions_json,
                  replan_tasks_json = excluded.replan_tasks_json,
                  target_date = excluded.target_date,
                  updated_at = CURRENT_TIMESTAMP
                RETURNING *
                """,
                (
                    review_id,
                    review_date,
                    summary,
                    _dump(suggestions),
                    done_count,
                    total_count,
                    _dump(suggestions),
                    _dump([task.model_dump(by_alias=True) for task in replan_tasks]),
                    target_date,
                ),
            ).fetchone()

        return self._row_to_daily_review(row, mode=mode, provider=provider, model=model)

    def get_daily_review(self, review_date: str) -> DailyReviewOut:
        normalized_date = _parse_date(review_date).isoformat()
        with get_conn() as conn:
            row = conn.execute("SELECT * FROM daily_reviews WHERE date = ?", (normalized_date,)).fetchone()
        if not row:
            raise not_found("daily review does not exist")
        return self._row_to_daily_review(row, mode="saved")

    def apply_replan(self, payload: ReplanApplyRequest) -> list[PlanOut]:
        created = []
        for task in payload.tasks:
            created.append(
                create_plan(
                    PlanCreate(
                        date=task.target_date,
                        time=task.time,
                        content=task.title,
                        result=task.reason,
                        priority="medium",
                        estimatedMinutes=45,
                        source="ai",
                    )
                )
            )
        return created

    def _plans_for_review(self, payload: DailyReviewRequest) -> list[dict[str, object]]:
        day = payload.data.get(payload.date, {}) if payload.data else {}
        frontend_plans = day.get("plans", []) if isinstance(day, dict) else []
        if frontend_plans:
            return [dict(plan) for plan in frontend_plans if isinstance(plan, dict)]
        return [_plan_to_dict(plan) for plan in list_plans(payload.date)]

    def _row_to_daily_review(self, row, mode: str, provider: str | None = None, model: str | None = None) -> DailyReviewOut:
        suggestions = _load_list(row["suggestions_json"] or row["suggestions"])
        replan_tasks = _normalize_replan_tasks(_load_list(row["replan_tasks_json"]), row["target_date"])
        return DailyReviewOut(
            id=row["id"],
            mode=mode,
            date=row["date"],
            summary=row["summary"],
            suggestions=[str(item) for item in suggestions],
            doneCount=row["done_count"],
            totalCount=row["total_count"],
            targetDate=row["target_date"],
            replanTasks=replan_tasks,
            provider=provider,
            model=model,
            updatedAt=row["updated_at"],
        )

    def _mock_goal_plan(self, payload: GoalPlanRequest) -> tuple[str, list[PhaseItem], list[PlannerTask]]:
        goal = payload.goal or "AI 应用开发实习"
        return (
            f"已围绕“{goal}”生成阶段计划，每天投入 {payload.daily_hours:g} 小时。",
            [
                PhaseItem(title="阶段 1：岗位能力对齐", detail="拆解目标岗位 JD 高频技能，建立学习清单和刷题节奏。"),
                PhaseItem(title="阶段 2：AI 应用项目冲刺", detail="完成规划闭环、RAG、评测和部署能力，沉淀可展示证据。"),
                PhaseItem(title="阶段 3：投递与复盘", detail="优化简历 bullet、项目讲法和面试题库，持续根据反馈调整。"),
            ],
            [
                PlannerTask(time="09:00", title="阅读目标岗位 JD 并提取 5 个关键词", reason="让当天任务和真实岗位要求对齐。"),
                PlannerTask(time="14:30", title="实现或优化一个 AI 应用功能", reason="每天保留可展示的工程产出。"),
                PlannerTask(time="20:30", title="记录完成情况并生成明日调整", reason="形成计划、执行、复盘、重排闭环。"),
            ],
        )

    def _mock_daily_review(
        self,
        done_count: int,
        total_count: int,
        unfinished: list[dict[str, object]],
        target_date: str,
    ) -> tuple[str, list[str], list[ReplanTask]]:
        suggestions = [
            "保留今天已经完成的产出，作为周报和面试复盘素材。",
            "把未完成任务拆成 30-45 分钟的小块，降低明天启动成本。",
            "明天优先处理和长期目标最相关的一项任务。",
        ]
        replan_tasks = []
        for index, plan in enumerate(unfinished[:3]):
            replan_tasks.append(
                ReplanTask(
                    targetDate=target_date,
                    time=str(plan.get("time") or f"{9 + index:02d}:00")[:5],
                    title=f"继续推进：{plan.get('title') or plan.get('content') or '未完成任务'}",
                    reason="来自今日未完成任务，已放入明日重排预览。",
                    sourcePlanId=str(plan.get("id")) if plan.get("id") else None,
                )
            )
        if not replan_tasks:
            replan_tasks.append(
                ReplanTask(
                    targetDate=target_date,
                    time="09:00",
                    title="整理今日完成证据并规划下一步",
                    reason="今天没有遗留任务，明天从复盘沉淀开始。",
                )
            )
        return f"今天完成 {done_count}/{total_count} 项。", suggestions, replan_tasks
