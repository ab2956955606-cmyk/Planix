import json
from datetime import date as date_type
from datetime import timedelta
from uuid import uuid4

from ..db import get_conn, load_memory
from ..errors import bad_request
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
    StructuredGoalPlan,
)
from .llm import LlmClient
from .planner import _json_object
from .plans import create_plan, list_plans
from .rag import RagService
from .structured_goal_plan import (
    build_local_structured_plan,
    derive_phase_items,
    derive_planner_tasks,
    normalize_structured_plan,
)


GOAL_PLAN_LLM_TIMEOUT_SECONDS = 30
GOAL_PLAN_MAX_TOKENS = 1200


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
                reason=str(item.get("reason") or "This task supports the current goal."),
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
                reason=str(item.get("reason") or "Replanned from unfinished work."),
                sourcePlanId=item.get("sourcePlanId") or item.get("source_plan_id"),
            )
        )
    return tasks


def _structured_from_parsed(
    parsed: dict[str, object] | None,
    fallback: StructuredGoalPlan,
) -> StructuredGoalPlan:
    if not parsed:
        return fallback
    raw = parsed.get("structuredPlan") or parsed.get("structured_plan")
    if raw is None and "goalTitle" in parsed and "milestones" in parsed:
        raw = parsed
    return normalize_structured_plan(raw, fallback)


def _plan_to_dict(plan: PlanOut) -> dict[str, object]:
    return plan.model_dump(by_alias=True)


class PlanningService:
    def __init__(self):
        self.rag = RagService()

    def create_goal_plan(self, payload: GoalPlanRequest) -> GoalPlanOut:
        _parse_date(payload.date)
        preferences = payload.preferences or load_memory()
        sources = self.rag.retrieve(" ".join([payload.goal, payload.materials]), limit=4)
        retrieved_sources = [source.model_dump(by_alias=True) for source in sources]
        fallback_structured = build_local_structured_plan(
            payload.goal,
            date=payload.date,
            deadline=payload.deadline,
            daily_hours=payload.daily_hours,
            source_count=len(sources),
        )
        llm_result, _ = LlmClient().complete(
            "planning_goal_plan",
            (
                "You are an AI planning agent. Return only valid JSON, no markdown. "
                'Required shape: {"summary":"...","structuredPlan":{"goalTitle":"...",'
                '"goalDescription":"...","durationDays":14,"milestones":[{"title":"...",'
                '"description":"...","tasks":[{"title":"...","description":"...",'
                '"estimatedMinutes":60,"dueDate":"YYYY-MM-DD or null","priority":"low|medium|high"}]}],'
                '"reviewPlan":{"frequency":"daily|weekly","questions":["..."]}},'
                '"phases":[{"title":"...","detail":"..."}],'
                '"tasks":[{"time":"HH:MM","title":"...","reason":"..."}]}. '
                "Use retrievedSources when available. The structuredPlan is the source of truth. "
                "Do not include write intents and do not claim that data was written."
            ),
            _dump(
                {
                    "goal": payload.goal,
                    "deadline": payload.deadline,
                    "dailyHours": payload.daily_hours,
                    "materials": payload.materials[:3000],
                    "retrievedSources": retrieved_sources,
                    "preferences": preferences,
                    "date": payload.date,
                }
            ),
            max_tokens=GOAL_PLAN_MAX_TOKENS,
            temperature=0.2,
            timeout_seconds=GOAL_PLAN_LLM_TIMEOUT_SECONDS,
        )

        mode = "mock"
        provider = None
        model = None
        parsed = _json_object(llm_result.content) if llm_result else None
        if parsed:
            mode = "llm"
            provider = llm_result.provider if llm_result else None
            model = llm_result.model if llm_result else None
            structured_plan = _structured_from_parsed(parsed, fallback_structured)
            summary = str(parsed.get("summary") or structured_plan.goal_description)
            phases = _normalize_phase_items(parsed.get("phases"))
            tasks = _normalize_planner_tasks(parsed.get("tasks"))
        else:
            structured_plan = fallback_structured
            summary = structured_plan.goal_description
            phases = []
            tasks = []

        if not phases or not tasks:
            phases = phases or derive_phase_items(structured_plan)
            tasks = tasks or derive_planner_tasks(structured_plan)
        if not summary:
            summary = structured_plan.goal_description

        plan_id = str(uuid4())
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO planning_goals(
                  id, goal, deadline, daily_hours, materials, preferences,
                  summary, phases_json, tasks_json, structured_plan_json, sources_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    _dump(structured_plan.model_dump(by_alias=True)),
                    _dump(retrieved_sources),
                ),
            )

        return GoalPlanOut(
            id=plan_id,
            mode=mode,
            summary=summary,
            phases=phases,
            tasks=tasks,
            sources=sources,
            structuredPlan=structured_plan,
            provider=provider,
            model=model,
        )

    def create_daily_review(self, payload: DailyReviewRequest) -> DailyReviewOut:
        review_date = _parse_date(payload.date).isoformat()
        target_date = _next_day(review_date)
        plans = self._plans_for_review(payload)
        done_count = len([plan for plan in plans if plan.get("done")])
        total_count = len(plans)
        unfinished = [plan for plan in plans if not plan.get("done")]
        llm_result, _ = LlmClient().complete(
            "planning_daily_review",
            (
                "You are an AI daily review and replanning assistant. Return only valid JSON, no markdown. "
                'Required shape: {"summary":"...","suggestions":["..."],'
                '"replanTasks":[{"targetDate":"YYYY-MM-DD","time":"HH:MM","title":"...","reason":"...",'
                '"sourcePlanId":"..."}]}. '
                "Use at most 4 suggestions and at most 4 replanTasks. Do not modify data directly."
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
            max_tokens=1800,
            temperature=0.2,
        )

        mode = "mock"
        provider = None
        model = None
        parsed = _json_object(llm_result.content) if llm_result else None
        if parsed:
            mode = "llm"
            provider = llm_result.provider if llm_result else None
            model = llm_result.model if llm_result else None
            summary = str(parsed.get("summary") or f"Today completed {done_count}/{total_count} tasks.")
            suggestions = _normalize_suggestions(parsed.get("suggestions"))
            replan_tasks = _normalize_replan_tasks(parsed.get("replanTasks") or parsed.get("replan_tasks"), target_date)
        else:
            summary, suggestions, replan_tasks = self._mock_daily_review(done_count, total_count, unfinished, target_date)

        if not suggestions:
            suggestions = ["Keep today's useful output and split unfinished work into smaller next steps."]

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
            return DailyReviewOut(
                id="",
                mode="saved",
                date=normalized_date,
                summary="",
                suggestions=[],
                doneCount=0,
                totalCount=0,
                targetDate=_next_day(normalized_date),
                replanTasks=[],
                updatedAt="",
            )
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

    def _mock_goal_plan(self, payload: GoalPlanRequest, source_count: int = 0) -> tuple[str, list[PhaseItem], list[PlannerTask]]:
        goal = payload.goal or "AI application internship"
        source_note = f"Referenced {source_count} retrieved material chunks. " if source_count else ""
        return (
            f"{source_note}Generated a three-phase plan for {goal} with {payload.daily_hours:g} focused hours per day.",
            [
                PhaseItem(
                    title="Phase 1: Role alignment",
                    detail="Extract the target role requirements, map required skills, and build a focused learning checklist.",
                ),
                PhaseItem(
                    title="Phase 2: Portfolio sprint",
                    detail="Ship demonstrable AI application features, including planning loop, RAG, evaluation, and deployment evidence.",
                ),
                PhaseItem(
                    title="Phase 3: Application review",
                    detail="Refine resume bullets, project narrative, interview notes, and weekly feedback loops.",
                ),
            ],
            [
                PlannerTask(
                    time="09:00",
                    title="Extract five requirements from the target JD",
                    reason="Align today's work with real internship expectations.",
                ),
                PlannerTask(
                    time="14:30",
                    title="Implement or improve one AI application feature",
                    reason="Keep a visible engineering output every day.",
                ),
                PlannerTask(
                    time="20:30",
                    title="Review progress and update tomorrow's task list",
                    reason="Close the loop between planning, execution, review, and replanning.",
                ),
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
            "Keep today's completed outputs as weekly review and interview evidence.",
            "Split unfinished tasks into 30-45 minute blocks to reduce tomorrow's startup cost.",
            "Prioritize the task most directly connected to the long-term goal.",
        ]
        replan_tasks = []
        for index, plan in enumerate(unfinished[:3]):
            title = plan.get("title") or plan.get("content") or "unfinished task"
            replan_tasks.append(
                ReplanTask(
                    targetDate=target_date,
                    time=str(plan.get("time") or f"{9 + index:02d}:00")[:5],
                    title=f"Continue: {title}",
                    reason="Moved from today's unfinished work into tomorrow's replan preview.",
                    sourcePlanId=str(plan.get("id")) if plan.get("id") else None,
                )
            )
        if not replan_tasks:
            replan_tasks.append(
                ReplanTask(
                    targetDate=target_date,
                    time="09:00",
                    title="Review today's evidence and choose the next step",
                    reason="No unfinished task was found, so tomorrow starts from a lightweight review.",
                )
            )
        return f"Today completed {done_count}/{total_count} tasks.", suggestions, replan_tasks
