from __future__ import annotations

from typing import Literal

from pydantic import Field

from .base import CognitiveContract
from .goal_model import UserGoalModel


class MemoryDocument(CognitiveContract):
    id: str
    kind: str
    title: str
    summary: str
    content: str = ""
    tags: list[str] = Field(default_factory=list)


class CalendarConstraint(CognitiveContract):
    date: str
    statement: str
    source_id: str | None = None


class ResearchPolicy(CognitiveContract):
    allow_web_research: bool = False
    require_user_approval: bool = True
    freshness_required: bool = False
    source_types_allowed: list[str] = Field(default_factory=list)


class EvidenceInput(CognitiveContract):
    goal_model: UserGoalModel
    memory_query_context: str
    existing_materials: list[MemoryDocument] = Field(default_factory=list)
    calendar_constraints: list[CalendarConstraint] = Field(default_factory=list)
    resource_candidates: list[dict] = Field(default_factory=list)
    planning_hypotheses: list[dict] = Field(default_factory=list)
    research_policy: ResearchPolicy = Field(default_factory=ResearchPolicy)


class UserEvidence(CognitiveContract):
    source_id: str | None = None
    kind: str
    statement: str
    why_relevant: str
    confidence: float = Field(ge=0, le=1)


class EvidencePlanningRule(CognitiveContract):
    rule: str
    strength: Literal["hard", "soft"]
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


class DomainEvidence(CognitiveContract):
    claim: str
    source_type: str
    source_ref: str | None = None
    relevance: str
    freshness: str | None = None
    credibility: float = Field(ge=0, le=1)


class EvidenceResourceNeed(CognitiveContract):
    purpose: str
    ideal_resource_type: str
    selection_criteria: list[str] = Field(default_factory=list)


class EvidenceResourceCandidate(CognitiveContract):
    title: str
    type: str
    source_ref: str | None = None
    how_it_helps: str
    user_fit: str
    limitations: list[str] = Field(default_factory=list)
    credibility: float = Field(ge=0, le=1)


class CalendarReality(CognitiveContract):
    available_windows: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    load_warnings: list[str] = Field(default_factory=list)


class EvidenceGap(CognitiveContract):
    description: str
    consequence: str
    proposed_resolution: Literal[
        "ask_user",
        "web_research",
        "make_explicit_assumption",
        "reduce_scope",
    ]


class EvidencePack(CognitiveContract):
    user_evidence: list[UserEvidence] = Field(default_factory=list)
    planning_rules: list[EvidencePlanningRule] = Field(default_factory=list)
    domain_evidence: list[DomainEvidence] = Field(default_factory=list)
    resource_needs: list[EvidenceResourceNeed] = Field(default_factory=list)
    resource_candidates: list[EvidenceResourceCandidate] = Field(default_factory=list)
    calendar_reality: CalendarReality = Field(default_factory=CalendarReality)
    gaps: list[EvidenceGap] = Field(default_factory=list)
    synthesis: str
    confidence: float = Field(ge=0, le=1)
    can_proceed_to_strategy: bool
