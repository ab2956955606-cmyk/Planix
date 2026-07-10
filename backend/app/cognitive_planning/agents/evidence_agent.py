from __future__ import annotations

from datetime import date
from typing import Protocol

from ...services.cognitive_planning.contracts import EvidenceInput, EvidencePack, ResearchPolicy
from ...services.cognitive_planning.retrieval import (
    CalendarContextRetriever,
    CognitiveMemoryRetriever,
    PlanningHistoryRetriever,
)
from ..contracts import GoalUnderstandingArtifact, RealityAssessment
from ..memory import UserModelMemoryRepository
from .base import AgentResult, CognitiveModelClient


class WebEvidenceProvider(Protocol):
    def search(self, query: str, policy: ResearchPolicy) -> list[dict]: ...


class DisabledWebEvidenceProvider:
    def search(self, query: str, policy: ResearchPolicy) -> list[dict]:
        return []


EVIDENCE_SYSTEM = """
You are Planix Evidence Agent. Build an Evidence Pack that can change decisions. Use the supplied user-model
memories, raw user materials and notes, planning history, Calendar reality, and explicitly approved research.
Do not treat a raw note, a catalog entry, or a model recollection as a user preference. Every evidence item
must name its source type, credibility, relevance, and exactly why it changes this plan.

When supplied sources are incomplete, you may state conservative model-knowledge inferences with a lower
credibility and no invented URL, price, policy, availability, or current fact. Record current-information needs
as gaps. Never output empty statistics such as 'found 4 memories'. Static resource catalogs are not decisions.
Block strategy when evidence is too weak for a safe or credible recommendation. Return only the requested
JSON and never hidden chain-of-thought.
""".strip()


class EvidenceAgent:
    name = "Evidence Agent"
    artifact_type = "evidence_pack"

    def __init__(
        self,
        model: CognitiveModelClient | None = None,
        *,
        memory: CognitiveMemoryRetriever | None = None,
        calendar: CalendarContextRetriever | None = None,
        planning_history: PlanningHistoryRetriever | None = None,
        user_model: UserModelMemoryRepository | None = None,
        web_provider: WebEvidenceProvider | None = None,
    ):
        self.model = model or CognitiveModelClient()
        self.memory = memory or CognitiveMemoryRetriever()
        self.calendar = calendar or CalendarContextRetriever()
        self.planning_history = planning_history or PlanningHistoryRetriever()
        self.user_model = user_model or UserModelMemoryRepository()
        self.web_provider = web_provider or DisabledWebEvidenceProvider()

    def run(
        self,
        goal: GoalUnderstandingArtifact,
        reality: RealityAssessment,
        *,
        context_date: str | None = None,
        web_research_allowed: bool = False,
        web_research_approved: bool = False,
        freshness_required: bool = False,
    ) -> AgentResult[EvidencePack]:
        query = " ".join(value for value in (goal.goal_statement, goal.desired_change, goal.domain) if value)
        policy = ResearchPolicy(
            allowWebResearch=web_research_allowed,
            requireUserApproval=not web_research_approved,
            freshnessRequired=freshness_required,
            sourceTypesAllowed=[
                "user_material",
                "memory_note",
                "planning_history",
                "calendar",
                "model_knowledge",
                *(["official_notice", "web_search"] if web_research_allowed and web_research_approved else []),
            ],
        )
        web_candidates = self.web_provider.search(query, policy) if web_research_allowed and web_research_approved else []
        content_memories = [item for item in self.memory.retrieve(goal) if item.kind != "preference"]
        payload = EvidenceInput(
            goalModel=goal,
            memoryQueryContext=query,
            userModelMemories=[item.model_dump(by_alias=True) for item in self.user_model.relevant(goal.domain)],
            existingMaterials=[*content_memories, *self.planning_history.retrieve(goal)],
            calendarConstraints=self.calendar.retrieve(context_date or date.today().isoformat()),
            resourceCandidates=web_candidates,
            planningHypotheses=[],
            researchPolicy=policy,
        )
        return self.model.complete_contract(
            stage="evidence_synthesis",
            task_type="planning_evidence",
            feature="cognitive_os_evidence_synthesis",
            system=EVIDENCE_SYSTEM,
            payload={
                **payload.model_dump(by_alias=True),
                "realityAssessment": reality.model_dump(by_alias=True),
            },
            contract_type=EvidencePack,
            temperature=0.15,
        )
