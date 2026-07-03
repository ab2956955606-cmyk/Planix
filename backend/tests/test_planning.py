from app.db import get_conn
from app.services import planning as planning_module
from app.services.ai_settings import EffectiveAiSettings
from app.services.llm import LlmError, LlmResult
import json


def _goal_payload() -> dict:
    return {
        "goal": "Build a strong AI application internship portfolio",
        "deadline": "2026-09-30",
        "dailyHours": 3,
        "materials": "RAG FastAPI Agent evaluation",
        "preferences": "Deep work in the morning",
        "date": "2026-07-01",
    }


def _settings(
    *,
    provider: str = "deepseek",
    api_key: str = "sk-test-local",
    base_url: str = "https://api.deepseek.com/v1?token=secret",
    model: str = "deepseek-v4-flash",
    timeout_seconds: int = 10,
) -> EffectiveAiSettings:
    return EffectiveAiSettings(
        provider=provider,
        base_url=base_url,
        model=model,
        api_key=api_key,
        temperature=0.1,
        timeout_seconds=timeout_seconds,
        updated_at="",
    )


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
    assert body["fallbackReason"] == "missing_api_key"
    assert body["baseUrlHost"] == "api.deepseek.com"

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
        settings = _settings()

        def complete(self, *args, **kwargs):
            return None, LlmError("timeout", "timeout", 0)

    monkeypatch.setattr(planning_module, "LlmClient", lambda: TimeoutClient())

    response = client.post("/api/planning/goal-plan", json=_goal_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "mock"
    assert body["fallbackReason"] == "llm_error"
    assert body["errorType"] == "timeout"
    assert body["baseUrlHost"] == "api.deepseek.com"
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
        settings = _settings()

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
    assert body["fallbackReason"] is None
    assert body["errorType"] is None
    assert structured["goalTitle"] == "Broken"
    assert structured["durationDays"] == 14
    assert structured["milestones"][0]["tasks"][0]["priority"] in {"low", "medium", "high"}
    assert isinstance(structured["milestones"][0]["tasks"][0]["estimatedMinutes"], int)
    assert structured["reviewPlan"]["frequency"] in {"daily", "weekly"}


def test_goal_plan_uses_smart_llm_timeout(client, monkeypatch):
    captured = {}

    class CaptureClient:
        settings = _settings()

        def complete(self, *args, **kwargs):
            captured.update(kwargs)
            return None, None

    monkeypatch.setattr(planning_module, "LlmClient", lambda: CaptureClient())

    response = client.post("/api/planning/goal-plan", json=_goal_payload())

    assert response.status_code == 200
    assert captured["timeout_seconds"] == planning_module.GOAL_PLAN_MIN_LLM_TIMEOUT_SECONDS
    assert captured["max_tokens"] == planning_module.GOAL_PLAN_DEFAULT_MAX_TOKENS
    assert captured["max_token_cap"] == planning_module.GOAL_PLAN_MAX_TOKEN_LIMIT
    assert captured["response_format_json"] is True


def test_goal_plan_max_tokens_env_defaults_and_clamps(monkeypatch):
    monkeypatch.delenv(planning_module.GOAL_PLAN_MAX_TOKENS_ENV, raising=False)
    assert planning_module._goal_plan_max_tokens() == 4096

    monkeypatch.setenv(planning_module.GOAL_PLAN_MAX_TOKENS_ENV, "6000")
    assert planning_module._goal_plan_max_tokens() == 6000

    monkeypatch.setenv(planning_module.GOAL_PLAN_MAX_TOKENS_ENV, "8000")
    assert planning_module._goal_plan_max_tokens() == 8000

    monkeypatch.setenv(planning_module.GOAL_PLAN_MAX_TOKENS_ENV, "99999")
    assert planning_module._goal_plan_max_tokens() == 8000

    monkeypatch.setenv(planning_module.GOAL_PLAN_MAX_TOKENS_ENV, "abc")
    assert planning_module._goal_plan_max_tokens() == 4096

    monkeypatch.setenv(planning_module.GOAL_PLAN_MAX_TOKENS_ENV, "")
    assert planning_module._goal_plan_max_tokens() == 4096


def test_goal_plan_caps_smart_llm_timeout(client, monkeypatch):
    captured = {}

    class SlowSettingsClient:
        settings = _settings(timeout_seconds=120)

        def complete(self, *args, **kwargs):
            captured.update(kwargs)
            return None, None

    monkeypatch.setattr(planning_module, "LlmClient", lambda: SlowSettingsClient())

    response = client.post("/api/planning/goal-plan", json=_goal_payload())

    assert response.status_code == 200
    assert captured["timeout_seconds"] == planning_module.GOAL_PLAN_MAX_LLM_TIMEOUT_SECONDS


def test_goal_plan_passes_chinese_output_language_to_llm(client, monkeypatch):
    captured = {}

    class CaptureLanguageClient:
        settings = _settings()

        def complete(self, feature, system, user, **kwargs):
            captured["system"] = system
            captured["user"] = json.loads(user)
            return None, None

    monkeypatch.setattr(planning_module, "LlmClient", lambda: CaptureLanguageClient())

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
    assert captured["user"]["outputLanguage"] == "zh-CN"
    assert "outputLanguage" in captured["system"]
    assert "Simplified Chinese" in captured["system"]


def test_goal_plan_prefers_frontend_output_language_over_goal_text(client, monkeypatch):
    captured = {}

    class CaptureLanguageClient:
        settings = _settings()

        def complete(self, feature, system, user, **kwargs):
            captured["user"] = json.loads(user)
            return None, None

    monkeypatch.setattr(planning_module, "LlmClient", lambda: CaptureLanguageClient())

    response = client.post(
        "/api/planning/goal-plan",
        json={
            "goal": "帮我规划一个 Python 学习计划",
            "deadline": "2026-07-29",
            "dailyHours": 2,
            "materials": "",
            "preferences": "",
            "date": "2026-07-01",
            "outputLanguage": "en-US",
        },
    )

    assert response.status_code == 200
    assert captured["user"]["outputLanguage"] == "en-US"


def test_goal_plan_truncated_llm_json_reports_invalid_model_output(client, monkeypatch):
    class TruncatedJsonClient:
        settings = _settings()

        def complete(self, *args, **kwargs):
            return (
                LlmResult(
                    content='{"summary":"Live plan","structuredPlan":{"goalTitle":"Broken"',
                    provider="deepseek",
                    model="deepseek-v4-flash",
                ),
                None,
            )

    monkeypatch.setattr(planning_module, "LlmClient", lambda: TruncatedJsonClient())

    response = client.post("/api/planning/goal-plan", json=_goal_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "mock"
    assert body["fallbackReason"] == "llm_error"
    assert body["errorType"] == "invalid_model_output"
    assert body["structuredPlan"]["goalTitle"]


def test_goal_plan_empty_llm_content_is_reported(client, monkeypatch):
    class EmptyContentClient:
        settings = _settings()

        def complete(self, *args, **kwargs):
            return None, LlmError(
                "The model returned empty content. Increase max tokens or use a non-reasoning model.",
                "empty_content",
                0,
            )

    monkeypatch.setattr(planning_module, "LlmClient", lambda: EmptyContentClient())

    response = client.post("/api/planning/goal-plan", json=_goal_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "mock"
    assert body["fallbackReason"] == "llm_error"
    assert body["errorType"] == "empty_content"
    assert body["structuredPlan"]["goalTitle"]


def test_goal_plan_model_output_truncated_is_reported(client, monkeypatch):
    class TruncatedOutputClient:
        settings = _settings()

        def complete(self, *args, **kwargs):
            return None, LlmError(
                "The model output was truncated before completion.",
                "model_output_truncated",
                0,
            )

    monkeypatch.setattr(planning_module, "LlmClient", lambda: TruncatedOutputClient())

    response = client.post("/api/planning/goal-plan", json=_goal_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "mock"
    assert body["fallbackReason"] == "llm_error"
    assert body["errorType"] == "model_output_truncated"
    assert body["structuredPlan"]["goalTitle"]


def test_goal_plan_mock_provider_reports_mock_fallback(client, monkeypatch):
    class MockProviderClient:
        settings = _settings(provider="mock", api_key="sk-test-local")

        def complete(self, *args, **kwargs):
            return None, None

    monkeypatch.setattr(planning_module, "LlmClient", lambda: MockProviderClient())

    response = client.post("/api/planning/goal-plan", json=_goal_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "mock"
    assert body["fallbackReason"] == "mock_provider"
    assert body["errorType"] is None


def test_goal_plan_llm_success_has_no_fallback_diagnostics(client, monkeypatch):
    class SuccessClient:
        settings = _settings()

        def complete(self, *args, **kwargs):
            return (
                LlmResult(
                    content='{"summary":"Live plan","structuredPlan":{"goalTitle":"Live Goal","goalDescription":"Live goal description","durationDays":7,"milestones":[{"title":"M1","description":"Milestone","tasks":[{"title":"Task","description":"Task detail","priority":"high","estimatedMinutes":45,"dueDate":null}]}],"reviewPlan":{"frequency":"daily","questions":["What improved today?"]}}}',
                    provider="deepseek",
                    model="deepseek-v4-flash",
                ),
                None,
            )

    monkeypatch.setattr(planning_module, "LlmClient", lambda: SuccessClient())

    response = client.post("/api/planning/goal-plan", json=_goal_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "llm"
    assert body["fallbackReason"] is None
    assert body["errorType"] is None
    assert body["baseUrlHost"] is None
    assert body["phases"][0]["title"] == "M1"
    assert body["tasks"][0]["title"] == "Task"


def test_goal_plan_llm_error_types_are_reported_safely(client, monkeypatch):
    error_types = [
        "auth_error",
        "bad_model",
        "bad_base_url",
        "network_error",
        "timeout",
        "insufficient_balance",
        "invalid_key_format",
        "model_output_truncated",
        "empty_content",
    ]

    for error_type in error_types:
        class ErrorClient:
            settings = _settings()

            def complete(self, *args, **kwargs):
                return None, LlmError(f"{error_type} happened", error_type, 0, detail="Authorization: Bearer secret")

        monkeypatch.setattr(planning_module, "LlmClient", lambda: ErrorClient())

        response = client.post("/api/planning/goal-plan", json=_goal_payload())

        assert response.status_code == 200
        body = response.json()
        assert body["fallbackReason"] == "llm_error"
        assert body["errorType"] == error_type
        assert body["baseUrlHost"] == "api.deepseek.com"
        combined = " ".join(str(body.get(key) or "") for key in ("errorMessage", "baseUrlHost"))
        assert "Bearer" not in combined
        assert "secret" not in combined
        assert "token=" not in combined


def test_local_structured_goal_plan_template_is_readable_chinese(client):
    response = client.post(
        "/api/planning/goal-plan",
        json={
            "goal": "学会 Python",
            "deadline": "2026-07-29",
            "dailyHours": 2,
            "materials": "",
            "preferences": "",
            "date": "2026-07-01",
        },
    )

    assert response.status_code == 200
    body = response.json()
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
    assert "阶段" in combined
    assert "Python" in combined
    assert "锛" not in combined
    assert "鍒" not in combined
    assert "乱码" not in combined


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
