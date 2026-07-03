import json
import sqlite3
from collections import Counter
from hashlib import sha256
from re import findall
from uuid import uuid4

from ..db import get_conn
from ..errors import bad_request
from ..schemas import AiPayload, RagDocumentCreate, RagDocumentOut, RagIngestPayload, RagQueryOut, RagSource
from .llm import LlmClient
from .planner import _json_object


def chunk_text(text: str, size: int = 420, overlap: int = 48) -> list[str]:
    cleaned = " ".join(text.split())
    if not cleaned:
        return []
    chunks = []
    step = max(size - overlap, 1)
    for start in range(0, len(cleaned), step):
        chunk = cleaned[start : start + size].strip()
        if chunk:
            chunks.append(chunk)
        if start + size >= len(cleaned):
            break
    return chunks


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+", text)]


def _fts_query(text: str) -> str:
    tokens = tokenize(text)
    if not tokens:
        return ""
    escaped = [token.replace('"', '""') for token in tokens[:12]]
    return " OR ".join(f'"{token}"' for token in escaped)


def _keywords(text: str, limit: int = 6) -> list[str]:
    stopwords = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "you",
        "your",
        "are",
        "is",
        "to",
        "of",
        "in",
        "a",
        "an",
    }
    counts = Counter(token for token in tokenize(text) if token not in stopwords and len(token) > 1)
    return [word for word, _ in counts.most_common(limit)]


class RagService:
    def create_document(self, payload: RagDocumentCreate) -> RagDocumentOut:
        title = payload.title.strip() or "Untitled material"
        content = payload.content.strip()
        if not content:
            raise bad_request("content cannot be empty")

        chunks = chunk_text(content)
        if not chunks:
            raise bad_request("content cannot be empty")

        document_id = str(uuid4())
        summary = content[:220]
        content_hash = sha256(content.encode("utf-8")).hexdigest()

        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO documents(id, title, source, source_type, summary, content_hash)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (document_id, title, payload.source_type, payload.source_type, summary, content_hash),
            )
            for index, chunk in enumerate(chunks):
                chunk_id = str(uuid4())
                conn.execute(
                    """
                    INSERT INTO document_chunks(id, document_id, chunk_index, content, token_count)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (chunk_id, document_id, index, chunk, len(tokenize(chunk))),
                )
                conn.execute(
                    """
                    INSERT INTO document_chunks_fts(chunk_id, document_id, title, content)
                    VALUES (?, ?, ?, ?)
                    """,
                    (chunk_id, document_id, title, chunk),
                )
            row = conn.execute(
                """
                SELECT d.id, d.title, d.source_type, d.summary, d.created_at, COUNT(c.id) AS chunks
                FROM documents d
                LEFT JOIN document_chunks c ON c.document_id = d.id
                WHERE d.id = ?
                GROUP BY d.id
                """,
                (document_id,),
            ).fetchone()

        return self._document_out(row)

    def list_documents(self) -> list[RagDocumentOut]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT d.id, d.title, d.source_type, d.summary, d.created_at, COUNT(c.id) AS chunks
                FROM documents d
                LEFT JOIN document_chunks c ON c.document_id = d.id
                GROUP BY d.id
                ORDER BY d.created_at DESC
                """
            ).fetchall()
        return [self._document_out(row) for row in rows]

    def delete_document(self, document_id: str) -> None:
        with get_conn() as conn:
            conn.execute("DELETE FROM document_chunks_fts WHERE document_id = ?", (document_id,))
            conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))

    def ingest(self, payload: RagIngestPayload) -> dict[str, int | str]:
        document = self.create_document(
            RagDocumentCreate(title=payload.title, content=payload.content, sourceType="ingest")
        )
        return {"title": document.title, "chunks": document.chunks}

    def query(self, payload: AiPayload) -> RagQueryOut:
        query_text = " ".join(part for part in [payload.goal, payload.materials] if part.strip())
        sources = self.retrieve(query_text, limit=4)
        source_payload = [source.model_dump(by_alias=True) for source in sources]
        llm_result, _ = LlmClient().complete(
            "rag_query",
            (
                "You answer study planning questions with the provided sources. "
                "Return strict JSON only with keys: answer and keywords. "
                "keywords is an array of short strings. If sources are empty, say what material is missing."
            ),
            json.dumps(
                {
                    "goal": payload.goal,
                    "questionOrMaterials": payload.materials,
                    "sources": source_payload,
                },
                ensure_ascii=False,
            ),
        )
        if llm_result:
            parsed = _json_object(llm_result.content)
            if parsed:
                answer = str(parsed.get("answer") or "").strip()
                keywords = parsed.get("keywords")
                if not isinstance(keywords, list):
                    keywords = _keywords(" ".join(source.chunk for source in sources))
                if answer:
                    return RagQueryOut(
                        mode="llm",
                        answer=answer,
                        sources=sources,
                        keywords=[str(item) for item in keywords[:8]],
                        provider=llm_result.provider,
                        model=llm_result.model,
                    )

        return RagQueryOut(
            mode="mock",
            answer=self._mock_answer(sources),
            sources=sources,
            keywords=_keywords(" ".join(source.chunk for source in sources)),
        )

    def retrieve(self, query_text: str, limit: int = 4) -> list[RagSource]:
        query = _fts_query(query_text)
        if not query:
            return []

        try:
            with get_conn() as conn:
                rows = conn.execute(
                    """
                    SELECT
                      document_chunks_fts.document_id,
                      document_chunks_fts.title,
                      document_chunks_fts.content AS chunk,
                      document_chunks.chunk_index,
                      bm25(document_chunks_fts) AS rank
                    FROM document_chunks_fts
                    JOIN document_chunks ON document_chunks.id = document_chunks_fts.chunk_id
                    WHERE document_chunks_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (query, limit),
                ).fetchall()
        except sqlite3.OperationalError:
            return self._fallback_retrieve(query_text, limit)

        sources = []
        for row in rows:
            rank = float(row["rank"])
            score = -rank if rank <= 0 else 1 / (1 + rank)
            sources.append(
                RagSource(
                    documentId=row["document_id"],
                    title=row["title"],
                    chunk=row["chunk"],
                    score=round(score, 6),
                    chunkIndex=row["chunk_index"],
                )
            )
        if not sources:
            return self._fallback_retrieve(query_text, limit)
        return sources

    def _fallback_retrieve(self, query_text: str, limit: int) -> list[RagSource]:
        query_terms = set(tokenize(query_text))
        if not query_terms:
            return []

        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT d.id AS document_id, d.title, c.content AS chunk, c.chunk_index
                FROM document_chunks c
                JOIN documents d ON d.id = c.document_id
                ORDER BY c.created_at DESC
                LIMIT 200
                """
            ).fetchall()

        scored = []
        for row in rows:
            terms = set(tokenize(row["chunk"]))
            score = len(query_terms & terms)
            if score:
                scored.append((score, row))

        sources = []
        for score, row in sorted(scored, key=lambda item: item[0], reverse=True)[:limit]:
            sources.append(
                RagSource(
                    documentId=row["document_id"],
                    title=row["title"],
                    chunk=row["chunk"],
                    score=float(score),
                    chunkIndex=row["chunk_index"],
                )
            )
        return sources

    def _document_out(self, row) -> RagDocumentOut:
        return RagDocumentOut(
            id=row["id"],
            title=row["title"],
            sourceType=row["source_type"],
            summary=row["summary"],
            chunks=row["chunks"],
            createdAt=row["created_at"],
        )

    def _mock_answer(self, sources: list[RagSource]) -> str:
        if not sources:
            return "资料库还没有命中内容。请先保存 JD、课程笔记、面经或项目资料，再用问题触发检索。"
        titles = "、".join(dict.fromkeys(source.title for source in sources))
        return (
            f"根据资料库命中的《{titles}》片段，建议优先把高频技能、项目产出和时间约束转成可执行任务，"
            "并在计划中标注对应证据来源，方便后续复盘和面试讲解。"
        )
