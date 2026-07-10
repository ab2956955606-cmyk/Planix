from __future__ import annotations

from typing import Any

from ....schemas import CognitivePlanningMetadata, PendingPlanningQuestion, PlanningSessionResponse, UserNeedContract
from ...planning_agent_runtime import PlanningAgentRuntime
from ..contracts import (
    EvidencePack,
    ExecutionBlueprint,
    PlanCritiqueReport,
    PlanningLearningUpdate,
    RealityAssessment,
    StrategyPortfolio,
    UserGoalModel,
)
from ..orchestration.persistence import json_object
from .legacy_schema_adapter import (
    evidence_to_memory,
    evidence_to_resources,
    execution_to_draft,
    goal_to_contract,
    learning_to_patch,
    strategy_to_design,
)


class SessionApiAdapter:
    def __init__(self, agent_runtime: PlanningAgentRuntime | None = None):
        self.agent_runtime = agent_runtime or PlanningAgentRuntime()

    def from_row(self, row) -> PlanningSessionResponse:
        goal_raw = json_object(row["goal_model_json"])
        evidence_raw = json_object(row["evidence_pack_json"])
        reality_raw = json_object(row["reality_assessment_json"]) if "reality_assessment_json" in row.keys() else {}
        strategy_raw = json_object(row["strategy_portfolio_json"])
        execution_raw = json_object(row["execution_blueprint_json"])
        critique_raw = json_object(row["critique_report_json"])
        learning_raw = json_object(row["planning_learning_update_json"])
        metadata_raw = json_object(row["cognitive_metadata_json"])

        goal = UserGoalModel.model_validate(goal_raw) if goal_raw else None
        evidence = EvidencePack.model_validate(evidence_raw) if evidence_raw else None
        reality = RealityAssessment.model_validate(reality_raw) if reality_raw else None
        strategy = StrategyPortfolio.model_validate(strategy_raw) if strategy_raw else None
        execution = ExecutionBlueprint.model_validate(execution_raw) if execution_raw else None
        critique = PlanCritiqueReport.model_validate(critique_raw) if critique_raw else None
        learning = PlanningLearningUpdate.model_validate(learning_raw) if learning_raw else None
        metadata = CognitivePlanningMetadata.model_validate(metadata_raw) if metadata_raw else None

        design_approved = bool(execution or row["status"] in {"waiting_execution_approval", "ready_to_write_calendar", "waiting_calendar_write_approval", "written_to_calendar"})
        execution_approved = row["status"] in {"ready_to_write_calendar", "waiting_calendar_write_approval", "written_to_calendar"}
        contract = goal_to_contract(goal, row["user_input"]) if goal else None
        memory = evidence_to_memory(evidence) if evidence else None
        resources = evidence_to_resources(evidence, goal.domain if goal else "") if evidence else None
        design = strategy_to_design(strategy, goal, approved=design_approved) if strategy and goal else None
        draft = execution_to_draft(execution, strategy, critique, approved=execution_approved) if execution and strategy else None
        patch = learning_to_patch(learning) if learning else None
        if contract and evidence and not evidence.can_proceed_to_strategy:
            gaps = [item.description for item in evidence.gaps]
            questions = [item.description for item in evidence.gaps if item.proposed_resolution == "ask_user"][:3]
            contract = contract.model_copy(
                update={
                    "can_move_to_design": False,
                    "missing_information": [*contract.missing_information, *gaps],
                    "clarification_questions": questions or contract.clarification_questions,
                    "pending_question": PendingPlanningQuestion(
                        askedFields=["evidence_gap"],
                        expectedAnswerType="evidence_gap",
                        questionText=(questions or gaps or ["More evidence is required before strategy design."])[0],
                        questions=questions or gaps[:3],
                    ),
                }
            )
        if not contract:
            legacy_contract = json_object(row["user_need_contract_json"])
            contract = UserNeedContract.model_validate(legacy_contract) if legacy_contract else None
        if contract and metadata and metadata.planning_mode == "blocked_model_unavailable":
            contract = contract.model_copy(update={"can_move_to_design": False})

        return PlanningSessionResponse(
            sessionId=row["id"],
            threadId=row["thread_id"],
            entryPoint=row["entry_point"],
            status=row["status"],
            userInput=row["user_input"],
            userNeedContract=contract,
            pendingQuestion=contract.pending_question if contract else None,
            memoryInsight=memory,
            resourceBrief=resources,
            designProposal=design,
            executionDraft=draft,
            learningPatch=patch,
            cognitiveMetadata=metadata,
            goalModel=goal_raw or None,
            realityAssessment=reality.model_dump(by_alias=True) if reality else None,
            evidencePack=evidence_raw or None,
            strategyPortfolio=strategy_raw or None,
            executionBlueprint=execution_raw or None,
            critiqueReport=critique_raw or None,
            planningLearningUpdate=learning_raw or None,
            approvedStrategyId=(row["approved_strategy_id"] or None) if "approved_strategy_id" in row.keys() else None,
            artifacts=self.agent_runtime.list_artifacts(row["id"]),
            decisions=self.agent_runtime.list_decisions(row["id"]),
            messages=self.agent_runtime.list_messages(row["id"]),
            version=int(row["version"] or 1),
            createdAt=row["created_at"],
            updatedAt=row["updated_at"],
        )
