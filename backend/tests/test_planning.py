from app.db import get_conn
from app.services import planning as planning_module
from app.services.llm import LlmError, LlmResult


def _goal_payload() -> dict:
    return {
        "goal": "Build a strong AI application internship portfolio",
        "deadline": "2026-09-30",
        "dailyHours": 3,
        "materials": "RAG FastAPI Agent evaluation",
        "preferences": "Deep work in the morning",
        "date": "2026-07-01",
    }


def test_goal_plan_returns_and_persists_structured_mock_result(client):
    response = client.post("/api/planning/goal-plan", json=_goal_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["id"]
    assert body["mode"] == "mock"
    assert body["summary"]
    assert len(body["phases"]) >= 1
    assert len(body["tasks"]) >= 1
    assert body["structuredPlan"]["goalTitle"]
    assert body["structuredPlan"]["durationDays"] >= 1
    assert body["structuredPlan"]["milestones"][0]["tasks"][0]["priority"] in {"low", "medium", "high"}

    with get_conn() as conn:
        row = conn.execute(
            "SELECT structured_plan_json, sources_json FROM planning_goals WHERE id = ?",
            (body["id"],),
        ).fetchone()

    assert row is not None
    assert "goalTitle" in row["structured_plan_json"]
    assert row["sources_json"].startswith("[")


def test_goal_plan_python_goal_has_structured_milestones(client):
    response = client.post(
        "/api/planning/goal-plan",
        json={
            "goal": "帮我规划一个 Python 学习计划",
            "deadline": "2026-07-29",
            "dailyHours": 2,
            "materials": "",
            "preferences": "",
            "date": "2026-07-01",
        },
    )

    assert response.status_code == 200
    body = response.json()
    structured = body["structuredPlan"]
    assert "Python" in structured["goalTitle"]
    assert structured["durationDays"] == 28
    assert structured["milestones"]
    assert structured["milestones"][0]["tasks"]
    assert structured["reviewPlan"]["questions"]


def test_goal_plan_llm_error_returns_readable_local_structured_result(client, monkeypatch):
    class TimeoutClient:
        def complete(self, *args, **kwargs):
            return None, LlmError("timeout", "timeout", 0)

    monkeypatch.setattr(planning_module, "LlmClient", lambda: TimeoutClient())

    response = client.post("/api/planning/goal-plan", json=_goal_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "mock"
    assert body["structuredPlan"]["goalTitle"]
    combined = " ".join(
        [
            body["summary"],
            body["structuredPlan"]["goalTitle"],
            body["structuredPlan"]["goalDescription"],
            *[phase["title"] for phase in body["phases"]],
            *[phase["detail"] for phase in body["phases"]],
            *[task["title"] for task in body["tasks"]],
            *[task["reason"] for task in body["tasks"]],
        ]
    )
    assert "�" not in combined
    assert "乱码" not in combined
    assert "ui-mock" not in combined
    assert "静态 UI 模拟" not in combined


def test_goal_plan_invalid_llm_structured_plan_is_safely_completed(client, monkeypatch):
    class InvalidStructuredClient:
        def complete(self, *args, **kwargs):
            return (
                LlmResult(
                    content='{"summary":"LLM partial","structuredPlan":{"goalTitle":"Broken","durationDays":"14","milestones":[{"title":"M","tasks":[{"title":"Task","priority":"urgent","estimatedMinutes":"bad"}]}],"reviewPlan":{"frequency":"sometimes"}}}',
                    provider="deepseek",
                    model="deepseek-v4-flash",
                ),
                None,
            )

    monkeypatch.setattr(planning_module, "LlmClient", lambda: InvalidStructuredClient())

    response = client.post("/api/planning/goal-plan", json=_goal_payload())

    assert response.status_code == 200
    body = response.json()
    structured = body["structuredPlan"]
    assert body["mode"] == "llm"
    assert structured["goalTitle"] == "Broken"
    assert structured["durationDays"] == 14
    assert structured["milestones"][0]["tasks"][0]["priority"] in {"low", "medium", "high"}
    assert isinstance(structured["milestones"][0]["tasks"][0]["estimatedMinutes"], int)
    assert structured["reviewPlan"]["frequency"] in {"daily", "weekly"}


def test_goal_plan_uses_short_llm_timeout(client, monkeypatch):
    captured = {}

    class CaptureClient:
        def complete(self, *args, **kwargs):
            captured.update(kwargs)
            return None, None

    monkeypatch.setattr(planning_module, "LlmClient", lambda: CaptureClient())

    response = client.post("/api/planning/goal-plan", json=_goal_payload())

    assert response.status_code == 200
    assert captured["timeout_seconds"] == planning_module.GOAL_PLAN_LLM_TIMEOUT_SECONDS
    assert captured["max_tokens"] == planning_module.GOAL_PLAN_MAX_TOKENS


def test_goal_plan_returns_rag_sources_when_documents_match(client):
    document = client.post(
        "/api/rag/documents",
        json={
            "title": "AI internship JD",
            "content": "AI application internships value RAG, FastAPI, React, Agent tools, and evaluation.",
        },
    ).json()

    response = client.post("/api/planning/goal-plan", json=_goal_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["sources"]
    assert body["sources"][0]["documentId"] == document["id"]
    assert body["structuredPlan"]["goalDescription"]


def test_daily_review_creates_replan_preview_without_writing_plans(client):
    created = client.post(
        "/api/plans",
        json={
            "date": "2026-07-01",
            "time": "09:00",
            "content": "Finish planning loop backend",
            "done": False,
        },
    ).json()

    response = client.post(
        "/api/planning/daily-review",
        json={
            "date": "2026-07-01",
            "goal": "Build portfolio-grade AI planner",
            "data": {
                "2026-07-01": {
                    "plans": [
                        {
                            "id": created["id"],
                            "time": "09:00",
                            "title": "Finish planning loop backend",
                            "done": False,
                            "completion": "",
                        }
                    ]
                }
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["doneCount"] == 0
    assert body["totalCount"] == 1
    assert body["targetDate"] == "2026-07-02"
    assert body["replanTasks"][0]["targetDate"] == "2026-07-02"

    tomorrow = client.get("/api/plans", params={"date": "2026-07-02"}).json()
    assert tomorrow == []

    saved = client.get("/api/planning/daily-review", params={"date": "2026-07-01"})
    assert saved.status_code == 200
    assert saved.json()["mode"] == "saved"


def test_missing_daily_review_returns_empty_saved_state(client):
    response = client.get("/api/planning/daily-review", params={"date": "2026-07-03"})
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "saved"
    assert body["date"] == "2026-07-03"
    assert body["summary"] == ""
    assert body["suggestions"] == []
    assert body["doneCount"] == 0
    assert body["totalCount"] == 0
    assert body["targetDate"] == "2026-07-04"
    assert body["replanTasks"] == []


def test_replan_apply_writes_ai_plans(client):
    response = client.post(
        "/api/planning/replan/apply",
        json={
            "tasks": [
                {
                    "targetDate": "2026-07-02",
                    "time": "10:00",
                    "title": "Continue backend tests",
                    "reason": "Moved from today's unfinished work",
                    "sourcePlanId": "local-plan-1",
                }
            ]
        },
    )
    assert response.status_code == 200
    created = response.json()
    assert created[0]["date"] == "2026-07-02"
    assert created[0]["content"] == "Continue backend tests"
    assert created[0]["source"] == "ai"

    listed = client.get("/api/plans", params={"date": "2026-07-02"}).json()
    assert [item["id"] for item in listed] == [created[0]["id"]]
