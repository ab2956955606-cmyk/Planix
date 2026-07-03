import json

from app.db import get_conn


def _runtime_payload() -> dict:
    return {
        "input": "Plan one week of AI application internship preparation",
        "date": "2026-07-03",
        "preferences": "Deep work in the morning",
        "materials": "RAG FastAPI Agent Runtime",
        "data": {},
    }


def _stream_events(client, payload: dict | None = None) -> list[dict]:
    with client.stream("POST", "/api/runtime/run", json=payload or _runtime_payload()) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/x-ndjson")
        text = "".join(response.iter_text())
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def test_runtime_run_returns_valid_ndjson_sequence(client):
    events = _stream_events(client)

    assert events
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
    assert events[0]["type"] == "node"
    assert events[0]["nodeType"] == "input"
    assert events[-1]["type"] == "final"

    node_types = [event.get("nodeType") for event in events if event["type"] == "node"]
    assert node_types[:3] == ["input", "reasoning", "tool"]
    assert "observation" in node_types
    assert "output" in node_types


def test_runtime_tools_are_readonly_or_preview_and_do_not_write_plans(client):
    client.post(
        "/api/plans",
        json={
            "date": "2026-07-03",
            "time": "09:00",
            "content": "Existing task",
            "done": False,
        },
    )
    before = client.get("/api/plans", params={"date": "2026-07-03"}).json()

    events = _stream_events(client)

    tool_events = [event for event in events if event["type"] == "tool"]
    assert tool_events
    tool_names = {event["toolCall"]["name"] for event in tool_events}
    assert tool_names <= {"search_materials", "get_today_plans", "get_memory", "propose_tasks"}
    write_modes = {event["toolCall"]["writeMode"] for event in tool_events}
    assert write_modes <= {"readonly", "preview"}
    assert "preview" in write_modes

    proposal_event = next(
        event for event in tool_events
        if event["toolCall"]["name"] == "propose_tasks"
    )
    proposal = proposal_event["toolCall"]["output"]
    assert proposal["notice"].startswith("当前仅生成结构化预览")
    assert proposal["structuredPlan"]["goalTitle"]
    assert proposal["structuredPlan"]["milestones"]
    assert proposal["tasks"]

    after = client.get("/api/plans", params={"date": "2026-07-03"}).json()
    assert [item["id"] for item in after] == [item["id"] for item in before]


def test_runtime_persists_agent_run_and_events(client):
    events = _stream_events(client)
    run_id = events[0]["runId"]

    with get_conn() as conn:
        run = conn.execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,)).fetchone()
        stored_events = conn.execute(
            "SELECT COUNT(*) AS total FROM agent_events WHERE run_id = ?",
            (run_id,),
        ).fetchone()["total"]

    assert run is not None
    assert run["status"] == "done"
    assert run["output_summary"]
    assert stored_events == len(events)


def test_runtime_search_materials_returns_sources(client):
    client.post(
        "/api/rag/documents",
        json={
            "title": "Runtime JD",
            "content": "Agent runtime roles need RAG retrieval, FastAPI streaming, and safe tool routing.",
        },
    )

    events = _stream_events(client)

    material_event = next(
        event for event in events
        if event["type"] == "tool" and event["toolCall"]["name"] == "search_materials"
    )
    assert material_event["toolCall"]["writeMode"] == "readonly"
    assert material_event["toolCall"]["output"]
    source = material_event["toolCall"]["output"][0]
    assert {"documentId", "title", "chunk", "score", "chunkIndex"} <= set(source)


def test_runtime_python_goal_returns_learning_plan(client):
    events = _stream_events(
        client,
        {
            "input": "帮我规划一个 python 学习计划",
            "date": "2026-07-03",
            "preferences": "",
            "materials": "",
            "data": {},
        },
    )

    final = next(event for event in events if event["type"] == "final")
    assert "Python" in final["content"]
    assert "语法" in final["content"]
    assert "项目" in final["content"]
    assert "复盘" in final["content"]

    proposal_event = next(
        event for event in events
        if event["type"] == "tool" and event["toolCall"]["name"] == "propose_tasks"
    )
    structured = proposal_event["toolCall"]["output"]["structuredPlan"]
    assert structured["durationDays"] >= 1
    assert structured["milestones"][0]["tasks"][0]["priority"] in {"low", "medium", "high"}


def test_runtime_success_events_do_not_include_old_ui_mock_names(client):
    events = _stream_events(client)
    combined = json.dumps(events, ensure_ascii=False)

    assert "plan_context_lookup" not in combined
    assert "ui-mock" not in combined
    assert "静态 UI 模拟" not in combined
    assert "乱码" not in combined
