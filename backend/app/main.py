from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.schemas import AiPayload, MemoryPayload, RagIngestPayload
from backend.app.services.evaluator import PlannerEvaluator
from backend.app.services.memory import MemoryStore
from backend.app.services.planner import PlannerAgent
from backend.app.services.rag import RagService
from backend.app.services.tools import list_tools

app = FastAPI(title="MyNotes AI API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = PlannerAgent()
rag = RagService()
memory = MemoryStore()
evaluator = PlannerEvaluator()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/agent/plan")
def plan(payload: AiPayload) -> dict[str, object]:
    return agent.plan(payload)


@app.post("/api/agent/review")
def review(payload: AiPayload) -> dict[str, object]:
    return agent.review(payload)


@app.get("/api/agent/tools")
def tools() -> list[dict[str, object]]:
    return list_tools()


@app.post("/api/rag/ingest")
def rag_ingest(payload: RagIngestPayload) -> dict[str, int | str]:
    return rag.ingest(payload)


@app.post("/api/rag/query")
def rag_query(payload: AiPayload) -> dict[str, object]:
    return rag.query(payload)


@app.post("/api/memory/preferences")
def save_preferences(payload: MemoryPayload) -> dict[str, str]:
    return memory.save(payload)


@app.get("/api/memory/preferences")
def get_preferences(user_id: str = "local-user") -> dict[str, str]:
    return memory.get(user_id)


@app.post("/api/eval/planner")
def eval_planner(payload: AiPayload) -> dict[str, object]:
    return evaluator.run(payload)
