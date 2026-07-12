from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any

from fastapi import HTTPException

from ....schemas import CreatePlanningSessionRequest, PlanningSessionResponse, PlanningSessionTextRequest, UserNeedContract
from ...planning_agent_runtime import PlanningAgentRuntime
from ..agents import (
    CognitiveModelClient,
    ContextEvidenceAgent,
    CriticLearningAgent,
    ExecutionDesignerAgent,
    GoalModelingAgent,
    PlanningModelUnavailable,
    StrategyArchitectAgent,
    extract_obvious_facts,
)
from ..compatibility import SessionApiAdapter
from ..contracts import (
    CognitivePlanningMetadata,
    CognitivePlanningState,
    EvidencePack,
    CriticRepairRequest,
    CritiqueIssue,
    ExecutionBlueprint,
    GoalCompletionResult,
    GoalModelingInput,
    PlanCritiqueReport,
    PlanningLearningUpdate,
    SafePlanningError,
    StrategyPortfolio,
    UserGoalModel,
)
from ..evaluation import DeterministicGuardError, calendar_write_allowed, validate_execution_invariants
from ..retrieval import PlanningHypothesisRepository
from .graph import build_cognitive_graph
from .persistence import CognitivePlanningPersistence, json_object
from ..control_intent import detect_planning_control_intent


TRUE_VALUES = {"1", "true", "yes", "on"}


RESUME_NODE_BY_STAGE = {
    "goal_modeling": "goal_modeling",
    "goal_intelligence": "goal_intelligence",
    "goal_completion": "goal_completion",
    "reality_assessment": "reality",
    "context_evidence": "evidence",
    "evidence_synthesis": "evidence",
    "strategy_architecture": "strategy",
    "strategy_design": "strategy",
    "execution_narrative": "execution",
    "execution_design": "execution",
    "independent_critique": "critic",
    "critic_review": "critic",
    "plan_critique": "critic",
    "feedback_learning": "feedback_learning",
}


def use_cognitive_planning() -> bool:
    return os.getenv("PLANIX_USE_COGNITIVE_PLANNING", "").strip().lower() in TRUE_VALUES


class CognitivePlanningRuntime:
    """Model-backed planning kernel. It never falls back to legacy content templates."""

    def __init__(
        self,
        *,
        model_client: CognitiveModelClient | None = None,
        persistence: CognitivePlanningPersistence | None = None,
    ):
        model = model_client or CognitiveModelClient()
        # Compatibility runtime nodes remain Agent adapters; the Harness owns
        # version-bound approval/policy state even when this legacy graph is
        # selected explicitly.
        from ....harness import HarnessRuntime

        self.harness = HarnessRuntime()
        self.persistence = persistence or CognitivePlanningPersistence()
        self.agent_runtime = PlanningAgentRuntime()
        self.adapter = SessionApiAdapter(self.agent_runtime)
        self.goal_agent = GoalModelingAgent(model)
        self.evidence_agent = ContextEvidenceAgent(model=model)
        self.strategy_agent = StrategyArchitectAgent(model)
        self.execution_agent = ExecutionDesignerAgent(model)
        self.critic_agent = CriticLearningAgent(model)
        self.hypotheses = PlanningHypothesisRepository()

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
            planningMode=mode,
            currentStage=stage,
            agentConfidence=confidence,
            appliedUserRules=rules or [],
            repairCount=repair_count,
        )

    def _state_from_row(self, row, *, action: str, user_input: str = "") -> CognitivePlanningState:
        state: CognitivePlanningState = {
            "session_id": row["id"],
            "thread_id": row["thread_id"],
            "user_input": user_input,
            "conversation_history": self.persistence.conversation(row),
            "request_context": json_object(row["request_context_json"]) if "request_context_json" in row.keys() else {},
            "user_action": action,
            "status": row["status"],
            "business_status": (row["business_status"] or "goal_clarification") if "business_status" in row.keys() else "goal_clarification",
            "runtime_status": (row["runtime_status"] or "idle") if "runtime_status" in row.keys() else "idle",
            "planning_mode": "model_backed",
            "repair_count": int(row["repair_count"] or 0),
            "errors": [],
        }
        if "approved_strategy_id" in row.keys() and row["approved_strategy_id"]:
            state["approved_strategy_id"] = row["approved_strategy_id"]
        mappings = (
            ("goal_model", "goal_model_json", UserGoalModel),
            ("goal_completion", "goal_completion_json", GoalCompletionResult),
            ("evidence_pack", "evidence_pack_json", EvidencePack),
            ("strategy_portfolio", "strategy_portfolio_json", StrategyPortfolio),
            ("execution_blueprint", "execution_blueprint_json", ExecutionBlueprint),
            ("critique_report", "critique_report_json", PlanCritiqueReport),
            ("learning_update", "planning_learning_update_json", PlanningLearningUpdate),
        )
        for state_key, column, contract in mappings:
            raw = json_object(row[column])
            if raw:
                state[state_key] = contract.model_validate(raw)
        metadata = json_object(row["cognitive_metadata_json"])
        if metadata:
            state["planning_mode"] = metadata.get("planningMode", "model_backed")
            stage = str(metadata.get("currentStage") or "")
            if stage in RESUME_NODE_BY_STAGE:
                state["resume_node"] = RESUME_NODE_BY_STAGE[stage]
        evidence = state.get("evidence_pack")
        if evidence is not None and not evidence.is_authority_normalized:
            state["legacy_evidence_pack"] = evidence
            state["evidence_requires_authority_refresh"] = True
            for key in (
                "evidence_pack",
                "strategy_portfolio",
                "execution_blueprint",
                "critique_report",
                "approved_strategy_id",
            ):
                state.pop(key, None)
            state["user_action"] = "continue_current_stage"
            state["business_status"] = "evidence_pending"
            state["runtime_status"] = "running"
            state["resume_node"] = "evidence"
        return state

    def _resume_if_legacy_evidence(self, row) -> PlanningSessionResponse | None:
        state = self._state_from_row(row, action="continue_current_stage")
        if not state.get("evidence_requires_authority_refresh"):
            return None
        self.persistence.update(row["id"], runtime_status="running", business_status="evidence_pending")
        return self._invoke(state)

    def _invoke(self, state: CognitivePlanningState) -> PlanningSessionResponse:
        graph = build_cognitive_graph(self)
        result = graph.invoke(state)
        session_id = str(result.get("session_id") or state["session_id"])
        return self.get_session(session_id)

    def _record_artifact(
        self,
        state: CognitivePlanningState,
        *,
        agent: str,
        artifact_type: str,
        artifact: Any,
        model_usage: dict[str, Any],
        decision: str,
        reason: str,
        summary: str,
        status: str = "draft",
        input_artifact_types: tuple[str, ...] = (),
    ) -> str:
        input_artifact_ids = self._latest_artifact_ids(state["session_id"], input_artifact_types)
        item = self.agent_runtime.record_artifact(
            state["session_id"],
            owner_agent=agent,
            artifact_type=artifact_type,
            content=artifact,
            status=status,
        )
        self.agent_runtime.record_decision(
            state["session_id"],
            agent=agent,
            decision=decision,
            reason=reason,
            summary=summary,
            confidence=float(getattr(artifact, "confidence", 1) or 0),
            input_artifact_ids=input_artifact_ids,
            output_artifact_ids=[item.id],
            model_usage=model_usage,
        )
        return item.id

    def _latest_artifact_ids(self, session_id: str, artifact_types: tuple[str, ...]) -> list[str]:
        latest: dict[str, str] = {}
        for artifact in self.agent_runtime.list_artifacts(session_id):
            if artifact.artifact_type in artifact_types:
                latest[artifact.artifact_type] = artifact.id
        return [latest[key] for key in artifact_types if key in latest]

    def _handoff(self, state: CognitivePlanningState, from_agent: str, to_agent: str, reason: str) -> None:
        self.agent_runtime.record_message(
            state["session_id"],
            from_agent=from_agent,
            to_agent=to_agent,
            message_type="handoff",
            reason=reason,
            payload={},
            resolved=True,
        )

    def _block_model(self, state: CognitivePlanningState, *, agent: str, error: SafePlanningError) -> CognitivePlanningState:
        state["planning_mode"] = "blocked_model_unavailable"
        state["errors"] = [*state.get("errors", []), error]
        state["status"] = "needs_goal_clarification"
        self.agent_runtime.record_decision(
            state["session_id"],
            agent=agent,
            decision="block",
            reason=error.message,
            summary="Deep planning stopped because no model produced a valid artifact. Your facts were kept; no formal plan or Calendar write was created.",
            confidence=1,
        )
        self.agent_runtime.record_message(
            state["session_id"],
            from_agent=agent,
            to_agent=agent,
            message_type="block",
            reason=error.message,
            payload={"errorType": error.error_type, "retryable": error.retryable, "attempts": error.attempts},
            resolved=False,
        )
        known = UserNeedContract(
            rawUserInput="\n".join(turn.content for turn in state.get("conversation_history", []) if turn.role == "user"),
            interpretedGoal=state.get("user_input", "") or "Planning request",
            missingInformation=["working_model"],
            userWordsThatMustBeRespected=[turn.content for turn in state.get("conversation_history", []) if turn.role == "user"],
            canMoveToDesign=False,
            clarificationQuestions=[],
        )
        self.persistence.update(
            state["session_id"],
            status="needs_goal_clarification",
            cognitive_metadata=self._metadata(mode="blocked_model_unavailable", stage=error.stage, repair_count=int(state.get("repair_count", 0))),
            user_need_contract=known,
        )
        return state

    # LangGraph nodes
    def session_guard_node(self, state: CognitivePlanningState) -> CognitivePlanningState:
        if state.get("evidence_requires_authority_refresh"):
            self.persistence.update(
                state["session_id"],
                business_status="evidence_pending",
                runtime_status="running",
                clear=(
                    "evidence_pack",
                    "strategy_portfolio",
                    "execution_blueprint",
                    "critique_report",
                    "planning_learning_update",
                    "approved_strategy_id",
                ),
            )
        return state

    def wait_for_goal_answer_node(self, state: CognitivePlanningState) -> CognitivePlanningState:
        state["status"] = "needs_goal_clarification"
        completion = state.get("goal_completion")
        state["business_status"] = "evidence_pending" if completion and completion.complete else "goal_clarification"
        state["runtime_status"] = "idle"
        self.persistence.update(
            state["session_id"],
            status="needs_goal_clarification",
            business_status=state["business_status"],
            runtime_status="idle",
        )
        return state

    def wait_for_strategy_approval_node(self, state: CognitivePlanningState) -> CognitivePlanningState:
        state["status"] = "waiting_design_approval"
        state["business_status"] = "strategy_pending"
        state["runtime_status"] = "idle"
        self.persistence.update(
            state["session_id"],
            status="waiting_design_approval",
            business_status="strategy_pending",
            runtime_status="idle",
        )
        return state

    def wait_for_execution_approval_node(self, state: CognitivePlanningState) -> CognitivePlanningState:
        if state.get("user_action") == "approve_execution":
            return self.execution_approval_node(state)
        state["business_status"] = "execution_pending"
        state["runtime_status"] = "idle"
        self.persistence.update(
            state["session_id"],
            business_status="execution_pending",
            runtime_status="idle",
        )
        return state

    def goal_modeling_node(self, state: CognitivePlanningState) -> CognitivePlanningState:
        previous = state.get("goal_model")
        payload = GoalModelingInput(
            conversationHistory=state.get("conversation_history", []),
            previousGoalModel=previous,
            preExtractedFacts=extract_obvious_facts(state.get("user_input", "")),
            relevantMemoryHints=[],
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
            reason=goal.feasibility_judgment.summary,
            summary="Goal model updated. " + ("Evidence synthesis can begin." if goal.can_proceed_to_evidence else "The highest-impact unknowns need user input."),
            status="approved" if goal.can_proceed_to_evidence else "blocked",
            input_artifact_types=("user_goal_model",),
        )
        self.persistence.update(
            state["session_id"],
            status=status,
            goal_model=goal,
            cognitive_metadata=self._metadata(
                mode="model_backed",
                stage="goal_modeling",
                confidence=goal.confidence,
                repair_count=int(state.get("repair_count", 0)),
            ),
            clear=("evidence_pack", "strategy_portfolio", "execution_blueprint", "critique_report") if not goal.can_proceed_to_evidence else (),
        )
        if goal.can_proceed_to_evidence:
            self._handoff(state, self.goal_agent.name, self.evidence_agent.name, "Goal understanding is sufficient for evidence synthesis.")
        elif goal.questions:
            state["conversation_history"] = self.persistence.append_assistant_turn(
                state["session_id"],
                "\n".join(item.question for item in goal.questions),
            )
        return state

    def context_evidence_node(self, state: CognitivePlanningState) -> CognitivePlanningState:
        goal = state.get("goal_model")
        if not goal:
            return state
        try:
            context = state.get("request_context", {})
            evidence_kwargs = {
                "context_date": str(context.get("date") or "") or None,
                "web_research_allowed": bool(context.get("webResearchAllowed", False)),
                "web_research_approved": bool(context.get("webResearchApproved", False)),
                "freshness_required": bool(context.get("freshnessRequired", False)),
            }
            reality = state.get("reality_assessment")
            result = (
                self.evidence_agent.run(goal, reality, **evidence_kwargs)
                if reality is not None
                else self.evidence_agent.run(goal, **evidence_kwargs)
            )
        except PlanningModelUnavailable as exc:
            return self._block_model(state, agent=self.evidence_agent.name, error=exc.error)
        evidence = result.artifact
        state["evidence_pack"] = evidence
        state["status"] = "needs_goal_clarification" if not evidence.can_proceed_to_strategy else state.get("status", "needs_goal_clarification")
        state["business_status"] = "strategy_pending" if evidence.can_proceed_to_strategy else "evidence_pending"
        state["runtime_status"] = "running" if evidence.can_proceed_to_strategy else "idle"
        rules = [item.rule for item in evidence.planning_rules]
        self._record_artifact(
            state,
            agent=self.evidence_agent.name,
            artifact_type=self.evidence_agent.artifact_type,
            artifact=evidence,
            model_usage=result.model_usage,
            decision="approve" if evidence.can_proceed_to_strategy else "block",
            reason=evidence.synthesis,
            summary="Evidence was synthesized into planning rules, resource needs, Calendar reality, and explicit gaps.",
            status="approved" if evidence.can_proceed_to_strategy else "blocked",
            input_artifact_types=("user_goal_model",),
        )
        self.persistence.update(
            state["session_id"],
            status=state["status"],
            business_status=state["business_status"],
            runtime_status=state["runtime_status"],
            evidence_pack=evidence,
            cognitive_metadata=self._metadata(
                mode="model_backed",
                stage="context_evidence",
                confidence=evidence.confidence,
                rules=rules,
                repair_count=int(state.get("repair_count", 0)),
            ),
            clear=("strategy_portfolio", "execution_blueprint", "critique_report") if not evidence.can_proceed_to_strategy else (),
        )
        if evidence.can_proceed_to_strategy:
            self._handoff(state, self.evidence_agent.name, self.strategy_agent.name, "Evidence is sufficient to compare planning strategies.")
        else:
            questions = [item.description for item in evidence.gaps if item.proposed_resolution == "ask_user"][:3]
            if questions:
                state["conversation_history"] = self.persistence.append_assistant_turn(
                    state["session_id"],
                    "\n".join(questions),
                )
        return state

    def strategy_architect_node(self, state: CognitivePlanningState) -> CognitivePlanningState:
        goal = state.get("goal_model")
        evidence = state.get("evidence_pack")
        if not goal or not evidence:
            return state
        feedback = state.get("user_input") if state.get("user_action") == "revise_strategy" else None
        try:
            strategy_kwargs = {"previous": state.get("strategy_portfolio"), "feedback": feedback}
            if state.get("reality_assessment") is not None:
                strategy_kwargs["reality"] = state.get("reality_assessment")
            result = self.strategy_agent.run(goal, evidence, **strategy_kwargs)
        except PlanningModelUnavailable as exc:
            return self._block_model(state, agent=self.strategy_agent.name, error=exc.error)
        strategy = result.artifact
        state["strategy_portfolio"] = strategy
        state["status"] = "waiting_design_approval"
        state["business_status"] = "strategy_pending"
        state["runtime_status"] = "idle"
        state.pop("execution_blueprint", None)
        state.pop("critique_report", None)
        if not state.get("repair_loop"):
            state.pop("approved_strategy_id", None)
            state["repair_count"] = 0
        self._record_artifact(
            state,
            agent=self.strategy_agent.name,
            artifact_type=self.strategy_agent.artifact_type,
            artifact=strategy,
            model_usage=result.model_usage,
            decision="request_user_input",
            reason=strategy.recommendation_reason,
            summary="A strategy portfolio is ready. Execution remains blocked until the user explicitly approves a direction.",
            input_artifact_types=("user_goal_model", "evidence_pack", "strategy_portfolio"),
        )
        self.persistence.update(
            state["session_id"],
            status="waiting_design_approval",
            business_status="strategy_pending",
            runtime_status="idle",
            strategy_portfolio=strategy,
            repair_count=int(state.get("repair_count", 0)),
            cognitive_metadata=self._metadata(
                mode="model_backed",
                stage="strategy_architecture",
                rules=[item.rule for item in evidence.planning_rules],
                repair_count=int(state.get("repair_count", 0)),
            ),
            clear=("execution_blueprint", "critique_report", "approved_strategy_id") if not state.get("repair_loop") else ("execution_blueprint", "critique_report"),
        )
        return state

    def _approved_strategy(self, state: CognitivePlanningState):
        portfolio = state.get("strategy_portfolio")
        approved_id = state.get("approved_strategy_id")
        if not portfolio or not approved_id:
            return None
        return next((item for item in portfolio.strategies if item.id == approved_id), None)

    def execution_designer_node(self, state: CognitivePlanningState) -> CognitivePlanningState:
        goal = state.get("goal_model")
        evidence = state.get("evidence_pack")
        strategy = self._approved_strategy(state)
        if not goal or not evidence or not strategy:
            state["status"] = "waiting_design_approval"
            state["business_status"] = "strategy_pending"
            state["runtime_status"] = "idle"
            return state
        repair = state.pop("repair_instructions", [])
        try:
            execution_kwargs = {"repair_instructions": repair}
            if state.get("reality_assessment") is not None:
                execution_kwargs["reality"] = state.get("reality_assessment")
            result = self.execution_agent.run(goal, evidence, strategy, **execution_kwargs)
        except PlanningModelUnavailable as exc:
            return self._block_model(state, agent=self.execution_agent.name, error=exc.error)
        execution = result.artifact
        state["execution_blueprint"] = execution
        state["business_status"] = "execution_pending"
        state["runtime_status"] = "running"
        self._record_artifact(
            state,
            agent=self.execution_agent.name,
            artifact_type=self.execution_agent.artifact_type,
            artifact=execution,
            model_usage=result.model_usage,
            decision="produce_artifact",
            reason=execution.narrative.execution_logic,
            summary="Execution Designer produced concrete actions, dependencies, completion evidence, resources, and fallback actions.",
            input_artifact_types=("user_goal_model", "evidence_pack", "strategy_portfolio", "execution_blueprint"),
        )
        self.persistence.update(
            state["session_id"],
            business_status="execution_pending",
            runtime_status="running",
            execution_blueprint=execution,
            cognitive_metadata=self._metadata(
                mode="model_backed",
                stage="execution_design",
                repair_count=int(state.get("repair_count", 0)),
            ),
            clear=("critique_report",),
        )
        self._handoff(state, self.execution_agent.name, self.critic_agent.name, "The draft execution blueprint requires independent semantic review.")
        return state

    def independent_critic_node(self, state: CognitivePlanningState) -> CognitivePlanningState:
        goal = state.get("goal_model")
        evidence = state.get("evidence_pack")
        strategy = state.get("strategy_portfolio")
        execution = state.get("execution_blueprint")
        if not goal or not evidence or not strategy or not execution:
            return state
        try:
            critique_kwargs = {}
            if state.get("reality_assessment") is not None:
                critique_kwargs["reality"] = state.get("reality_assessment")
            result = self.critic_agent.critique(goal, evidence, strategy, execution, **critique_kwargs)
        except PlanningModelUnavailable as exc:
            return self._block_model(state, agent=self.critic_agent.name, error=exc.error)
        critique = result.artifact
        if critique.status == "passed" and (
            any(item.severity == "blocker" for item in critique.issues) or critique.repair_requests
        ):
            critique = critique.model_copy(
                update={
                    "status": "needs_repair" if int(state.get("repair_count", 0)) < 2 else "blocked",
                    "calendar_writable": False,
                    "remaining_risks": [
                        *critique.remaining_risks,
                        "Critic output was internally inconsistent: passed status included blocking issues or repair requests.",
                    ],
                }
            )
        elif critique.status == "passed" and not critique.calendar_writable:
            critique = critique.model_copy(
                update={
                    "status": "blocked",
                    "calendar_writable": False,
                    "remaining_risks": [
                        *critique.remaining_risks,
                        "Critic output was internally inconsistent: passed status was not Calendar writable.",
                    ],
                }
            )
        elif critique.status != "passed" and critique.calendar_writable:
            critique = critique.model_copy(update={"calendar_writable": False})
        try:
            validate_execution_invariants(execution)
        except DeterministicGuardError as exc:
            critique = critique.model_copy(
                update={
                    "status": "needs_repair" if int(state.get("repair_count", 0)) < 2 else "blocked",
                    "calendar_writable": False,
                    "remaining_risks": [*critique.remaining_risks, *exc.issues],
                    "issues": [
                        *critique.issues,
                        *[
                            CritiqueIssue(
                                severity="blocker",
                                description=issue,
                                evidence="deterministic execution guard",
                                responsibleAgent="execution_designer",
                            )
                            for issue in exc.issues
                        ],
                    ],
                    "repair_requests": critique.repair_requests
                    or [
                        CriticRepairRequest(
                            targetAgent="execution_designer",
                            instruction="Repair deterministic execution invariants: " + "; ".join(exc.issues),
                            expectedChange="All task ids, dependencies, dates, action steps, evidence, resources, and fallbacks pass schema guards.",
                        )
                    ],
                }
            )
        state["critique_report"] = critique
        review_passed = critique.status == "passed" and critique.calendar_writable
        state["status"] = "waiting_execution_approval" if review_passed else "execution_revision"
        state["business_status"] = "execution_pending"
        state["runtime_status"] = "idle"
        self._record_artifact(
            state,
            agent=self.critic_agent.name,
            artifact_type=self.critic_agent.critique_artifact_type,
            artifact=critique,
            model_usage=result.model_usage,
            decision="approve" if critique.status == "passed" and critique.calendar_writable else "request_agent_revision" if critique.status == "needs_repair" else "block",
            reason=critique.simulation_summary,
            summary="Independent Critic approved the blueprint." if critique.status == "passed" else "Independent Critic found issues that must be repaired before approval or Calendar write.",
            status="approved" if critique.status == "passed" else "needs_revision" if critique.status == "needs_repair" else "blocked",
            input_artifact_types=("user_goal_model", "evidence_pack", "strategy_portfolio", "execution_blueprint", "critique_report"),
        )
        self.persistence.update(
            state["session_id"],
            status=state["status"],
            business_status="execution_pending",
            runtime_status="idle",
            critique_report=critique,
            repair_count=int(state.get("repair_count", 0)),
            cognitive_metadata=self._metadata(
                mode="model_backed",
                stage="plan_critique",
                confidence=critique.confidence,
                repair_count=int(state.get("repair_count", 0)),
            ),
        )
        return state

    def repair_router_node(self, state: CognitivePlanningState) -> CognitivePlanningState:
        update = state.get("learning_update")
        critique = state.get("critique_report")
        if update and update.current_plan_patch:
            target = update.current_plan_patch.target_artifact
            instructions = [{"instruction": update.current_plan_patch.instruction}]
            state.pop("learning_update", None)
        elif critique and critique.repair_requests:
            target = critique.repair_requests[0].target_agent
            instructions = [item.model_dump(by_alias=True) for item in critique.repair_requests]
        else:
            state["next_node"] = "__end__"
            return state
        if update is None:
            count = min(2, int(state.get("repair_count", 0)) + 1)
            state["repair_count"] = count
            state["repair_loop"] = True
            self.persistence.update(state["session_id"], repair_count=count)
        if target in {"execution_blueprint", "execution", "execution_designer", "resource", "schedule"}:
            state["repair_instructions"] = instructions
            state["next_node"] = "execution_designer"
        elif target in {"strategy_portfolio", "strategy", "strategy_architect"}:
            state["user_action"] = "revise_strategy"
            state["user_input"] = instructions[0].get("instruction", "Revise the strategy.")
            state["repair_loop"] = update is None
            state["next_node"] = "strategy_architect"
        elif target in {"evidence_pack", "context_evidence", "evidence"}:
            state["next_node"] = "context_evidence"
        elif target in {"reality_assessment", "reality"}:
            state["next_node"] = "reality"
        elif target in {"user_goal_model", "goal_modeling", "goal_intelligence"}:
            state["next_node"] = "goal_modeling"
        else:
            state["next_node"] = "__end__"
        return state

    def execution_approval_node(self, state: CognitivePlanningState) -> CognitivePlanningState:
        execution = state.get("execution_blueprint")
        critique = state.get("critique_report")
        try:
            if execution:
                validate_execution_invariants(execution)
        except DeterministicGuardError as exc:
            raise HTTPException(status_code=422, detail={"message": "execution blueprint failed deterministic guards", "issues": exc.issues}) from exc
        allowed = calendar_write_allowed(
            planning_mode=state.get("planning_mode", "blocked_model_unavailable"),
            critique=critique,
            strategy_approved=bool(state.get("approved_strategy_id")),
            execution_approved=True,
        )
        if not allowed:
            raise HTTPException(status_code=422, detail={"message": "execution plan has not passed the independent critic"})
        state["status"] = "ready_to_write_calendar"
        state["business_status"] = "calendar_pending"
        state["runtime_status"] = "idle"
        self.persistence.update(
            state["session_id"],
            status="ready_to_write_calendar",
            business_status="calendar_pending",
            runtime_status="idle",
            cognitive_metadata=self._metadata(
                mode="model_backed",
                stage="waiting_calendar_write",
                confidence=critique.confidence if critique else None,
                repair_count=int(state.get("repair_count", 0)),
            ),
        )
        self.agent_runtime.record_decision(
            state["session_id"],
            agent=self.execution_agent.name,
            decision="approve",
            reason="The user approved an execution blueprint that passed the independent critic.",
            summary="Execution is confirmed and can now enter the Calendar PermissionGate.",
            confidence=1,
            input_artifact_ids=self._latest_artifact_ids(
                state["session_id"],
                ("strategy_portfolio", "execution_blueprint", "critique_report"),
            ),
        )
        return state

    def feedback_learning_node(self, state: CognitivePlanningState) -> CognitivePlanningState:
        try:
            learning_kwargs = {
                "goal": state.get("goal_model"),
                "evidence": state.get("evidence_pack"),
                "strategy": state.get("strategy_portfolio"),
                "execution": state.get("execution_blueprint"),
                "critique": state.get("critique_report"),
            }
            if state.get("reality_assessment") is not None:
                learning_kwargs["reality"] = state.get("reality_assessment")
            result = self.critic_agent.learn(state.get("user_input", ""), **learning_kwargs)
        except PlanningModelUnavailable as exc:
            return self._block_model(state, agent=self.critic_agent.name, error=exc.error)
        update = result.artifact
        state["learning_update"] = update
        state["status"] = "learning_from_feedback"
        state["business_status"] = "execution_pending"
        state["runtime_status"] = "running"
        if update.current_plan_patch:
            state["repair_count"] = 0
        self._record_artifact(
            state,
            agent=self.critic_agent.name,
            artifact_type=self.critic_agent.learning_artifact_type,
            artifact=update,
            model_usage=result.model_usage,
            decision="request_agent_revision" if update.current_plan_patch else "produce_artifact",
            reason=update.diagnosis.root_cause,
            summary="Feedback was diagnosed into a responsible stage, current-plan patch, and evidence-based learning hypothesis.",
            input_artifact_types=("user_goal_model", "evidence_pack", "strategy_portfolio", "execution_blueprint", "critique_report", "planning_learning_update"),
        )
        self._persist_learning_hypothesis(state, update)
        self.persistence.update(
            state["session_id"],
            status="learning_from_feedback",
            business_status="execution_pending",
            runtime_status="running",
            planning_learning_update=update,
            repair_count=int(state.get("repair_count", 0)),
            cognitive_metadata=self._metadata(
                mode="model_backed",
                stage="feedback_learning",
                repair_count=int(state.get("repair_count", 0)),
            ),
        )
        return state

    def _persist_learning_hypothesis(
        self,
        state: CognitivePlanningState,
        update: PlanningLearningUpdate,
    ) -> None:
        """Route every automatic long-term rule through Memory Evaluation."""

        self.harness.evaluate_memory_candidate(
            state["session_id"],
            learning_update=update,
            memory_repository=self.hypotheses,
        )

    def calendar_gate_node(self, state: CognitivePlanningState) -> CognitivePlanningState:
        execution = state.get("execution_blueprint")
        critique = state.get("critique_report")
        if state.get("status") != "ready_to_write_calendar":
            raise HTTPException(status_code=409, detail={"message": "execution plan must be explicitly approved first"})
        try:
            if not execution:
                raise DeterministicGuardError(["execution blueprint is missing"])
            validate_execution_invariants(execution)
            undated = [task.id for task in execution.tasks if not task.scheduled_date]
            if undated:
                raise DeterministicGuardError([f"tasks need scheduledDate before Calendar write: {', '.join(undated)}"])
        except DeterministicGuardError as exc:
            raise HTTPException(status_code=422, detail={"message": "calendar write gate blocked", "issues": exc.issues}) from exc
        if not calendar_write_allowed(
            planning_mode=state.get("planning_mode", "blocked_model_unavailable"),
            critique=critique,
            strategy_approved=bool(state.get("approved_strategy_id")),
            execution_approved=True,
        ):
            raise HTTPException(status_code=422, detail={"message": "only a model-backed, critic-passed plan can be written to Calendar"})
        state["status"] = "waiting_calendar_write_approval"
        state["business_status"] = "calendar_pending"
        state["runtime_status"] = "idle"
        self.persistence.update(
            state["session_id"],
            status="waiting_calendar_write_approval",
            business_status="calendar_pending",
            runtime_status="idle",
            cognitive_metadata=self._metadata(
                mode="model_backed",
                stage="calendar_permission_gate",
                confidence=critique.confidence if critique else None,
                repair_count=int(state.get("repair_count", 0)),
            ),
        )
        return state

    # Compatibility facade
    def create_session(self, payload: CreatePlanningSessionRequest) -> PlanningSessionResponse:
        session_id = self.persistence.create(
            thread_id=payload.thread_id or "",
            user_input=payload.user_input,
            context=payload.context,
        )
        row = self.persistence.get_row(session_id)
        self.persistence.update(session_id, runtime_status="running")
        row = self.persistence.get_row(session_id)
        state = self._state_from_row(row, action="create", user_input=payload.user_input)
        return self._invoke(state)

    def clarify(self, session_id: str, payload: PlanningSessionTextRequest) -> PlanningSessionResponse:
        control_intent = detect_planning_control_intent(payload.text)
        if control_intent == "skip_current_stage":
            skip = getattr(self, "skip_current_stage", None)
            if not callable(skip):
                raise HTTPException(status_code=409, detail={"message": "this planning runtime cannot skip goal clarification"})
            return skip(session_id)
        if control_intent == "continue_current_stage":
            return self.continue_current_stage(session_id)
        if control_intent in {"cancel_planning", "restart_planning"}:
            return self.cancel(session_id)
        if control_intent == "approve_current_stage":
            current = self.get_session(session_id)
            if current.status in {"waiting_design_approval", "design_revision"}:
                return self.approve_design(session_id)
            if current.status == "waiting_execution_approval":
                return self.approve_execution(session_id)
            return self.continue_current_stage(session_id)
        if control_intent == "modify_current_stage":
            return self.get_session(session_id)
        history = self.persistence.append_user_turn(session_id, payload.text)
        row = self.persistence.get_row(session_id)
        if not row:
            raise HTTPException(status_code=404, detail={"message": "planning session not found"})
        state = self._state_from_row(row, action="answer_question", user_input=payload.text)
        state["runtime_status"] = "running"
        state["planning_mode"] = "model_backed"
        self.persistence.update(session_id, runtime_status="running")
        state["conversation_history"] = history
        return self._invoke(state)

    def continue_current_stage(self, session_id: str) -> PlanningSessionResponse:
        row = self.persistence.get_row(session_id)
        if not row:
            raise HTTPException(status_code=404, detail={"message": "planning session not found"})
        if row["status"] in {"cancelled", "written_to_calendar"}:
            return self.adapter.from_row(row)
        state = self._state_from_row(row, action="continue_current_stage")
        if (
            not state.get("evidence_requires_authority_refresh")
            and state.get("runtime_status") == "idle"
            and row["status"] in {
            "waiting_design_approval",
            "waiting_execution_approval",
            "ready_to_write_calendar",
            "waiting_calendar_write_approval",
            }
        ):
            return self.adapter.from_row(row)
        state["runtime_status"] = "running"
        state["planning_mode"] = "model_backed"
        self.persistence.update(session_id, runtime_status="running")
        return self._invoke(state)

    def cancel(self, session_id: str) -> PlanningSessionResponse:
        row = self.persistence.get_row(session_id)
        if not row:
            raise HTTPException(status_code=404, detail={"message": "planning session not found"})
        self.persistence.mark_cancelled(session_id)
        return self.get_session(session_id)

    def revise_design(self, session_id: str, payload: PlanningSessionTextRequest) -> PlanningSessionResponse:
        self.persistence.append_user_turn(session_id, payload.text)
        row = self.persistence.get_row(session_id)
        if not row:
            raise HTTPException(status_code=404, detail={"message": "planning session not found"})
        return self._invoke(self._state_from_row(row, action="give_feedback", user_input=payload.text))

    def approve_design(self, session_id: str) -> PlanningSessionResponse:
        row = self.persistence.get_row(session_id)
        if not row:
            raise HTTPException(status_code=404, detail={"message": "planning session not found"})
        resumed = self._resume_if_legacy_evidence(row)
        if resumed is not None:
            return resumed
        if row["status"] != "waiting_design_approval" or not json_object(row["strategy_portfolio_json"]):
            raise HTTPException(status_code=409, detail={"message": "strategy is not waiting for approval"})
        portfolio = StrategyPortfolio.model_validate(json_object(row["strategy_portfolio_json"]))
        self.harness.record_approval(session_id, "strategy")
        approved_strategy_id = portfolio.recommended_strategy_id
        self.persistence.update(session_id, approved_strategy_id=approved_strategy_id)
        row = self.persistence.get_row(session_id)
        state = self._state_from_row(row, action="approve_strategy")
        self.agent_runtime.record_decision(
            session_id,
            agent=self.strategy_agent.name,
            decision="approve",
            reason="The user explicitly approved the recommended strategy.",
            summary="The strategy gate passed; execution design may begin.",
            confidence=1,
            input_artifact_ids=self._latest_artifact_ids(session_id, ("strategy_portfolio",)),
        )
        self._handoff(state, self.strategy_agent.name, self.execution_agent.name, "The user explicitly approved the recommended strategy.")
        return self._invoke(state)

    def approve_execution(self, session_id: str, *, accept_missing_resources: bool = False) -> PlanningSessionResponse:
        row = self.persistence.get_row(session_id)
        if not row:
            raise HTTPException(status_code=404, detail={"message": "planning session not found"})
        resumed = self._resume_if_legacy_evidence(row)
        if resumed is not None:
            return resumed
        if row["status"] != "waiting_execution_approval":
            raise HTTPException(status_code=409, detail={"message": "execution plan is not waiting for approval"})
        state = self._state_from_row(row, action="approve_execution")
        critic_policy = self.harness.critic_policy(
            session_id,
            critique_report=state.get("critique_report"),
        )
        if not critic_policy.allowed:
            raise HTTPException(
                status_code=409,
                detail={"message": "current Execution artifact has not passed the independent Critic"},
            )
        self.harness.record_approval(session_id, "execution")
        return self._invoke(state)

    def revise_execution(self, session_id: str, payload: PlanningSessionTextRequest) -> PlanningSessionResponse:
        self.persistence.append_user_turn(session_id, payload.text)
        row = self.persistence.get_row(session_id)
        if not row:
            raise HTTPException(status_code=404, detail={"message": "planning session not found"})
        return self._invoke(self._state_from_row(row, action="give_feedback", user_input=payload.text))

    def submit_feedback(self, session_id: str, payload: PlanningSessionTextRequest) -> PlanningSessionResponse:
        return self.revise_execution(session_id, payload)

    def prepare_calendar_write(self, session_id: str, *, accept_missing_resources: bool = False) -> PlanningSessionResponse:
        row = self.persistence.get_row(session_id)
        if not row:
            raise HTTPException(status_code=404, detail={"message": "planning session not found"})
        resumed = self._resume_if_legacy_evidence(row)
        if resumed is not None:
            return resumed
        if row["status"] != "ready_to_write_calendar":
            raise HTTPException(
                status_code=409,
                detail={"message": "execution plan must be approved before Calendar preparation"},
            )
        return self._invoke(self._state_from_row(row, action="write_calendar"))

    def approve_calendar_write(
        self,
        session_id: str,
        *,
        execution_artifact_ref: dict | None = None,
    ) -> None:
        row = self.persistence.get_row(session_id)
        if not row:
            raise HTTPException(status_code=404, detail={"message": "planning session not found"})
        if self._state_from_row(row, action="continue_current_stage").get(
            "evidence_requires_authority_refresh"
        ):
            raise HTTPException(
                status_code=409,
                detail={"message": "Evidence authority refresh is required before Calendar approval"},
            )
        if row["status"] != "waiting_calendar_write_approval":
            raise HTTPException(status_code=409, detail={"message": "Calendar write is not waiting for approval"})
        if not execution_artifact_ref:
            raise HTTPException(status_code=409, detail={"message": "Calendar action is not bound to an Execution artifact"})
        try:
            self.harness.assert_current_artifact(
                session_id,
                kind="execution_blueprint",
                expected_ref=execution_artifact_ref,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail={"message": str(exc)}) from exc
        state = self._state_from_row(row, action="write_calendar")
        decision = self.harness.calendar_write_policy(
            session_id,
            planning_mode=str(state.get("planning_mode") or "blocked_model_unavailable"),
            critique_report=state.get("critique_report"),
        )
        blockers = [gate for gate in decision.failed_gates if gate != "calendar_approval"]
        if blockers:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Calendar approval is stale or upstream planning gates failed",
                    "failedGates": blockers,
                },
            )
        self.harness.record_approval(session_id, "calendar")

    def assert_calendar_write_allowed(
        self,
        session_id: str,
        *,
        execution_artifact_ref: dict | None = None,
    ) -> None:
        row = self.persistence.get_row(session_id)
        if not row:
            raise HTTPException(status_code=404, detail={"message": "planning session not found"})
        if self._state_from_row(row, action="continue_current_stage").get(
            "evidence_requires_authority_refresh"
        ):
            raise HTTPException(
                status_code=409,
                detail={"message": "Evidence authority refresh is required before Calendar write"},
            )
        if not execution_artifact_ref:
            raise HTTPException(status_code=409, detail={"message": "Calendar action is not bound to an Execution artifact"})
        try:
            self.harness.assert_current_artifact(
                session_id,
                kind="execution_blueprint",
                expected_ref=execution_artifact_ref,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail={"message": str(exc)}) from exc
        state = self._state_from_row(row, action="write_calendar")
        decision = self.harness.calendar_write_policy(
            session_id,
            planning_mode=str(state.get("planning_mode") or "blocked_model_unavailable"),
            critique_report=state.get("critique_report"),
        )
        if not decision.allowed:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Calendar write failed the Harness policy gate",
                    "failedGates": list(decision.failed_gates),
                },
            )

    def latest_for_thread(self, thread_id: str) -> PlanningSessionResponse | None:
        row = self.persistence.latest_active(thread_id)
        return self.adapter.from_row(row) if row else None

    def get_session(self, session_id: str) -> PlanningSessionResponse:
        row = self.persistence.get_row(session_id)
        if not row:
            raise HTTPException(status_code=404, detail={"message": "planning session not found"})
        return self.adapter.from_row(row)

    def mark_calendar_written(
        self,
        session_id: str,
        *,
        execution_artifact_ref: dict | None = None,
    ) -> None:
        self.assert_calendar_write_allowed(
            session_id,
            execution_artifact_ref=execution_artifact_ref,
        )
        self.persistence.mark_written(session_id)
        self.harness.consume_calendar_approval(session_id)

    def execution_to_structured_plan(self, session: PlanningSessionResponse) -> dict[str, Any]:
        if not session.execution_blueprint or not session.goal_model:
            raise HTTPException(status_code=422, detail={"message": "cognitive execution blueprint is missing"})
        execution = ExecutionBlueprint.model_validate(session.execution_blueprint)
        goal = UserGoalModel.model_validate(session.goal_model)
        today = date.today()
        task_dates = []
        tasks: list[dict[str, Any]] = []
        for index, task in enumerate(execution.tasks):
            due = task.scheduled_date or (today + timedelta(days=index)).isoformat()
            task_dates.append(due)
            tasks.append(
                {
                    "title": task.title,
                    "description": task.purpose,
                    "estimatedMinutes": task.estimated_minutes,
                    "dueDate": due,
                    "priority": "high" if task.difficulty == "high" else "low" if task.difficulty == "low" else "medium",
                    "sourceKey": f"planning-session:{session.session_id}:t{index}",
                }
            )
        duration = 1
        if task_dates:
            parsed = sorted(date.fromisoformat(value) for value in task_dates)
            duration = max(1, (parsed[-1] - parsed[0]).days + 1)
        return {
            "goalTitle": goal.goal_statement,
            "goalDescription": goal.desired_change,
            "durationDays": duration,
            "milestones": [
                {
                    "title": "Approved execution blueprint",
                    "description": execution.narrative.execution_logic,
                    "tasks": tasks,
                }
            ],
            "reviewPlan": {
                "frequency": "weekly",
                "questions": [question for checkpoint in execution.checkpoints for question in checkpoint.questions][:6],
            },
        }
