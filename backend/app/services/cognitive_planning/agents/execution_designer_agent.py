from __future__ import annotations

from typing import Any

from ..contracts import (
    EvidencePack,
    ExecutionBlueprint,
    ExecutionNarrative,
    StrategyOption,
    UserGoalModel,
)
from .base import AgentResult, CognitiveModelClient


NARRATIVE_SYSTEM = """
You are Planix Execution Designer Agent. First explain the execution logic for the user-approved strategy:
dependencies, workload rhythm, checkpoints, buffers, risks, and why this sequence is feasible. This is a
cross-domain execution narrative, not a task template. Return only the requested JSON.
""".strip()


BLUEPRINT_SYSTEM = """
You are Planix Execution Designer Agent. Compile the approved strategy and execution narrative into a concrete
cross-domain action system. Every task must say what to do, why now, exact action steps, completion evidence,
deliverable, relevant resources with exact usage, dependencies, risks, and a fallback action. Respect time and
Calendar reality. Use domainExtensions for domain-specific facts instead of universal fields. Never use generic
template task titles such as '学习并复现', '完成一个可检查产出', '确认基础与最小路径', '项目驱动练习', or
'包装与复盘' unless the title names a concrete object and deliverable. Return only the requested JSON.
""".strip()


class ExecutionDesignerAgent:
    name = "Execution Designer Agent"
    artifact_type = "execution_blueprint"

    def __init__(self, model: CognitiveModelClient | None = None):
        self.model = model or CognitiveModelClient()

    def run(
        self,
        goal: UserGoalModel,
        evidence: EvidencePack,
        strategy: StrategyOption,
        *,
        repair_instructions: list[dict[str, Any]] | None = None,
    ) -> AgentResult[ExecutionBlueprint]:
        common = {
            "goalModel": goal.model_dump(by_alias=True),
            "evidencePack": evidence.model_dump(by_alias=True),
            "approvedStrategy": strategy.model_dump(by_alias=True),
            "repairInstructions": repair_instructions or [],
        }
        narrative_result = self.model.complete_contract(
            stage="execution_narrative",
            task_type="planning_execution",
            feature="cognitive_execution_narrative",
            system=NARRATIVE_SYSTEM,
            payload=common,
            contract_type=ExecutionNarrative,
            temperature=0.2,
        )
        blueprint_result = self.model.complete_contract(
            stage="execution_design",
            task_type="planning_execution",
            feature="cognitive_execution_blueprint",
            system=BLUEPRINT_SYSTEM,
            payload={**common, "executionNarrative": narrative_result.artifact.model_dump(by_alias=True)},
            contract_type=ExecutionBlueprint,
            temperature=0.2,
        )
        usage = dict(blueprint_result.model_usage)
        prior_usage = narrative_result.model_usage
        for key in ("promptTokens", "completionTokens", "totalTokens", "latencyMs"):
            prior_value = prior_usage.get(key)
            current_value = usage.get(key)
            if prior_value is not None or current_value is not None:
                usage[key] = int(prior_value or 0) + int(current_value or 0)
        usage["attempts"] = [*(prior_usage.get("attempts") or []), *(usage.get("attempts") or [])]
        usage["fallbackUsed"] = bool(prior_usage.get("fallbackUsed") or usage.get("fallbackUsed"))
        usage["localFallbackAllowed"] = False
        return AgentResult(blueprint_result.artifact, usage)
