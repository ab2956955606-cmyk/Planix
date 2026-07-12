from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ValidationError

from ....harness.recovery import recover_json_object
from ...llm import LlmClient, LlmError, LlmResult
from ..contracts import SafePlanningError


ContractT = TypeVar("ContractT", bound=BaseModel)


TOKEN_ENV_BY_TASK = {
    "planning_goal_model": ("PLANIX_GOAL_MODEL_MAX_TOKENS", 5400),
    "planning_reality": ("PLANIX_REALITY_MAX_TOKENS", 5400),
    "planning_evidence": ("PLANIX_EVIDENCE_MAX_TOKENS", 6600),
    "planning_strategy": ("PLANIX_STRATEGY_MAX_TOKENS", 7200),
    "planning_execution": ("PLANIX_EXECUTION_MAX_TOKENS", 12000),
    "planning_critique": ("PLANIX_CRITIQUE_MAX_TOKENS", 6600),
    "planning_learning": ("PLANIX_LEARNING_MAX_TOKENS", 5400),
}

TOKEN_CAP_BY_TASK = {
    "planning_goal_model": 10800,
    "planning_reality": 10800,
    "planning_evidence": 13200,
    "planning_strategy": 14400,
    "planning_execution": 24000,
    "planning_critique": 13200,
    "planning_learning": 10800,
}


class PlanningModelUnavailable(RuntimeError):
    def __init__(self, stage: str, error: SafePlanningError):
        super().__init__(error.message)
        self.stage = stage
        self.error = error


@dataclass(frozen=True)
class AgentResult(Generic[ContractT]):
    artifact: ContractT
    model_usage: dict[str, Any]


def _extract_json(value: str) -> dict[str, Any]:
    # Harness recovery repairs syntax only (fences/prefixes/trailing commas).
    # Missing or invalid contract fields still fail closed below.
    return recover_json_object(value) or {}


def _safe_error(stage: str, error: LlmError | None, message: str) -> SafePlanningError:
    return SafePlanningError(
        stage=stage,
        errorType=error.error_type if error else "model_unavailable",
        message=message,
        retryable=(error.error_type if error else "") not in {"auth_error", "invalid_key_format"},
        attempts=error.attempts or [] if error else [],
    )


def _usage(result: LlmResult, task_type: str) -> dict[str, Any]:
    raw = result.usage or {}
    return {
        "provider": result.provider,
        "model": result.model,
        "promptTokens": raw.get("promptTokens") or raw.get("prompt_tokens"),
        "completionTokens": raw.get("completionTokens") or raw.get("completion_tokens"),
        "totalTokens": raw.get("totalTokens") or raw.get("total_tokens"),
        "latencyMs": result.latency_ms,
        "mode": "llm",
        "taskType": task_type,
        "fallbackUsed": result.fallback_used,
        "localFallbackAllowed": False,
        "attempts": result.attempts or [],
    }


class CognitiveModelClient:
    def __init__(self, llm: LlmClient | None = None):
        self.llm = llm or LlmClient()

    def complete_contract(
        self,
        *,
        stage: str,
        task_type: str,
        feature: str,
        system: str,
        payload: dict[str, Any],
        contract_type: type[ContractT],
        temperature: float = 0.2,
    ) -> AgentResult[ContractT]:
        env_name, default_tokens = TOKEN_ENV_BY_TASK[task_type]
        task_token_cap = TOKEN_CAP_BY_TASK[task_type]
        try:
            max_tokens = max(256, min(int(os.getenv(env_name, default_tokens)), task_token_cap))
        except ValueError:
            max_tokens = default_tokens
        schema = contract_type.model_json_schema(by_alias=True)
        user = json.dumps(
            {
                "input": payload,
                "requiredOutputSchema": schema,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        result, error = self.llm.complete(
            feature,
            system,
            user,
            max_tokens=max_tokens,
            max_token_cap=task_token_cap,
            temperature=temperature,
            response_format_json=True,
            task_type=task_type,
        )
        if not result:
            message = error.message if error else "No configured model completed this cognitive planning stage."
            raise PlanningModelUnavailable(stage, _safe_error(stage, error, message))
        raw = _extract_json(result.content)
        if not raw:
            raise PlanningModelUnavailable(
                stage,
                SafePlanningError(
                    stage=stage,
                    errorType="invalid_model_output",
                    message="The model did not return a JSON object for this planning stage.",
                    retryable=True,
                    attempts=result.attempts or [],
                ),
            )
        try:
            artifact = contract_type.model_validate(raw)
        except ValidationError as exc:
            first = exc.errors()[0] if exc.errors() else {}
            location = ".".join(str(item) for item in first.get("loc", []))
            message = f"The model output failed the {stage} contract"
            if location:
                message += f" at {location}"
            raise PlanningModelUnavailable(
                stage,
                SafePlanningError(
                    stage=stage,
                    errorType="invalid_model_output",
                    message=message + ".",
                    retryable=True,
                    attempts=result.attempts or [],
                ),
            ) from exc
        return AgentResult(artifact=artifact, model_usage=_usage(result, task_type))
