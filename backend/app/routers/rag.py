from fastapi import APIRouter, Response, status

from ..schemas import AiPayload, RagDocumentCreate, RagDocumentOut, RagIngestPayload, RagQueryOut
from ..services.rag import RagService

router = APIRouter(prefix="/api/rag", tags=["rag"])

rag = RagService()


@router.post("/documents", response_model=RagDocumentOut)
def create_document(payload: RagDocumentCreate) -> RagDocumentOut:
    return rag.create_document(payload)


@router.get("/documents", response_model=list[RagDocumentOut])
def list_documents() -> list[RagDocumentOut]:
    return rag.list_documents()


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: str) -> Response:
    rag.delete_document(document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/ingest")
def rag_ingest(payload: RagIngestPayload) -> dict[str, int | str]:
    return rag.ingest(payload)


@router.post("/query", response_model=RagQueryOut)
def rag_query(payload: AiPayload) -> RagQueryOut:
    return rag.query(payload)
