from __future__ import annotations

from typing import Any

from ...services.cognitive_planning.contracts import (
    EvidencePack,
    ExecutionBlueprint,
    ExecutionNarrative,
    StrategyOption,
)
from ..contracts import GoalUnderstandingArtifact, RealityAssessment
from .base import AgentResult, CognitiveModelClient


NARRATIVE_SYSTEM = """
You are Planix Execution Agent. Explain how the user-approved strategy becomes a feasible sequence in this
specific domain: dependencies, workload, checkpoints, buffers, risks, and the reason for the order. Do not use
a reusable stage template. Return only the requested JSON.
""".strip()


BLUEPRINT_SYSTEM = """
You are Planix Execution Agent. Turn the approved strategy into concrete actions. Every task must answer:
what exactly to do, why it must happen now, how completion is proved, and what to do if it fails. Include
dependencies, a checkable deliverable, credible resources with exact usage, and realistic time placement.
Use domainExtensions for facts unique to this plan. Never use filler titles such as '学习并复现', '完成产出',
'基础阶段', '提高阶段', or '项目驱动练习'. Do not invent URLs or present AI-generated material as an
external source. Return only the requested JSON.
""".strip()


class ExecutionAgent:
    name = "Execution Agent"
    artifact_type = "execution_blueprint"

    def __init__(self, model: CognitiveModelClient | None = None):
        self.model = model or CognitiveModelClient()

    def run(
        self,
        goal: GoalUnderstandingArtifact,
        evidence: EvidencePack,
        strategy: StrategyOption,
        *,
        reality: RealityAssessment | None = None,
        repair_instructions: list[dict[str, Any]] | None = None,
    ) -> AgentResult[ExecutionBlueprint]:
        common = {
            "goalModel": goal.model_dump(by_alias=True),
            "realityAssessment": reality.model_dump(by_alias=True) if reality else None,
            "evidencePack": evidence.model_dump(by_alias=True),
            "approvedStrategy": strategy.model_dump(by_alias=True),
            "repairInstructions": repair_instructions or [],
        }
        narrative = self.model.complete_contract(
            stage="execution_narrative",
            task_type="planning_execution",
            feature="cognitive_os_execution_narrative",
            system=NARRATIVE_SYSTEM,
            payload=common,
            contract_type=ExecutionNarrative,
            temperature=0.2,
        )
        blueprint = self.model.complete_contract(
            stage="execution_design",
            task_type="planning_execution",
            feature="cognitive_os_execution_blueprint",
            system=BLUEPRINT_SYSTEM,
            payload={**common, "executionNarrative": narrative.artifact.model_dump(by_alias=True)},
            contract_type=ExecutionBlueprint,
            temperature=0.2,
        )
        usage = dict(blueprint.model_usage)
        for key in ("promptTokens", "completionTokens", "totalTokens", "latencyMs"):
            if narrative.model_usage.get(key) is not None or usage.get(key) is not None:
                usage[key] = int(narrative.model_usage.get(key) or 0) + int(usage.get(key) or 0)
        usage["attempts"] = [*(narrative.model_usage.get("attempts") or []), *(usage.get("attempts") or [])]
        usage["fallbackUsed"] = bool(narrative.model_usage.get("fallbackUsed") or usage.get("fallbackUsed"))
        usage["localFallbackAllowed"] = False
        return AgentResult(blueprint.artifact, usage)
