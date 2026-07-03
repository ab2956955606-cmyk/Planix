from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type
import json
import time
from typing import Any, Iterator
from uuid import uuid4

from ..db import get_conn, load_memory
from ..schemas import AgentRunRequest, StructuredGoalPlan
from .llm import LlmClient
from .plans import list_plans
from .rag import RagService
from .structured_goal_plan import build_local_structured_plan, derive_planner_tasks, render_goal_plan_markdown


NodeType = str
NodeStatus = str


@dataclass(frozen=True)
class RuntimeStep:
    id: str
    node_type: NodeType
    title: str
    content: str = ""
    tool_name: str = ""
    tool_input: dict[str, object] | None = None


class AgentRunRepository:
    def create_run(self, user_input: str) -> str:
        run_id = str(uuid4())
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO agent_runs(id, input, status)
                VALUES (?, ?, 'running')
                """,
                (run_id, user_input[:4000]),
            )
        return run_id

    def record_event(self, run_id: str, event: dict[str, object]) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO agent_events(id, run_id, sequence, event_type, node_id, payload)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    run_id,
                    int(event.get("sequence") or 0),
                    str(event.get("type") or ""),
                    str(event.get("nodeId") or ""),
                    json.dumps(event, ensure_ascii=False),
                ),
            )

    def finish_run(self, run_id: str, status: str, output_summary: str = "", error: str = "") -> None:
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE agent_runs
                SET status = ?, output_summary = ?, error = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, output_summary[:4000], error[:1000], run_id),
            )

    def recent_summaries(self, limit: int = 3) -> list[str]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT output_summary
                FROM agent_runs
                WHERE output_summary != ''
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [str(row["output_summary"]) for row in rows]


class StreamEngine:
    def __init__(self, run_id: str, repository: AgentRunRepository):
        self.run_id = run_id
        self.repository = repository
        self.sequence = 0

    def make_event(self, event_type: str, **payload: object) -> dict[str, object]:
        self.sequence += 1
        event: dict[str, object] = {
            "runId": self.run_id,
            "sequence": self.sequence,
            "type": event_type,
            **payload,
        }
        self.repository.record_event(self.run_id, event)
        return event

    def encode(self, event: dict[str, object]) -> str:
        return json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"


class MemorySystem:
    def __init__(self, repository: AgentRunRepository):
        self.repository = repository

    def get_context(self, payload: AgentRunRequest) -> dict[str, object]:
        preferences = payload.preferences.strip() or load_memory()
        return {
            "currentGoal": payload.input,
            "date": payload.date,
            "preferences": preferences,
            "materials": payload.materials[:3000],
            "recentRuns": self.repository.recent_summaries(),
        }


class RuntimePlanner:
    def plan(self, payload: AgentRunRequest, memory: dict[str, object]) -> list[RuntimeStep]:
        focus = payload.input.strip() or "Planix agent task"
        plan_content = (
            f"Plan for: {focus}\n"
            "1. Retrieve grounded context from memory, materials, and today's plans.\n"
            "2. Generate a structured planning preview without writing user data.\n"
            "3. Render the preview as a readable plan for user confirmation."
        )
        return [
            RuntimeStep(id="plan", node_type="reasoning", title="Execution Plan", content=plan_content),
            RuntimeStep(
                id="tool-materials",
                node_type="tool",
                title="search_materials",
                tool_name="search_materials",
                tool_input={"query": " ".join([payload.input, payload.materials]).strip(), "topK": 3},
            ),
            RuntimeStep(
                id="tool-plans",
                node_type="tool",
                title="get_today_plans",
                tool_name="get_today_plans",
                tool_input={"date": payload.date},
            ),
            RuntimeStep(
                id="tool-memory",
                node_type="tool",
                title="get_memory",
                tool_name="get_memory",
                tool_input={"date": payload.date},
            ),
            RuntimeStep(
                id="tool-propose",
                node_type="tool",
                title="propose_tasks",
                tool_name="propose_tasks",
                tool_input={"goal": payload.input, "date": payload.date, "preferences": memory.get("preferences", "")},
            ),
        ]


class ToolRouter:
    allowed_tools = {"search_materials", "get_today_plans", "get_memory", "propose_tasks"}

    def route(self, step: RuntimeStep) -> dict[str, object] | None:
        if not step.tool_name or step.tool_name not in self.allowed_tools:
            return None
        return {
            "name": step.tool_name,
            "input": step.tool_input or {},
            "writeMode": "preview" if step.tool_name == "propose_tasks" else "readonly",
        }


class RuntimeToolExecutor:
    def __init__(self):
        self.rag = RagService()

    def execute(self, tool_call: dict[str, object], memory: dict[str, object]) -> object:
        name = str(tool_call["name"])
        tool_input = tool_call.get("input")
        params = tool_input if isinstance(tool_input, dict) else {}
        if name == "get_memory":
            return {
                "preferences": memory.get("preferences", ""),
                "recentRuns": memory.get("recentRuns", []),
            }
        if name == "get_today_plans":
            plan_date = str(params.get("date") or memory.get("date") or date_type.today().isoformat())
            return [plan.model_dump(by_alias=True) for plan in list_plans(plan_date)]
        if name == "search_materials":
            query = str(params.get("query") or memory.get("currentGoal") or "")
            return [source.model_dump(by_alias=True) for source in self.rag.retrieve(query, limit=3)]
        if name == "propose_tasks":
            goal = str(params.get("goal") or memory.get("currentGoal") or "Planix task")
            plan_date = str(params.get("date") or memory.get("date") or date_type.today().isoformat())
            query = " ".join([goal, str(memory.get("materials") or "")]).strip()
            sources = self.rag.retrieve(query, limit=3)
            structured_plan = build_local_structured_plan(goal, date=plan_date, daily_hours=2, source_count=len(sources))
            return {
                "notice": "当前仅生成结构化预览，尚未写入 Goals、Calendar 或 Notes。",
                "structuredPlan": structured_plan.model_dump(by_alias=True),
                "tasks": [task.model_dump(by_alias=True) for task in derive_planner_tasks(structured_plan)],
                "sources": [source.model_dump(by_alias=True) for source in sources],
            }
        return {"error": f"Tool {name} is not available."}


class RuntimeOrchestrator:
    def __init__(self):
        self.repository = AgentRunRepository()
        self.memory_system = MemorySystem(self.repository)
        self.planner = RuntimePlanner()
        self.router = ToolRouter()
        self.tool_executor = RuntimeToolExecutor()

    def run(self, payload: AgentRunRequest) -> Iterator[str]:
        run_id = self.repository.create_run(payload.input)
        stream = StreamEngine(run_id, self.repository)
        final_output = ""
        try:
            memory = self.memory_system.get_context(payload)
            steps = self.planner.plan(payload, memory)

            yield stream.encode(
                stream.make_event(
                    "node",
                    nodeId="input",
                    nodeType="input",
                    title="Input",
                    content=payload.input,
                    status="done",
                )
            )

            plan_step = steps[0]
            yield stream.encode(
                stream.make_event(
                    "node",
                    nodeId=plan_step.id,
                    nodeType=plan_step.node_type,
                    title=plan_step.title,
                    content="",
                    status="running",
                )
            )
            yield stream.encode(stream.make_event("delta", nodeId=plan_step.id, delta=plan_step.content))
            yield stream.encode(stream.make_event("status", nodeId=plan_step.id, status="done"))

            tool_outputs: list[dict[str, object]] = []
            for step in steps[1:]:
                routed = self.router.route(step)
                if not routed:
                    continue
                yield stream.encode(
                    stream.make_event(
                        "node",
                        nodeId=step.id,
                        nodeType="tool",
                        title=step.title,
                        content="",
                        status="running",
                    )
                )
                start = time.perf_counter()
                output = self.tool_executor.execute(routed, memory)
                latency_ms = max(1, int((time.perf_counter() - start) * 1000))
                tool_call = {
                    **routed,
                    "output": output,
                    "latencyMs": latency_ms,
                }
                tool_outputs.append(tool_call)
                yield stream.encode(
                    stream.make_event(
                        "tool",
                        nodeId=step.id,
                        nodeType="tool",
                        title=step.title,
                        status="done",
                        toolCall=tool_call,
                    )
                )
                yield stream.encode(stream.make_event("status", nodeId=step.id, status="done"))

            observation = self._observation(tool_outputs)
            yield stream.encode(
                stream.make_event(
                    "node",
                    nodeId="observation",
                    nodeType="observation",
                    title="Observation",
                    content="",
                    status="running",
                )
            )
            yield stream.encode(stream.make_event("delta", nodeId="observation", delta=observation))
            yield stream.encode(stream.make_event("status", nodeId="observation", status="done"))

            yield stream.encode(
                stream.make_event(
                    "node",
                    nodeId="output",
                    nodeType="output",
                    title="Output",
                    content="",
                    status="running",
                )
            )
            for chunk in self._stream_output(payload, tool_outputs):
                final_output += chunk
                yield stream.encode(stream.make_event("delta", nodeId="output", delta=chunk))
            yield stream.encode(stream.make_event("status", nodeId="output", status="done"))
            yield stream.encode(stream.make_event("final", nodeId="output", content=final_output))
            self.repository.finish_run(run_id, "done", output_summary=final_output)
        except Exception as exc:
            message = f"Runtime failed: {exc}"
            yield stream.encode(stream.make_event("error", nodeId="output", error=message, status="error"))
            self.repository.finish_run(run_id, "error", output_summary=final_output, error=message)

    def _stream_output(
        self,
        payload: AgentRunRequest,
        tool_outputs: list[dict[str, object]],
    ) -> Iterator[str]:
        proposal = _proposal_from_tool_outputs(tool_outputs)
        if proposal:
            try:
                structured_plan = StructuredGoalPlan.model_validate(proposal["structuredPlan"])
            except (KeyError, ValueError, TypeError):
                structured_plan = build_local_structured_plan(payload.input, date=payload.date)
            sources = proposal.get("sources")
            source_items = sources if isinstance(sources, list) else _sources_from_tool_outputs(tool_outputs)
            today_plan_count = len(_tool_output_list(tool_outputs, "get_today_plans"))
            rendered = render_goal_plan_markdown(
                structured_plan,
                source_items,
                local_template=not LlmClient().is_enabled(),
                today_plan_count=today_plan_count,
            )
            for chunk in _chunk_text(rendered):
                yield chunk
            return

        rendered = render_goal_plan_markdown(
            build_local_structured_plan(payload.input, date=payload.date),
            _sources_from_tool_outputs(tool_outputs),
            local_template=True,
            today_plan_count=len(_tool_output_list(tool_outputs, "get_today_plans")),
        )
        for chunk in _chunk_text(rendered):
            yield chunk

    def _observation(self, tool_outputs: list[dict[str, object]]) -> str:
        readonly = len([item for item in tool_outputs if item.get("writeMode") == "readonly"])
        preview = len([item for item in tool_outputs if item.get("writeMode") == "preview"])
        source_count = len(_sources_from_tool_outputs(tool_outputs))
        return (
            f"Executed {readonly} read-only tool(s) and {preview} preview tool(s). "
            f"Retrieved {source_count} material source(s). No user data was modified."
        )


def _tool_output_list(tool_outputs: list[dict[str, object]], name: str) -> list[Any]:
    for item in tool_outputs:
        if item.get("name") != name:
            continue
        output = item.get("output")
        return output if isinstance(output, list) else []
    return []


def _sources_from_tool_outputs(tool_outputs: list[dict[str, object]]) -> list[dict[str, Any]]:
    sources = _tool_output_list(tool_outputs, "search_materials")
    return [source for source in sources if isinstance(source, dict)]


def _proposal_from_tool_outputs(tool_outputs: list[dict[str, object]]) -> dict[str, Any] | None:
    for item in tool_outputs:
        if item.get("name") != "propose_tasks":
            continue
        output = item.get("output")
        if isinstance(output, dict) and isinstance(output.get("structuredPlan"), dict):
            return output
    return None


def _chunk_text(text: str) -> Iterator[str]:
    lines = text.splitlines(keepends=True)
    for line in lines:
        yield line
