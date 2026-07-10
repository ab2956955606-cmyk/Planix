from __future__ import annotations

from ...services.cognitive_planning.agents.goal_modeling_agent import extract_obvious_facts
from ..contracts import GoalModelingInput, GoalUnderstandingArtifact
from .base import AgentResult, CognitiveModelClient


GOAL_INTELLIGENCE_SYSTEM = """
You are Planix Goal Intelligence Agent. Understand what the user is truly trying to change from the complete
conversation and evidence-backed user-model memory. You are not completing a learning, travel, fitness,
career, or any other domain form. Do not use a fixed question bank or infer that every person in a domain
needs the same information.

Decide independently: what the real goal may be, how reliable the current interpretation is, which unknowns
would materially change the strategy, which one to three questions have the highest decision value, and
whether asking more would improve the plan enough to justify interrupting the user. Preserve exact hard
constraints and important user wording. Fill possibleIntents, currentKnowledge, and uncertainties with concise
user-visible statements. Every question must explain why it matters and what decision its answer changes.
Stop asking when the goal is sufficiently reliable for a separate Reality Agent to assess it. Return only the
requested JSON. Do not reveal hidden chain-of-thought.
""".strip()


class GoalIntelligenceAgent:
    name = "Goal Intelligence Agent"
    artifact_type = "user_goal_model"

    def __init__(self, model: CognitiveModelClient | None = None):
        self.model = model or CognitiveModelClient()

    def run(self, payload: GoalModelingInput) -> AgentResult[GoalUnderstandingArtifact]:
        result = self.model.complete_contract(
            stage="goal_intelligence",
            task_type="planning_goal_model",
            feature="cognitive_os_goal_intelligence",
            system=GOAL_INTELLIGENCE_SYSTEM,
            payload=payload.model_dump(by_alias=True),
            contract_type=GoalUnderstandingArtifact,
            temperature=0.15,
        )
        goal = result.artifact
        questions = goal.questions[:3]
        blocking = [item for item in goal.decision_relevant_unknowns if item.priority == "blocking"]
        if blocking and goal.can_proceed_to_evidence:
            goal = goal.model_copy(update={"can_proceed_to_evidence": False, "questions": questions})
        elif len(goal.questions) > 3:
            goal = goal.model_copy(update={"questions": questions})
        return AgentResult(goal, result.model_usage)


__all__ = ["GoalIntelligenceAgent", "extract_obvious_facts"]
