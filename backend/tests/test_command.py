import json
import sqlite3

from app.db import get_conn, init_db
from app.schemas import RefinedTask
from app.services.command_agent import CommandAgentService, detect_command_intent, resolve_command_intent


def _events(response):
    lines = response.text.strip().splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _valid_structured_plan():
    return {
        "goalTitle": "AI internship prep",
        "goalDescription": "Prepare portfolio material for interviews.",
        "durationDays": 5,
        "milestones": [
            {
                "title": "Project story",
                "description": "Prepare Planix talking points.",
                "tasks": [
                    {
                        "title": "Draft Planix project intro",
                        "description": "Write a concise project overview.",
                        "estimatedMinutes": 60,
                        "dueDate": "2026-07-05",
                        "priority": "high",
                    }
                ],
            },
            {
                "title": "Interview practice",
                "description": "Practice answers.",
                "tasks": [
                    {
                        "title": "Practice Agent Runtime explanation",
                        "description": "Explain Runtime event flow.",
                        "estimatedMinutes": 45,
                        "dueDate": "2026-07-06",
                        "priority": "medium",
                    }
                ],
            },
        ],
        "reviewPlan": {"frequency": "daily", "questions": ["What improved?"]},
    }


class FakeRuntime:
    calls = 0
    last_input = ""

    def __init__(self, structured_plan=None):
        self.structured_plan = structured_plan if structured_plan is not None else _valid_structured_plan()

    def run(self, payload):
        FakeRuntime.calls += 1
        FakeRuntime.last_input = payload.input
        run_id = f"run_fake_{FakeRuntime.calls}"
        for name in ("get_memory", "get_today_plans", "search_materials"):
            yield json.dumps({"runId": run_id, "type": "node", "title": name, "status": "running"}) + "\n"
            yield json.dumps({"runId": run_id, "type": "tool", "toolCall": {"name": name, "input": {}, "output": {}}}) + "\n"
        yield json.dumps({"runId": run_id, "type": "node", "title": "propose_tasks", "status": "running"}) + "\n"
        yield json.dumps({
            "runId": run_id,
            "type": "tool",
            "toolCall": {
                "name": "propose_tasks",
                "input": {"goal": payload.input},
                "output": {
                    "mode": "local_fallback",
                    "structuredPlan": self.structured_plan,
                    "tasks": [],
                    "sources": [],
                    "fallbackReason": "test",
                },
            },
        }) + "\n"


class ExplodingRuntime:
    calls = 0

    def run(self, payload):
        ExplodingRuntime.calls += 1
        raise AssertionError("Runtime should not be called")


def _patch_runtime(monkeypatch, runtime_factory):
    monkeypatch.setattr("app.services.command_agent.RuntimeOrchestrator", runtime_factory)


class FakePlanningService:
    calls = []

    def refine_task(self, payload):
        FakePlanningService.calls.append(payload)
        return RefinedTask(
            title=payload.task_title,
            objective=f"Refine {payload.task_title}",
            estimatedMinutes=payload.available_minutes or 60,
            steps=["Step one", "Step two", "Step three"],
            checklist=["Check one", "Check two"],
            acceptanceCriteria=["Done"],
            deliverable="A concrete output",
            risks=[],
            fallbackTips=[],
            mode="local_fallback",
        )


def test_command_chat_streams_and_replays_thread(client):
    response = client.post("/api/command/chat", json={"message": "Planix 这个项目怎么介绍？"})

    assert response.status_code == 200
    events = _events(response)
    assert events[0]["type"] == "thread"
    assert any(event["type"] == "assistant_delta" for event in events)
    assert events[-1]["type"] == "done"
    thread_id = events[-1]["threadId"]

    thread = client.get(f"/api/command/thread/{thread_id}")
    assert thread.status_code == 200
    body = thread.json()
    assert body["id"] == thread_id
    assert len(body["messages"]) == 2
    assert body["messages"][0]["role"] == "user"
    assert body["messages"][1]["role"] == "assistant"
    assert body["currentDraft"] is None
    assert "drafts" not in body
    assert "actions" not in body
    assert "outputs" not in body


def test_command_schema_migrations_include_phase_44_columns(client):
    client.get("/api/health")
    with get_conn() as conn:
        draft_columns = {row["name"] for row in conn.execute("PRAGMA table_info(command_drafts)").fetchall()}
        message_columns = {row["name"] for row in conn.execute("PRAGMA table_info(command_messages)").fetchall()}
        action_columns = {row["name"] for row in conn.execute("PRAGMA table_info(command_actions)").fetchall()}
        approval_columns = {row["name"] for row in conn.execute("PRAGMA table_info(command_approvals)").fetchall()}
        assert "source_run_id" in draft_columns
        assert {"kind", "payload_json"} <= message_columns
        assert {"draft_id", "error_message"} <= action_columns
        assert "decision" in approval_columns
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'command_actions'"
        ).fetchone()
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'command_approvals'"
        ).fetchone()


def test_command_schema_migrates_legacy_action_and_approval_columns():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE command_actions (
          id TEXT PRIMARY KEY,
          thread_id TEXT NOT NULL,
          target TEXT NOT NULL,
          operation TEXT NOT NULL,
          risk TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'proposed',
          reason TEXT NOT NULL DEFAULT '',
          payload_json TEXT NOT NULL DEFAULT '{}',
          result_json TEXT NOT NULL DEFAULT '{}',
          error TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE command_approvals (
          id TEXT PRIMARY KEY,
          thread_id TEXT NOT NULL,
          action_id TEXT NOT NULL,
          permission TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'pending',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO command_actions(
          id, thread_id, target, operation, risk, error
        ) VALUES (
          'action_legacy', 'thread_legacy', 'calendar', 'create_or_update_plans', 'write', 'legacy failure'
        );
        """
    )

    init_db(conn)

    action_columns = {row["name"] for row in conn.execute("PRAGMA table_info(command_actions)").fetchall()}
    approval_columns = {row["name"] for row in conn.execute("PRAGMA table_info(command_approvals)").fetchall()}
    assert {"draft_id", "error_message"} <= action_columns
    assert "decision" in approval_columns
    row = conn.execute("SELECT draft_id, error_message FROM command_actions WHERE id = 'action_legacy'").fetchone()
    assert row["draft_id"] == ""
    assert row["error_message"] == "legacy failure"


def test_auto_normal_chat_does_not_run_runtime_or_create_draft(client, monkeypatch):
    ExplodingRuntime.calls = 0
    _patch_runtime(monkeypatch, lambda: ExplodingRuntime())

    response = client.post("/api/command/chat", json={"mode": "auto", "message": "Planix 这个项目怎么介绍？"})

    assert response.status_code == 200
    assert ExplodingRuntime.calls == 0
    events = _events(response)
    assert not any(event["type"] == "runtime_started" for event in events)
    with get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) AS count FROM command_drafts").fetchone()["count"] == 0


def test_chat_mode_planning_request_does_not_run_runtime(client, monkeypatch):
    ExplodingRuntime.calls = 0
    _patch_runtime(monkeypatch, lambda: ExplodingRuntime())

    response = client.post("/api/command/chat", json={"mode": "chat", "message": "帮我规划本周 AI 实习准备"})

    assert response.status_code == 200
    assert ExplodingRuntime.calls == 0
    events = _events(response)
    text = "".join(event.get("text", "") for event in events if event["type"] == "assistant_delta")
    assert "普通聊天模式" in text
    assert not any(event["type"] == "runtime_started" for event in events)
    with get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) AS count FROM command_drafts").fetchone()["count"] == 0


def test_auto_planning_request_creates_hidden_draft(client, monkeypatch):
    FakeRuntime.calls = 0
    _patch_runtime(monkeypatch, lambda: FakeRuntime())

    response = client.post("/api/command/chat", json={"mode": "auto", "message": "帮我规划本周 AI 实习准备"})

    assert response.status_code == 200
    events = _events(response)
    assert FakeRuntime.calls == 1
    assert [event["type"] for event in events].count("runtime_started") == 1
    assert any(event["type"] == "runtime_event" and event["name"] == "propose_tasks" for event in events)
    draft_event = next(event for event in events if event["type"] == "draft_created")
    summary_event = next(event for event in events if event["type"] == "summary")
    summary_index = next(index for index, event in enumerate(events) if event["type"] == "summary")
    assert events[summary_index + 1]["type"] == "plan_detail"
    assert draft_event["kind"] == "calendar_plan"
    assert "已生成计划草稿" in summary_event["text"]

    with get_conn() as conn:
        draft = conn.execute("SELECT * FROM command_drafts WHERE id = ?", (draft_event["draftId"],)).fetchone()
        assert draft is not None
        assert draft["status"] == "current"
        assert draft["kind"] == "calendar_plan"
        payload = json.loads(draft["payload_json"])
        assert payload["structuredPlan"]["goalTitle"] == "AI internship prep"
        assert payload["runtimeRunId"].startswith("run_fake_")
        assert conn.execute("SELECT COUNT(*) AS count FROM plans").fetchone()["count"] == 0

    thread_id = events[-1]["threadId"]
    thread = client.get(f"/api/command/thread/{thread_id}").json()
    assert thread["currentDraft"]["id"] == draft_event["draftId"]


def test_workbench_mode_creates_hidden_draft(client, monkeypatch):
    FakeRuntime.calls = 0
    _patch_runtime(monkeypatch, lambda: FakeRuntime())

    response = client.post("/api/command/chat", json={"mode": "workbench", "message": "Planix 这个项目怎么介绍？"})

    assert response.status_code == 200
    events = _events(response)
    assert FakeRuntime.calls == 1
    assert any(event["type"] == "draft_created" for event in events)


def test_command_threads_list_and_delete_do_not_delete_plans(client):
    from app.schemas import PlanCreate
    from app.services.plans import create_plan

    first = client.post("/api/command/chat", json={"mode": "chat", "message": "第一个对话"})
    second = client.post("/api/command/chat", json={"mode": "chat", "message": "第二个对话"})
    first_thread_id = _events(first)[-1]["threadId"]
    second_thread_id = _events(second)[-1]["threadId"]
    create_plan(PlanCreate(date="2026-07-05", time="09:00", content="Keep calendar plan"))

    listed = client.get("/api/command/threads").json()
    ids = [thread["id"] for thread in listed]
    assert second_thread_id in ids
    assert first_thread_id in ids
    assert listed[ids.index(second_thread_id)]["messageCount"] >= 2

    deleted = client.delete(f"/api/command/thread/{first_thread_id}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] == 1
    assert client.get(f"/api/command/thread/{first_thread_id}").status_code == 404

    listed_after = client.get("/api/command/threads").json()
    assert first_thread_id not in [thread["id"] for thread in listed_after]
    with get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) AS count FROM plans").fetchone()["count"] == 1


def test_second_generation_supersedes_previous_draft(client, monkeypatch):
    FakeRuntime.calls = 0
    _patch_runtime(monkeypatch, lambda: FakeRuntime())

    first = client.post("/api/command/chat", json={"mode": "auto", "message": "帮我规划本周 AI 实习准备"})
    thread_id = _events(first)[-1]["threadId"]
    second = client.post(
        "/api/command/chat",
        json={"threadId": thread_id, "mode": "auto", "message": "帮我规划下周 AI 实习准备"},
    )

    assert second.status_code == 200
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT version, status FROM command_drafts WHERE thread_id = ? ORDER BY version ASC",
            (thread_id,),
        ).fetchall()
    assert [(row["version"], row["status"]) for row in rows] == [(1, "superseded"), (2, "current")]


def test_runtime_handoff_uses_current_thread_context_only(client, monkeypatch):
    FakeRuntime.calls = 0
    FakeRuntime.last_input = ""
    _patch_runtime(monkeypatch, lambda: FakeRuntime())

    first = client.post("/api/command/chat", json={"mode": "chat", "message": "我要去赛里木湖"})
    thread_id = _events(first)[-1]["threadId"]
    second = client.post(
        "/api/command/chat",
        json={"threadId": thread_id, "mode": "auto", "message": "帮我做个规划"},
    )

    assert second.status_code == 200
    assert FakeRuntime.calls == 1
    assert "赛里木湖" in FakeRuntime.last_input

    client.post("/api/command/chat", json={"mode": "auto", "message": "帮我做个规划"})
    assert FakeRuntime.calls == 2
    assert "赛里木湖" not in FakeRuntime.last_input


def test_invalid_structured_plan_does_not_create_draft_but_saves_message(client, monkeypatch):
    _patch_runtime(monkeypatch, lambda: FakeRuntime(structured_plan={"goalTitle": "Bad", "milestones": []}))

    response = client.post("/api/command/chat", json={"mode": "auto", "message": "帮我规划本周 AI 实习准备"})

    assert response.status_code == 200
    events = _events(response)
    assert not any(event["type"] == "draft_created" for event in events)
    text = "".join(event.get("text", "") for event in events if event["type"] == "assistant_delta")
    assert "没有返回合法的 structuredPlan" in text
    thread_id = events[-1]["threadId"]
    thread = client.get(f"/api/command/thread/{thread_id}").json()
    assert len(thread["messages"]) == 2
    assert thread["messages"][1]["role"] == "assistant"
    assert thread["currentDraft"] is None
    with get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) AS count FROM command_drafts").fetchone()["count"] == 0


def test_draft_save_error_returns_error_event_and_done(client, monkeypatch):
    _patch_runtime(monkeypatch, lambda: FakeRuntime())

    def fail_create(*args, **kwargs):
        raise RuntimeError("migration missing")

    monkeypatch.setattr("app.services.command_agent.CommandAgentService._create_calendar_draft", fail_create)

    response = client.post("/api/command/chat", json={"mode": "auto", "message": "帮我规划本周 AI 实习准备"})

    assert response.status_code == 200
    events = _events(response)
    assert any(event["type"] == "error" and "计划草稿保存失败" in event["error"] for event in events)
    assert events[-1]["type"] == "done"
    thread_id = events[-1]["threadId"]
    thread = client.get(f"/api/command/thread/{thread_id}").json()
    assert thread["messages"][-1]["role"] == "assistant"
    assert "计划草稿保存失败" in thread["messages"][-1]["content"]
    with get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) AS count FROM command_drafts").fetchone()["count"] == 0


def test_calendar_write_error_uses_calendar_specific_message(client, monkeypatch):
    _patch_runtime(monkeypatch, lambda: FakeRuntime())
    first = client.post("/api/command/chat", json={"mode": "auto", "message": "Plan my skating practice"})
    thread_id = _events(first)[-1]["threadId"]

    def fail_execute(self, action_id):
        raise RuntimeError("write exploded")

    monkeypatch.setattr("app.services.command_agent.CommandAgentService._execute_calendar_action", fail_execute)

    response = client.post(
        "/api/command/chat",
        json={"threadId": thread_id, "mode": "auto", "permission": "medium", "message": "write this plan to calendar"},
    )

    assert response.status_code == 200
    events = _events(response)
    error = next(event for event in events if event["type"] == "error")
    assert "写入日历失败" in error["error"]
    assert "计划草稿保存失败" not in error["error"]


def test_phase_43_generation_does_not_create_write_actions(client, monkeypatch):
    _patch_runtime(monkeypatch, lambda: FakeRuntime())

    response = client.post("/api/command/chat", json={"mode": "auto", "message": "帮我规划本周 AI 实习准备"})

    assert response.status_code == 200
    with get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) AS count FROM plans").fetchone()["count"] == 0
        assert conn.execute("SELECT COUNT(*) AS count FROM command_actions").fetchone()["count"] == 0
        assert conn.execute("SELECT COUNT(*) AS count FROM command_approvals").fetchone()["count"] == 0
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'command_outputs'"
        ).fetchone()
        assert exists is None


def test_intent_router_rules():
    assert detect_command_intent("帮我规划本周 AI 实习准备") == "planning_request"
    assert detect_command_intent("重新生成一个轻松版本") == "regenerate_draft"
    assert detect_command_intent("展开看看完整计划") == "show_current_plan"
    assert detect_command_intent("写入日历") == "sync_to_calendar"
    assert detect_command_intent("帮我写入日历") == "sync_to_calendar"
    assert detect_command_intent("写入计划") == "sync_to_calendar"
    assert detect_command_intent("保存计划") == "sync_to_calendar"
    assert detect_command_intent("确认写入") == "sync_to_calendar"
    assert detect_command_intent("保存到日程") == "sync_to_calendar"
    assert detect_command_intent("把这个计划写进日历") == "sync_to_calendar"
    assert resolve_command_intent(
        "保存",
        detect_command_intent("保存"),
        has_current_draft=True,
    ) == "sync_to_calendar"
    assert resolve_command_intent(
        "保存",
        detect_command_intent("保存"),
        has_current_draft=False,
    ) == "unsupported_command"
    assert detect_command_intent("打开日历") == "navigate_ui"
    assert detect_command_intent("Planix 这个项目怎么介绍？") == "normal_chat"
    assert detect_command_intent("帮我细化全部任务") == "refine_current_plan"
    assert detect_command_intent("refine all tasks") == "refine_current_plan"


def test_command_drafts_route_stays_private(client):
    assert client.post("/api/command/drafts", json={}).status_code == 404


def test_show_current_plan_returns_inline_detail(client, monkeypatch):
    _patch_runtime(monkeypatch, lambda: FakeRuntime())
    first = client.post("/api/command/chat", json={"mode": "auto", "message": "帮我规划本周 AI 实习准备"})
    thread_id = _events(first)[-1]["threadId"]

    response = client.post(
        "/api/command/chat",
        json={"threadId": thread_id, "mode": "auto", "message": "展开看看完整计划"},
    )

    assert response.status_code == 200
    events = _events(response)
    detail = next(event for event in events if event["type"] == "plan_detail")
    assert detail["title"] == "AI internship prep"
    assert detail["structuredPlan"]["milestones"][0]["tasks"][0]["title"] == "Draft Planix project intro"


def test_regenerate_current_draft_supersedes_old_version(client, monkeypatch):
    FakeRuntime.calls = 0
    _patch_runtime(monkeypatch, lambda: FakeRuntime())
    first = client.post("/api/command/chat", json={"mode": "auto", "message": "帮我规划本周 AI 实习准备"})
    thread_id = _events(first)[-1]["threadId"]

    response = client.post(
        "/api/command/chat",
        json={"threadId": thread_id, "mode": "auto", "message": "重新生成一个更轻松的版本"},
    )

    assert response.status_code == 200
    assert FakeRuntime.calls == 2
    events = _events(response)
    assert any(event["type"] == "draft_created" and event["version"] == 2 for event in events)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT version, status FROM command_drafts WHERE thread_id = ? ORDER BY version ASC",
            (thread_id,),
        ).fetchall()
    assert [(row["version"], row["status"]) for row in rows] == [(1, "superseded"), (2, "current")]


def test_sync_calendar_low_requires_approval_and_does_not_write(client, monkeypatch):
    _patch_runtime(monkeypatch, lambda: FakeRuntime())
    first = client.post("/api/command/chat", json={"mode": "auto", "message": "帮我规划本周 AI 实习准备"})
    thread_id = _events(first)[-1]["threadId"]

    response = client.post(
        "/api/command/chat",
        json={"threadId": thread_id, "mode": "auto", "permission": "low", "message": "把这个计划写进日历"},
    )

    assert response.status_code == 200
    events = _events(response)
    assert any(event["type"] == "calendar_plan_preview" for event in events)
    approval = next(event for event in events if event["type"] == "approval_required")
    with get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) AS count FROM plans").fetchone()["count"] == 0
        action = conn.execute("SELECT * FROM command_actions WHERE id = ?", (approval["actionId"],)).fetchone()
        assert action["status"] == "waiting_approval"
        assert conn.execute("SELECT COUNT(*) AS count FROM command_approvals WHERE action_id = ?", (approval["actionId"],)).fetchone()["count"] == 1


def test_write_plan_phrase_uses_current_draft_without_runtime(client, monkeypatch):
    FakeRuntime.calls = 0
    _patch_runtime(monkeypatch, lambda: FakeRuntime())
    first = client.post("/api/command/chat", json={"mode": "auto", "message": "帮我规划本周 AI 实习准备"})
    thread_id = _events(first)[-1]["threadId"]
    assert FakeRuntime.calls == 1

    response = client.post(
        "/api/command/chat",
        json={"threadId": thread_id, "mode": "auto", "permission": "low", "message": "写入计划"},
    )

    assert response.status_code == 200
    events = _events(response)
    assert FakeRuntime.calls == 1
    assert not any(event["type"] == "runtime_started" for event in events)
    assert any(event["type"] == "calendar_plan_preview" for event in events)
    assert any(event["type"] == "approval_required" for event in events)
    with get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) AS count FROM plans").fetchone()["count"] == 0


def test_short_save_phrase_with_current_draft_means_calendar_write(client, monkeypatch):
    FakeRuntime.calls = 0
    _patch_runtime(monkeypatch, lambda: FakeRuntime())
    first = client.post("/api/command/chat", json={"mode": "auto", "message": "帮我规划本周 AI 实习准备"})
    thread_id = _events(first)[-1]["threadId"]

    response = client.post(
        "/api/command/chat",
        json={"threadId": thread_id, "mode": "auto", "permission": "low", "message": "保存"},
    )

    assert response.status_code == 200
    events = _events(response)
    assert FakeRuntime.calls == 1
    assert not any(event["type"] == "runtime_started" for event in events)
    assert any(event["type"] == "calendar_plan_preview" for event in events)


def test_approve_calendar_write_creates_plans(client, monkeypatch):
    _patch_runtime(monkeypatch, lambda: FakeRuntime())
    first = client.post("/api/command/chat", json={"mode": "auto", "message": "帮我规划本周 AI 实习准备"})
    thread_id = _events(first)[-1]["threadId"]
    write = client.post(
        "/api/command/chat",
        json={"threadId": thread_id, "mode": "auto", "permission": "low", "message": "把这个计划写进日历"},
    )
    action_id = next(event for event in _events(write) if event["type"] == "approval_required")["actionId"]

    response = client.post(
        "/api/command/approve",
        json={"threadId": thread_id, "actionId": action_id, "decision": "approve", "permission": "low"},
    )

    assert response.status_code == 200
    events = _events(response)
    result = next(event for event in events if event["type"] == "calendar_write_result")
    assert result["created"] == 2
    assert result["failed"] == 0
    with get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) AS count FROM plans").fetchone()["count"] == 2
        assert conn.execute("SELECT status FROM command_actions WHERE id = ?", (action_id,)).fetchone()["status"] == "success"
        first_plan = conn.execute(
            "SELECT result, priority, estimated_minutes FROM plans WHERE content = ?",
            ("Draft Planix project intro",),
        ).fetchone()
        assert first_plan["result"] == "Write a concise project overview."
        assert first_plan["priority"] == "high"
        assert first_plan["estimated_minutes"] == 60


def test_approve_calendar_write_error_uses_calendar_specific_message(client, monkeypatch):
    _patch_runtime(monkeypatch, lambda: FakeRuntime())
    first = client.post("/api/command/chat", json={"mode": "auto", "message": "Plan my skating practice"})
    thread_id = _events(first)[-1]["threadId"]
    write = client.post(
        "/api/command/chat",
        json={"threadId": thread_id, "mode": "auto", "permission": "low", "message": "write this plan to calendar"},
    )
    action_id = next(event for event in _events(write) if event["type"] == "approval_required")["actionId"]

    def fail_execute(self, action_id):
        raise RuntimeError("approve write exploded")

    monkeypatch.setattr("app.services.command_agent.CommandAgentService._execute_calendar_action", fail_execute)

    response = client.post(
        "/api/command/approve",
        json={"threadId": thread_id, "actionId": action_id, "decision": "approve", "permission": "low"},
    )

    assert response.status_code == 200
    events = _events(response)
    error = next(event for event in events if event["type"] == "error")
    assert "写入日历失败" in error["error"]
    assert "计划草稿保存失败" not in error["error"]


def test_reject_calendar_write_does_not_create_plans(client, monkeypatch):
    _patch_runtime(monkeypatch, lambda: FakeRuntime())
    first = client.post("/api/command/chat", json={"mode": "auto", "message": "帮我规划本周 AI 实习准备"})
    thread_id = _events(first)[-1]["threadId"]
    write = client.post(
        "/api/command/chat",
        json={"threadId": thread_id, "mode": "auto", "permission": "low", "message": "把这个计划写进日历"},
    )
    action_id = next(event for event in _events(write) if event["type"] == "approval_required")["actionId"]

    response = client.post(
        "/api/command/approve",
        json={"threadId": thread_id, "actionId": action_id, "decision": "reject", "permission": "low"},
    )

    assert response.status_code == 200
    events = _events(response)
    assert any(event["type"] == "execution_result" and event["status"] == "rejected" for event in events)
    with get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) AS count FROM plans").fetchone()["count"] == 0
        assert conn.execute("SELECT status FROM command_actions WHERE id = ?", (action_id,)).fetchone()["status"] == "rejected"


def test_medium_permission_auto_writes_calendar_without_approval(client, monkeypatch):
    _patch_runtime(monkeypatch, lambda: FakeRuntime())
    first = client.post("/api/command/chat", json={"mode": "auto", "message": "帮我规划本周 AI 实习准备"})
    thread_id = _events(first)[-1]["threadId"]

    response = client.post(
        "/api/command/chat",
        json={"threadId": thread_id, "mode": "auto", "permission": "medium", "message": "把这个计划写进日历"},
    )

    assert response.status_code == 200
    events = _events(response)
    assert not any(event["type"] == "approval_required" for event in events)
    result = next(event for event in events if event["type"] == "calendar_write_result")
    assert result["created"] == 2
    with get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) AS count FROM plans").fetchone()["count"] == 2


def test_refine_all_tasks_updates_current_draft_and_calendar_write_uses_refinements(client, monkeypatch):
    FakePlanningService.calls = []
    _patch_runtime(monkeypatch, lambda: FakeRuntime())
    monkeypatch.setattr("app.services.command_agent.PlanningService", lambda: FakePlanningService())

    first = client.post("/api/command/chat", json={"mode": "auto", "message": "Plan my skating practice"})
    thread_id = _events(first)[-1]["threadId"]

    response = client.post(
        "/api/command/chat",
        json={"threadId": thread_id, "mode": "auto", "message": "refine all tasks"},
    )

    assert response.status_code == 200
    events = _events(response)
    started = next(event for event in events if event["type"] == "refinement_started")
    result = next(event for event in events if event["type"] == "refined_tasks_result")
    assert started["total"] == 1
    assert result["succeeded"] == 1
    assert result["failed"] == 0
    assert len(FakePlanningService.calls) == 1
    assert FakePlanningService.calls[0].plan_context is not None
    assert FakePlanningService.calls[0].plan_context.plan_title == "AI internship prep"
    assert FakePlanningService.calls[0].plan_context.current_milestone["title"] == "Project story"
    assert FakePlanningService.calls[0].available_minutes == 60

    with get_conn() as conn:
        draft = conn.execute("SELECT payload_json FROM command_drafts WHERE id = ?", (started["draftId"],)).fetchone()
        payload = json.loads(draft["payload_json"])
        assert sorted(payload["refinements"].keys()) == ["m0:t0"]
        assert conn.execute("SELECT COUNT(*) AS count FROM plans").fetchone()["count"] == 0

    write = client.post(
        "/api/command/chat",
        json={"threadId": thread_id, "mode": "auto", "permission": "medium", "message": "write this plan to calendar"},
    )

    assert write.status_code == 200
    with get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) AS count FROM plans WHERE refined_task_json != ''").fetchone()["count"] == 1


def test_refine_all_tasks_caps_large_current_milestone_at_five(client, monkeypatch):
    FakePlanningService.calls = []
    structured_plan = _valid_structured_plan()
    structured_plan["milestones"][0]["tasks"] = [
        {
            "title": f"Task {index}",
            "description": f"Practice item {index}",
            "estimatedMinutes": 120,
            "dueDate": "2026-07-05",
            "priority": "high",
        }
        for index in range(1, 8)
    ]
    _patch_runtime(monkeypatch, lambda: FakeRuntime(structured_plan=structured_plan))
    monkeypatch.setattr("app.services.command_agent.PlanningService", lambda: FakePlanningService())

    first = client.post("/api/command/chat", json={"mode": "auto", "message": "Plan my Python practice"})
    thread_id = _events(first)[-1]["threadId"]

    response = client.post(
        "/api/command/chat",
        json={"threadId": thread_id, "mode": "auto", "message": "refine all tasks"},
    )

    assert response.status_code == 200
    events = _events(response)
    started = next(event for event in events if event["type"] == "refinement_started")
    result = next(event for event in events if event["type"] == "refined_tasks_result")
    assert started["total"] == 5
    assert result["succeeded"] == 5
    assert len(FakePlanningService.calls) == 5
    assert all(call.available_minutes == 120 for call in FakePlanningService.calls)


def test_refine_without_current_draft_does_not_write(client):
    response = client.post("/api/command/chat", json={"mode": "auto", "message": "refine all tasks"})

    assert response.status_code == 200
    events = _events(response)
    assert not any(event["type"] == "refinement_started" for event in events)
    text = "".join(event.get("text", "") for event in events if event["type"] == "assistant_delta")
    assert "没有可细化的计划草稿" in text
    with get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) AS count FROM plans").fetchone()["count"] == 0


def test_calendar_write_does_not_overwrite_manual_plan(client, monkeypatch):
    _patch_runtime(monkeypatch, lambda: FakeRuntime())
    client.post(
        "/api/plans",
        json={"date": "2026-07-05", "time": "08:00", "content": "Draft Planix project intro", "source": "manual", "result": "keep me"},
    )
    first = client.post("/api/command/chat", json={"mode": "auto", "message": "帮我规划本周 AI 实习准备"})
    thread_id = _events(first)[-1]["threadId"]

    response = client.post(
        "/api/command/chat",
        json={"threadId": thread_id, "mode": "auto", "permission": "medium", "message": "把这个计划写进日历"},
    )

    assert response.status_code == 200
    with get_conn() as conn:
        manual = conn.execute("SELECT * FROM plans WHERE source = 'manual'").fetchone()
        assert manual["result"] == "keep me"
        assert conn.execute("SELECT COUNT(*) AS count FROM plans WHERE source = 'ai'").fetchone()["count"] == 2


def test_calendar_write_does_not_overwrite_existing_ai_result(client):
    source_key = "command-draft:draft_existing_ai:m0:t0"
    client.post(
        "/api/plans",
        json={
            "date": "2026-07-05",
            "time": "08:00",
            "content": "Draft Planix project intro",
            "source": "ai",
            "sourceKey": source_key,
            "result": "keep existing user note",
        },
    )

    state, plan = CommandAgentService()._upsert_calendar_plan(
        {
            "title": "Draft Planix project intro",
            "date": "2026-07-05",
            "time": "09:00",
            "description": "Write a concise project overview.",
            "priority": "high",
            "estimatedMinutes": 60,
            "sourceKey": source_key,
        }
    )

    assert state == "updated"
    assert plan.result == "keep existing user note"
    assert plan.priority == "high"
    assert plan.estimated_minutes == 60
    with get_conn() as conn:
        row = conn.execute("SELECT result, priority, estimated_minutes FROM plans WHERE source_key = ?", (source_key,)).fetchone()
        assert row["result"] == "keep existing user note"
        assert row["priority"] == "high"
        assert row["estimated_minutes"] == 60
