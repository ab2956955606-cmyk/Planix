from fastapi import APIRouter

from ..schemas import (
    DailyReviewOut,
    DailyReviewRequest,
    GoalPlanOut,
    GoalPlanRequest,
    PlanOut,
    RefinedTask,
    RefineTaskRequest,
    ReplanApplyRequest,
)
from ..services.planning import PlanningService

router = APIRouter(prefix="/api/planning", tags=["planning"])

planning = PlanningService()


@router.post("/goal-plan", response_model=GoalPlanOut)
def create_goal_plan(payload: GoalPlanRequest) -> GoalPlanOut:
    return planning.create_goal_plan(payload)


@router.post("/daily-review", response_model=DailyReviewOut)
def create_daily_review(payload: DailyReviewRequest) -> DailyReviewOut:
    return planning.create_daily_review(payload)


@router.post("/refine-task", response_model=RefinedTask)
def refine_task(payload: RefineTaskRequest) -> RefinedTask:
    return planning.refine_task(payload)


@router.get("/daily-review", response_model=DailyReviewOut)
def get_daily_review(date: str) -> DailyReviewOut:
    return planning.get_daily_review(date)


@router.post("/replan/apply", response_model=list[PlanOut])
def apply_replan(payload: ReplanApplyRequest) -> list[PlanOut]:
    return planning.apply_replan(payload)
