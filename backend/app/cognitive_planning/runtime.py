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
from ..services.cognitive_planning.orchestration.runtime import (
    RESUME_NODE_BY_STAGE,
    CognitivePlanningRuntime as Phase6Runtime,
)
from .agents import (
    CognitiveModelClient,
    CriticAgent,
    EvidenceAgent,
    ExecutionAgent,
    GoalCompletionJudge,
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
        self.goal_completion_judge = GoalCompletionJudge()
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
        stage = str(error.stage or "")
        if stage in {"goal_intelligence", "goal_modeling", "goal_completion"}:
            completion = state.get("goal_completion")
            business_status = "goal_understood" if completion and completion.complete else "goal_clarification"
        elif stage in {"reality_assessment", "context_evidence", "evidence_synthesis"}:
            business_status = "evidence_pending"
        elif stage in {"strategy_architecture", "strategy_design"}:
            business_status = "strategy_pending"
        else:
            business_status = "execution_pending"
        state["planning_mode"] = "blocked_model_unavailable"
        state["errors"] = [*state.get("errors", []), error]
        state["status"] = "MODEL_UNAVAILABLE"
        state["business_status"] = business_status
        state["runtime_status"] = "blocked_model"
        state["resume_node"] = RESUME_NODE_BY_STAGE.get(stage, "goal_intelligence")
        self.agent_runtime.record_message(
            state["session_id"],
            from_agent=agent,
            to_agent=agent,
            message_type="block",
            reason=error.message,
            payload={
                "errorType": error.error_type,
                "retryable": error.retryable,
                "attempts": error.attempts,
                "resumeNode": state["resume_node"],
            },
            resolved=False,
        )
        self.persistence.update(
            state["session_id"],
            status="MODEL_UNAVAILABLE",
            business_status=business_status,
            runtime_status="blocked_model",
            cognitive_metadata=self._metadata(
                mode="blocked_model_unavailable",
                stage=error.stage,
                repair_count=int(state.get("repair_count", 0)),
            ),
        )
        return state

    def goal_modeling_node(self, state: CognitivePlanningState) -> CognitivePlanningState:
        previous = state.get("goal_model")
        domain = previous.domain if previous else ""
        user_model_memories = self.user_model.relevant(domain)
        pre_extracted_facts = extract_obvious_facts(state.get("user_input", ""))
        request_context = state.get("request_context", {})
        prior_understanding = request_context.get("goalUnderstanding") if isinstance(request_context, dict) else None
        if isinstance(prior_understanding, dict):
            allowed = {
                "intentState",
                "understoodIntent",
                "possibleDomains",
                "knownFacts",
                "uncertainties",
                "consistencyWarnings",
                "nextQuestion",
                "confidence",
            }
            pre_extracted_facts["goalUnderstanding"] = {
                key: prior_understanding[key]
                for key in allowed
                if key in prior_understanding
            }
        payload = GoalModelingInput(
            conversationHistory=state.get("conversation_history", []),
            previousGoalModel=previous,
            preExtractedFacts=pre_extracted_facts,
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
        state["runtime_status"] = "running"
        self._record_artifact(
            state,
            agent=self.goal_agent.name,
            artifact_type=self.goal_agent.artifact_type,
            artifact=goal,
            model_usage=result.model_usage,
            decision="produce_artifact",
            reason=(goal.questions[0].why_this_question_matters if goal.questions else goal.desired_change),
            summary="Goal Intelligence updated the semantic goal model; completion is judged separately.",
            status="draft",
            input_artifact_types=("user_goal_model",),
        )
        self.persistence.update(
            state["session_id"],
            runtime_status="running",
            goal_model=goal,
            cognitive_metadata=self._metadata(
                mode="model_backed",
                stage="goal_intelligence",
                confidence=goal.confidence,
                rules=[item.statement for item in user_model_memories],
                repair_count=int(state.get("repair_count", 0)),
            ),
        )
        return state

    def goal_completion_node(self, state: CognitivePlanningState) -> CognitivePlanningState:
        goal = state.get("goal_model")
        if not goal:
            return state
        completion = self.goal_completion_judge.evaluate(goal)
        if goal.can_proceed_to_evidence != completion.complete:
            goal = goal.model_copy(update={"can_proceed_to_evidence": completion.complete})
            state["goal_model"] = goal
        state["goal_completion"] = completion
        status = "needs_goal_clarification" if not completion.complete else state.get("status", "needs_goal_clarification")
        business_status = "goal_understood" if completion.complete else "goal_clarification"
        runtime_status = "running" if completion.complete else "idle"
        state["status"] = status
        state["business_status"] = business_status
        state["runtime_status"] = runtime_status
        self._record_artifact(
            state,
            agent=self.goal_completion_judge.name,
            artifact_type=self.goal_completion_judge.artifact_type,
            artifact=completion,
            model_usage={},
            decision="approve" if completion.complete else "request_user_input",
            reason=(
                "Only non-blocking unknowns remain."
                if completion.complete
                else completion.blocking_unknowns[0].impact
            ),
            summary=(
                "Goal completion passed; planning may continue toward strategy."
                if completion.complete
                else "Goal completion is waiting only on decision-blocking information."
            ),
            status="approved" if completion.complete else "blocked",
            input_artifact_types=("user_goal_model",),
        )
        self.persistence.update(
            state["session_id"],
            status=status,
            business_status=business_status,
            runtime_status=runtime_status,
            goal_model=goal,
            goal_completion=completion,
            cognitive_metadata=self._metadata(
                mode="model_backed",
                stage="goal_completion",
                confidence=goal.confidence,
                repair_count=int(state.get("repair_count", 0)),
            ),
            clear=("reality_assessment", "evidence_pack", "strategy_portfolio", "execution_blueprint", "critique_report")
            if not completion.complete
            else (),
        )
        if completion.complete:
            self._handoff(state, self.goal_agent.name, self.reality_agent.name, "Goal understanding is reliable enough for reality assessment.")
        elif completion.blocking_unknowns:
            state["conversation_history"] = self.persistence.append_assistant_turn(
                state["session_id"],
                "\n".join(item.question for item in completion.blocking_unknowns),
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
        state["business_status"] = "evidence_pending"
        state["runtime_status"] = "running" if reality.can_proceed_to_evidence else "idle"
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
            business_status="evidence_pending",
            runtime_status=state["runtime_status"],
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
