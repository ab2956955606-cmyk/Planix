from __future__ import annotations

from ...memory_store import MemoryService
from ..contracts import MemoryDocument, UserGoalModel


class CognitiveMemoryRetriever:
    def __init__(self, memory: MemoryService | None = None):
        self.memory = memory or MemoryService()

    def retrieve(self, goal: UserGoalModel, *, limit: int = 20) -> list[MemoryDocument]:
        query = " ".join(
            value
            for value in (goal.goal_statement, goal.desired_change, goal.domain, goal.subdomain or "")
            if value
        )
        items = self.memory.search_memories(
            query,
            kinds=["preference", "review", "material", "note"],
            limit=limit,
        )
        return [
            MemoryDocument(
                id=item.id,
                kind=item.kind,
                title=item.title,
                summary=item.summary,
                content=item.content[:2000],
                tags=item.tags,
            )
            for item in items
        ]
