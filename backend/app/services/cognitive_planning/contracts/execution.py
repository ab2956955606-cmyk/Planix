from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from .base import CognitiveContract


class ExecutionNarrative(CognitiveContract):
    execution_logic: str
    dependency_explanation: str
    weekly_or_stage_rhythm: str
    workload_reasoning: str
    risk_handling: str


class ExecutionResource(CognitiveContract):
    title: str
    type: str
    source_ref: str | None = None
    exact_usage: str
    expected_contribution: str
    fallback_resource: str | None = None


class ExecutionBlueprintTask(CognitiveContract):
    id: str
    title: str
    purpose: str
    why_now: str
    dependencies: list[str] = Field(default_factory=list)
    action_steps: list[str] = Field(min_length=1)
    estimated_minutes: int = Field(ge=1, le=1440)
    difficulty: Literal["low", "medium", "high"]
    scheduled_date: str | None = None
    schedule_window: str | None = None
    completion_evidence: list[str] = Field(min_length=1)
    deliverable: str
    resources: list[ExecutionResource] = Field(min_length=1)
    prerequisites: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    fallback_action: str
    domain_extensions: dict[str, Any] = Field(default_factory=dict)


class ExecutionCheckpoint(CognitiveContract):
    date_or_stage: str
    questions: list[str] = Field(default_factory=list)
    adjustment_rules: list[str] = Field(default_factory=list)


class ExecutionBlueprint(CognitiveContract):
    narrative: ExecutionNarrative
    tasks: list[ExecutionBlueprintTask] = Field(min_length=1)
    checkpoints: list[ExecutionCheckpoint] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    resource_coverage: Literal["strong", "partial", "weak"]
    status: Literal["draft"] = "draft"
