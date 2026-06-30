from collections import Counter
from re import findall

from backend.app.db import list_chunks, save_chunk
from backend.app.schemas import AiPayload, RagIngestPayload


def chunk_text(text: str, size: int = 420) -> list[str]:
    cleaned = " ".join(text.split())
    return [cleaned[i : i + size] for i in range(0, len(cleaned), size) if cleaned[i : i + size]]


def tokenize(text: str) -> set[str]:
    return set(findall(r"[\w\u4e00-\u9fff]+", text.lower()))


class RagService:
    def ingest(self, payload: RagIngestPayload) -> dict[str, int | str]:
        chunks = chunk_text(payload.content)
        for chunk in chunks:
            save_chunk(payload.title, chunk)
        return {"title": payload.title, "chunks": len(chunks)}

    def query(self, payload: AiPayload) -> dict[str, object]:
        candidates = [{"title": "current input", "chunk": payload.materials}] if payload.materials else []
        candidates.extend(list_chunks())
        query_terms = tokenize(" ".join([payload.goal, payload.materials]))
        scored = []
        for item in candidates:
            terms = tokenize(item["chunk"])
            score = len(query_terms & terms)
            scored.append((score, item))
        top = [item for score, item in sorted(scored, key=lambda row: row[0], reverse=True)[:3] if score > 0]
        if not top and candidates:
            top = candidates[:2]
        keywords = Counter(" ".join(source["chunk"] for source in top).split()).most_common(5)
        return {
            "mode": "api",
            "answer": "建议优先把资料中的高频技能、项目产出和时间约束转化为可执行任务。",
            "sources": [{"title": item["title"], "quote": item["chunk"][:180]} for item in top],
            "keywords": [word for word, _ in keywords],
        }
