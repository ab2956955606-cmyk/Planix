from __future__ import annotations

from datetime import date

from ..contracts import EvidenceInput, EvidencePack, ResearchPolicy, UserGoalModel
from ..retrieval import (
    CalendarContextRetriever,
    CognitiveMemoryRetriever,
    PlanningHistoryRetriever,
    PlanningHypothesisRepository,
    ResourceResearch,
)
from .base import AgentResult, CognitiveModelClient


EVIDENCE_SYSTEM = """
You are Planix Context & Evidence Agent. Synthesize memory, planning hypotheses, Calendar reality, local
materials, and resource candidates into evidence that can change planning decisions. Separate facts from
inference. Explain exactly how evidence affects the plan. Static resource entries are candidates, never a
decision. Do not invent links, current facts, availability, prices, policies, or credentials. When current or
authoritative research is needed but web research is not approved, record an explicit gap and limitation.
Block strategy when evidence is insufficient for a safe or credible plan. Return only the requested JSON and
never hidden chain-of-thought.
""".strip()


class ContextEvidenceAgent:
    name = "Context & Evidence Agent"
    artifact_type = "evidence_pack"

    def __init__(
        self,
        model: CognitiveModelClient | None = None,
        memory: CognitiveMemoryRetriever | None = None,
        calendar: CalendarContextRetriever | None = None,
        planning_history: PlanningHistoryRetriever | None = None,
        research: ResourceResearch | None = None,
        hypotheses: PlanningHypothesisRepository | None = None,
    ):
        self.model = model or CognitiveModelClient()
        self.memory = memory or CognitiveMemoryRetriever()
        self.calendar = calendar or CalendarContextRetriever()
        self.planning_history = planning_history or PlanningHistoryRetriever()
        self.research = research or ResourceResearch()
        self.hypotheses = hypotheses or PlanningHypothesisRepository()

    def run(
        self,
        goal: UserGoalModel,
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
                "official_doc",
                "user_material",
                "local_catalog",
                *(["official_notice", "web_search"] if web_research_allowed else []),
            ],
        )
        payload = EvidenceInput(
            goalModel=goal,
            memoryQueryContext=query,
            existingMaterials=[*self.memory.retrieve(goal), *self.planning_history.retrieve(goal)],
            calendarConstraints=self.calendar.retrieve(context_date or date.today().isoformat()),
            resourceCandidates=self.research.candidates(query, policy),
            planningHypotheses=[item.model_dump(by_alias=True) for item in self.hypotheses.relevant(goal.domain)],
            researchPolicy=policy,
        )
        return self.model.complete_contract(
            stage="context_evidence",
            task_type="planning_evidence",
            feature="cognitive_evidence_synthesis",
            system=EVIDENCE_SYSTEM,
            payload=payload.model_dump(by_alias=True),
            contract_type=EvidencePack,
            temperature=0.15,
        )
