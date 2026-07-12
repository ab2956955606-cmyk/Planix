from __future__ import annotations

from ...services.cognitive_planning.contracts import (
    EvidencePack,
    ExecutionBlueprint,
    PlanCritiqueReport,
    PlanningLearningUpdate,
    StrategyPortfolio,
)
from ..contracts import GoalUnderstandingArtifact, RealityAssessment
from .base import AgentResult, CognitiveModelClient


CRITIC_SYSTEM = """
You are Planix Critic Agent and are independent from every generator. Reject template leakage, weak user fit,
domain mistakes, unsafe advice, unrealistic workload, invented or unusable resources, vague tasks, dependency
errors, and plans the user cannot actually execute. Compare the plan with the Goal Understanding, Reality
Assessment, and Evidence Pack. Simulate the first action, the hardest period, resource failure, task failure,
half the expected available time, and one domain-specific risk. You have Calendar veto power. Return targeted
repair instructions to the responsible agent. Return only JSON and never hidden chain-of-thought.
""".strip()


LEARNING_SYSTEM = """
You are Planix Critic Agent learning from user feedback. Diagnose the failed assumption and responsible stage,
repair the current artifact, and create a user-model memory only when the observation is useful beyond this
single plan. A single observation remains tentative and must retain its evidence and confidence. Approval
phrases are not feedback. Return only the requested JSON and never hidden chain-of-thought.
""".strip()


class CriticAgent:
    name = "Critic Agent"
    critique_artifact_type = "critique_report"
    learning_artifact_type = "planning_learning_update"

    def __init__(self, model: CognitiveModelClient | None = None):
        self.model = model or CognitiveModelClient()

    def critique(
        self,
        goal: GoalUnderstandingArtifact,
        evidence: EvidencePack,
        strategy: StrategyPortfolio,
        execution: ExecutionBlueprint,
        *,
        reality: RealityAssessment | None = None,
    ) -> AgentResult[PlanCritiqueReport]:
        return self.model.complete_contract(
            stage="independent_critique",
            task_type="planning_critique",
            feature="cognitive_os_independent_critique",
            system=CRITIC_SYSTEM,
            payload={
                "goalUnderstanding": goal.model_dump(by_alias=True),
                "realityAssessment": reality.model_dump(by_alias=True) if reality else None,
                "evidencePack": evidence.model_input_view(),
                "strategyProposal": strategy.model_dump(by_alias=True),
                "executionPlan": execution.model_dump(by_alias=True),
            },
            contract_type=PlanCritiqueReport,
            temperature=0.05,
        )

    def learn(
        self,
        feedback: str,
        *,
        goal: GoalUnderstandingArtifact | None,
        evidence: EvidencePack | None,
        strategy: StrategyPortfolio | None,
        execution: ExecutionBlueprint | None,
        critique: PlanCritiqueReport | None,
        reality: RealityAssessment | None = None,
    ) -> AgentResult[PlanningLearningUpdate]:
        return self.model.complete_contract(
            stage="feedback_learning",
            task_type="planning_learning",
            feature="cognitive_os_feedback_learning",
            system=LEARNING_SYSTEM,
            payload={
                "feedback": feedback,
                "goalUnderstanding": goal.model_dump(by_alias=True) if goal else None,
                "realityAssessment": reality.model_dump(by_alias=True) if reality else None,
                "evidencePack": evidence.model_input_view() if evidence else None,
                "strategyProposal": strategy.model_dump(by_alias=True) if strategy else None,
                "executionPlan": execution.model_dump(by_alias=True) if execution else None,
                "criticReport": critique.model_dump(by_alias=True) if critique else None,
            },
            contract_type=PlanningLearningUpdate,
            temperature=0.15,
        )
