from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from .base import CognitiveContract


class ConversationTurn(CognitiveContract):
    role: Literal["user", "assistant", "system"]
    content: str


class MemoryHint(CognitiveContract):
    source_id: str | None = None
    kind: str
    statement: str
    confidence: float = Field(default=0.5, ge=0, le=1)


class Constraint(CognitiveContract):
    statement: str
    source_text: str = ""
    category: str = "general"


class Preference(CognitiveContract):
    statement: str
    source_text: str = ""
    confidence: float = Field(default=0.5, ge=0, le=1)


class KnownFact(CognitiveContract):
    key: str
    statement: str
    source_text: str = ""
    confidence: float = Field(default=1, ge=0, le=1)


class DecisionRelevantUnknown(CognitiveContract):
    key: str
    description: str
    why_it_changes_the_plan: str
    impact: Literal[
        "strategy",
        "safety",
        "feasibility",
        "schedule",
        "resources",
        "success_criteria",
    ]
    priority: Literal["blocking", "important", "optional"]


class GoalAssumption(CognitiveContract):
    statement: str
    confidence: float = Field(ge=0, le=1)
    needs_user_confirmation: bool = False


class GoalSuccessModel(CognitiveContract):
    definition: str
    measurable_signals: list[str] = Field(default_factory=list)
    intermediate_milestones: list[str] = Field(default_factory=list)


class FeasibilityJudgment(CognitiveContract):
    summary: str
    risks: list[str] = Field(default_factory=list)
    unrealistic_parts: list[str] = Field(default_factory=list)


class GoalQuestion(CognitiveContract):
    question: str = Field(min_length=1)
    why_this_question_matters: str = Field(min_length=1)
    expected_decision_impact: str = Field(min_length=1)


class UserGoalModel(CognitiveContract):
    goal_statement: str
    desired_change: str
    domain: str
    subdomain: str | None = None
    possible_intents: list[str] = Field(default_factory=list)
    current_knowledge: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    user_language: list[str] = Field(default_factory=list)
    hard_constraints: list[Constraint] = Field(default_factory=list)
    soft_preferences: list[Preference] = Field(default_factory=list)
    known_facts: list[KnownFact] = Field(default_factory=list)
    decision_relevant_unknowns: list[DecisionRelevantUnknown] = Field(default_factory=list)
    assumptions: list[GoalAssumption] = Field(default_factory=list)
    success_model: GoalSuccessModel
    feasibility_judgment: FeasibilityJudgment = Field(
        default_factory=lambda: FeasibilityJudgment(summary="Deferred to Reality Agent")
    )
    questions: list[GoalQuestion] = Field(default_factory=list, max_length=3)
    confidence: float = Field(ge=0, le=1)
    can_proceed_to_evidence: bool

    @model_validator(mode="after")
    def blocked_goal_requires_a_user_question(self) -> "UserGoalModel":
        blocking_unknowns = [item for item in self.decision_relevant_unknowns if item.priority == "blocking"]
        if blocking_unknowns and self.can_proceed_to_evidence:
            raise ValueError("blocking decision-relevant unknowns must stop evidence planning")
        if not self.can_proceed_to_evidence and not self.questions:
            raise ValueError("a blocked goal model must ask at least one decision-relevant question")
        return self


class GoalModelingInput(CognitiveContract):
    conversation_history: list[ConversationTurn]
    previous_goal_model: UserGoalModel | None = None
    pre_extracted_facts: dict[str, Any] = Field(default_factory=dict)
    relevant_memory_hints: list[MemoryHint] = Field(default_factory=list)
