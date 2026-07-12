from __future__ import annotations

from ..contracts import (
    EvidencePack,
    ExecutionBlueprint,
    PlanCritiqueReport,
    PlanningLearningUpdate,
    StrategyPortfolio,
    UserGoalModel,
)
from .base import AgentResult, CognitiveModelClient


CRITIC_SYSTEM = """
You are Planix Independent Critic. You are independent from the plan generator and only inspect formal
artifacts. Audit user fit, goal alignment, domain correctness, feasibility, safety, time fit, task specificity,
dependencies, resource actionability and credibility, schedule realism, and adaptability. Simulate at least the
first day, the busiest week or stage, the primary resource becoming unavailable, a failed task, the user having
only half the planned time, and one domain-specific risk. A plan is
calendarWritable only when model-backed, concrete, safe, feasible, and all blocking findings are resolved.
Return targeted repair instructions to the responsible agent. Never reveal hidden chain-of-thought.
""".strip()


LEARNING_SYSTEM = """
You are Planix Independent Critic & Learning Agent. Diagnose user feedback before storing anything. Identify
the failed assumption, responsible stage, root cause, a precise current-artifact patch, and only a genuinely
useful evidence-based user-model hypothesis. A single observation stays tentative. Approval phrases are not
feedback. Mark evidencePolarity="negative" when the feedback contradicts an existing hypothesis rather than
supporting it. Return only the requested JSON and never hidden chain-of-thought.
""".strip()


class CriticLearningAgent:
    name = "Independent Critic & Learning Agent"
    critique_artifact_type = "critique_report"
    learning_artifact_type = "planning_learning_update"

    def __init__(self, model: CognitiveModelClient | None = None):
        self.model = model or CognitiveModelClient()

    def critique(
        self,
        goal: UserGoalModel,
        evidence: EvidencePack,
        strategy: StrategyPortfolio,
        execution: ExecutionBlueprint,
    ) -> AgentResult[PlanCritiqueReport]:
        return self.model.complete_contract(
            stage="plan_critique",
            task_type="planning_critique",
            feature="cognitive_plan_critique",
            system=CRITIC_SYSTEM,
            payload={
                "goalModel": goal.model_dump(by_alias=True),
                "evidencePack": evidence.model_input_view(),
                "strategyPortfolio": strategy.model_dump(by_alias=True),
                "executionBlueprint": execution.model_dump(by_alias=True),
            },
            contract_type=PlanCritiqueReport,
            temperature=0.05,
        )

    def learn(
        self,
        feedback: str,
        *,
        goal: UserGoalModel | None,
        evidence: EvidencePack | None,
        strategy: StrategyPortfolio | None,
        execution: ExecutionBlueprint | None,
        critique: PlanCritiqueReport | None,
    ) -> AgentResult[PlanningLearningUpdate]:
        return self.model.complete_contract(
            stage="feedback_learning",
            task_type="planning_learning",
            feature="cognitive_feedback_learning",
            system=LEARNING_SYSTEM,
            payload={
                "feedback": feedback,
                "goalModel": goal.model_dump(by_alias=True) if goal else None,
                "evidencePack": evidence.model_input_view() if evidence else None,
                "strategyPortfolio": strategy.model_dump(by_alias=True) if strategy else None,
                "executionBlueprint": execution.model_dump(by_alias=True) if execution else None,
                "critiqueReport": critique.model_dump(by_alias=True) if critique else None,
            },
            contract_type=PlanningLearningUpdate,
            temperature=0.15,
        )
