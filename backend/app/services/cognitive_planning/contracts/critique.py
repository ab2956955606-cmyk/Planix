from __future__ import annotations

from typing import Literal

from pydantic import Field

from .base import CognitiveContract


class CritiqueDimensions(CognitiveContract):
    user_fit: int = Field(ge=0, le=100)
    goal_alignment: int = Field(ge=0, le=100)
    domain_correctness: int = Field(ge=0, le=100)
    feasibility: int = Field(ge=0, le=100)
    safety: int = Field(ge=0, le=100)
    task_specificity: int = Field(ge=0, le=100)
    resource_actionability: int = Field(ge=0, le=100)
    schedule_fit: int = Field(ge=0, le=100)
    adaptability: int = Field(ge=0, le=100)


class CritiqueIssue(CognitiveContract):
    severity: Literal["blocker", "major", "minor"]
    description: str
    evidence: str
    responsible_agent: Literal[
        "goal_modeling",
        "goal_intelligence",
        "reality",
        "context_evidence",
        "evidence",
        "strategy_architect",
        "strategy",
        "execution_designer",
        "execution",
    ]


class CriticRepairRequest(CognitiveContract):
    target_agent: Literal[
        "goal_modeling",
        "goal_intelligence",
        "reality",
        "context_evidence",
        "evidence",
        "strategy_architect",
        "strategy",
        "execution_designer",
        "execution",
    ]
    instruction: str
    expected_change: str


class PlanCritiqueReport(CognitiveContract):
    status: Literal["passed", "needs_repair", "blocked"]
    score: int = Field(ge=0, le=100)
    dimensions: CritiqueDimensions
    strengths: list[str] = Field(default_factory=list)
    issues: list[CritiqueIssue] = Field(default_factory=list)
    repair_requests: list[CriticRepairRequest] = Field(default_factory=list)
    simulation_summary: str = ""
    remaining_risks: list[str] = Field(default_factory=list)
    calendar_writable: bool = False
    confidence: float = Field(default=0.8, ge=0, le=1)
