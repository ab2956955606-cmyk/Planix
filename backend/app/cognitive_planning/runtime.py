from __future__ import annotations

import os

from ..schemas import PlanningSessionResponse
from ..services.cognitive_planning.contracts import (
    CognitivePlanningMetadata,
    CognitivePlanningState,
    GoalModelingInput,
    MemoryHint,
    RealityAssessment,
    RealityAssessmentInput,
    SafePlanningError,
    UserGoalModel,
)
from ..services.cognitive_planning.orchestration.persistence import json_object
from ..services.cognitive_planning.orchestration.runtime import CognitivePlanningRuntime as Phase6Runtime
from .agents import (
    CognitiveModelClient,
    CriticAgent,
    EvidenceAgent,
    ExecutionAgent,
    GoalIntelligenceAgent,
    PlanningModelUnavailable,
    RealityAgent,
    StrategyAgent,
    extract_obvious_facts,
)
from .graph import build_cognitive_os_graph
from .memory import UserModelMemoryRepository


TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


def use_cognitive_os() -> bool:
    value = os.getenv("PLANIX_COGNITIVE_MODE")
    if value is None:
        return True
    normalized = value.strip().lower()
    if normalized in FALSE_VALUES:
        return False
    return normalized in TRUE_VALUES


class CognitiveOSRuntime(Phase6Runtime):
    """AI-native planning runtime. Rules protect; templates never decide."""

    engine_version = "cognitive-os-v1"

    def __init__(
        self,
        *,
        model_client: CognitiveModelClient | None = None,
        persistence=None,
        user_model: UserModelMemoryRepository | None = None,
    ):
        model = model_client or CognitiveModelClient()
        super().__init__(model_client=model, persistence=persistence)
        self.user_model = user_model or UserModelMemoryRepository()
        self.goal_agent = GoalIntelligenceAgent(model)
        self.reality_agent = RealityAgent(model)
        self.evidence_agent = EvidenceAgent(model=model, user_model=self.user_model)
        self.strategy_agent = StrategyAgent(model)
        self.execution_agent = ExecutionAgent(model)
        self.critic_agent = CriticAgent(model)
        self.hypotheses = self.user_model

    def _metadata(
        self,
        *,
        mode: str,
        stage: str,
        confidence: float | None = None,
        rules: list[str] | None = None,
        repair_count: int = 0,
    ) -> CognitivePlanningMetadata:
        return CognitivePlanningMetadata(
            engineVersion="cognitive-os-v1",
            planningMode=mode,
            currentStage=stage,
            agentConfidence=confidence,
            appliedUserRules=rules or [],
            repairCount=repair_count,
        )

    def _state_from_row(self, row, *, action: str, user_input: str = "") -> CognitivePlanningState:
        state = super()._state_from_row(row, action=action, user_input=user_input)
        if "reality_assessment_json" in row.keys():
            raw = json_object(row["reality_assessment_json"])
            if raw:
                state["reality_assessment"] = RealityAssessment.model_validate(raw)
        return state

    def _invoke(self, state: CognitivePlanningState) -> PlanningSessionResponse:
        result = build_cognitive_os_graph(self).invoke(state)
        session_id = str(result.get("session_id") or state["session_id"])
        return self.get_session(session_id)

    def _block_model(
        self,
        state: CognitivePlanningState,
        *,
        agent: str,
        error: SafePlanningError,
    ) -> CognitivePlanningState:
        blocked = super()._block_model(state, agent=agent, error=error)
        blocked["status"] = "MODEL_UNAVAILABLE"
        self.persistence.update(
            state["session_id"],
            status="MODEL_UNAVAILABLE",
            cognitive_metadata=self._metadata(
                mode="blocked_model_unavailable",
                stage=error.stage,
                repair_count=int(state.get("repair_count", 0)),
            ),
            clear=("strategy_portfolio", "execution_blueprint", "critique_report", "approved_strategy_id"),
        )
        return blocked

    def goal_modeling_node(self, state: CognitivePlanningState) -> CognitivePlanningState:
        previous = state.get("goal_model")
        domain = previous.domain if previous else ""
        user_model_memories = self.user_model.relevant(domain)
        payload = GoalModelingInput(
            conversationHistory=state.get("conversation_history", []),
            previousGoalModel=previous,
            preExtractedFacts=extract_obvious_facts(state.get("user_input", "")),
            relevantMemoryHints=[
                MemoryHint(
                    sourceId=item.id,
                    kind=item.category,
                    statement=item.statement,
                    confidence=item.confidence,
                )
                for item in user_model_memories
            ],
        )
        try:
            result = self.goal_agent.run(payload)
        except PlanningModelUnavailable as exc:
            return self._block_model(state, agent=self.goal_agent.name, error=exc.error)
        goal = result.artifact
        state["goal_model"] = goal
        state["planning_mode"] = "model_backed"
        status = "needs_goal_clarification" if not goal.can_proceed_to_evidence else state.get("status", "needs_goal_clarification")
        state["status"] = status
        self._record_artifact(
            state,
            agent=self.goal_agent.name,
            artifact_type=self.goal_agent.artifact_type,
            artifact=goal,
            model_usage=result.model_usage,
            decision="approve" if goal.can_proceed_to_evidence else "request_user_input",
            reason=(goal.questions[0].why_this_question_matters if goal.questions else goal.desired_change),
            summary=(
                "The goal is understood well enough for an independent reality check."
                if goal.can_proceed_to_evidence
                else "Planix needs the highest-impact unknown resolved before designing anything."
            ),
            status="approved" if goal.can_proceed_to_evidence else "blocked",
            input_artifact_types=("user_goal_model",),
        )
        self.persistence.update(
            state["session_id"],
            status=status,
            goal_model=goal,
            cognitive_metadata=self._metadata(
                mode="model_backed",
                stage="goal_intelligence",
                confidence=goal.confidence,
                rules=[item.statement for item in user_model_memories],
                repair_count=int(state.get("repair_count", 0)),
            ),
            clear=("reality_assessment", "evidence_pack", "strategy_portfolio", "execution_blueprint", "critique_report")
            if not goal.can_proceed_to_evidence
            else (),
        )
        if goal.can_proceed_to_evidence:
            self._handoff(state, self.goal_agent.name, self.reality_agent.name, "Goal understanding is reliable enough for reality assessment.")
        elif goal.questions:
            state["conversation_history"] = self.persistence.append_assistant_turn(
                state["session_id"],
                "\n".join(item.question for item in goal.questions),
            )
        return state

    def reality_assessment_node(self, state: CognitivePlanningState) -> CognitivePlanningState:
        goal = state.get("goal_model")
        if not goal:
            return state
        memories = self.user_model.relevant(goal.domain)
        payload = RealityAssessmentInput(
            goalModel=goal,
            conversationHistory=state.get("conversation_history", []),
            userModelMemories=[
                MemoryHint(sourceId=item.id, kind=item.category, statement=item.statement, confidence=item.confidence)
                for item in memories
            ],
            requestContext=state.get("request_context", {}),
        )
        try:
            result = self.reality_agent.run(payload)
        except PlanningModelUnavailable as exc:
            return self._block_model(state, agent=self.reality_agent.name, error=exc.error)
        reality = result.artifact
        state["reality_assessment"] = reality
        state["status"] = "needs_goal_clarification" if not reality.can_proceed_to_evidence else state.get("status", "needs_goal_clarification")
        self._record_artifact(
            state,
            agent=self.reality_agent.name,
            artifact_type=self.reality_agent.artifact_type,
            artifact=reality,
            model_usage=result.model_usage,
            decision="approve" if reality.can_proceed_to_evidence else "request_user_input",
            reason=reality.feasibility_summary,
            summary=(
                "The goal passed reality assessment."
                if reality.can_proceed_to_evidence
                else "Reality assessment found a decision that the user must resolve."
            ),
            status="approved" if reality.can_proceed_to_evidence else "blocked",
            input_artifact_types=("user_goal_model", "reality_assessment"),
        )
        self.persistence.update(
            state["session_id"],
            status=state["status"],
            reality_assessment=reality,
            cognitive_metadata=self._metadata(
                mode="model_backed",
                stage="reality_assessment",
                confidence=reality.confidence,
                rules=[item.statement for item in memories],
                repair_count=int(state.get("repair_count", 0)),
            ),
            clear=("evidence_pack", "strategy_portfolio", "execution_blueprint", "critique_report")
            if not reality.can_proceed_to_evidence
            else (),
        )
        if reality.can_proceed_to_evidence:
            self._handoff(state, self.reality_agent.name, self.evidence_agent.name, "The realistic scope is ready for evidence synthesis.")
        elif reality.important_questions:
            state["conversation_history"] = self.persistence.append_assistant_turn(
                state["session_id"],
                "\n".join(item.question for item in reality.important_questions),
            )
        return state

    def repair_router_node(self, state: CognitivePlanningState) -> CognitivePlanningState:
        state = super().repair_router_node(state)
        state["next_node"] = {
            "goal_modeling": "goal_intelligence",
            "context_evidence": "evidence",
            "strategy_architect": "strategy",
            "execution_designer": "execution",
            "independent_critic": "critic",
        }.get(str(state.get("next_node") or ""), state.get("next_node", "__end__"))
        return state


__all__ = ["CognitiveOSRuntime", "use_cognitive_os"]
