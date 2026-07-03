from backend.app.db import get_conn
from backend.app.services.ai_settings import EffectiveAiSettings
from backend.app.services import llm as llm_module
from backend.app.services.llm import _chat_completions_url
from backend.app.services.llm import _effective_max_tokens, _message_content


def test_ai_settings_are_saved_without_exposing_key(client):
    saved = client.put(
        "/api/ai/settings",
        json={
            "provider": "deepseek",
            "baseUrl": "https://api.deepseek.com",
            "model": "deepseek-v4-flash",
            "apiKey": "sk-test-local",
            "temperature": 0.2,
            "timeoutSeconds": 30,
        },
    )
    assert saved.status_code == 200
    body = saved.json()
    assert body["provider"] == "deepseek"
    assert body["hasApiKey"] is True
    assert "apiKey" not in body

    loaded = client.get("/api/ai/settings")
    assert loaded.status_code == 200
    assert loaded.json()["hasApiKey"] is True
    assert "apiKey" not in loaded.json()


def test_ai_settings_test_uses_mock_without_key(client):
    saved = client.put(
        "/api/ai/settings",
        json={
            "provider": "mock",
            "baseUrl": "https://api.deepseek.com",
            "model": "deepseek-v4-flash",
            "apiKey": "",
            "temperature": 0.3,
            "timeoutSeconds": 20,
        },
    )
    assert saved.status_code == 200
    assert saved.json()["hasApiKey"] is False

    tested = client.post("/api/ai/test", json={"prompt": "ping"})
    assert tested.status_code == 200
    body = tested.json()
    assert body["ok"] is True
    assert body["mode"] == "mock"


def test_blank_api_key_clears_saved_key(client):
    first = client.put(
        "/api/ai/settings",
        json={
            "provider": "deepseek",
            "baseUrl": "https://api.deepseek.com",
            "model": "deepseek-v4-flash",
            "apiKey": "sk-test-local",
            "temperature": 0.3,
            "timeoutSeconds": 20,
        },
    )
    assert first.status_code == 200
    assert first.json()["hasApiKey"] is True

    cleared = client.put(
        "/api/ai/settings",
        json={
            "provider": "deepseek",
            "baseUrl": "https://api.deepseek.com",
            "model": "deepseek-v4-flash",
            "apiKey": "",
            "temperature": 0.3,
            "timeoutSeconds": 20,
        },
    )
    assert cleared.status_code == 200
    assert cleared.json()["hasApiKey"] is False
    assert client.get("/api/ai/settings").json()["hasApiKey"] is False


def test_missing_api_key_does_not_preserve_stale_key(client):
    first = client.put(
        "/api/ai/settings",
        json={
            "provider": "deepseek",
            "baseUrl": "https://api.deepseek.com",
            "model": "deepseek-v4-flash",
            "apiKey": "sk-test-local",
            "temperature": 0.3,
            "timeoutSeconds": 20,
        },
    )
    assert first.status_code == 200
    assert first.json()["hasApiKey"] is True

    saved = client.put(
        "/api/ai/settings",
        json={
            "provider": "deepseek",
            "baseUrl": "https://api.deepseek.com",
            "model": "deepseek-v4-flash",
            "temperature": 0.3,
            "timeoutSeconds": 20,
        },
    )
    assert saved.status_code == 200
    assert saved.json()["hasApiKey"] is False


def test_invalid_api_key_format_is_rejected(client):
    saved = client.put(
        "/api/ai/settings",
        json={
            "provider": "deepseek",
            "baseUrl": "https://api.deepseek.com",
            "model": "deepseek-v4-flash",
            "apiKey": "saved DeepSeek key",
            "temperature": 0.3,
            "timeoutSeconds": 20,
        },
    )
    assert saved.status_code == 422
    detail = str(saved.json()["detail"])
    assert "plain ASCII without spaces" in detail


def test_saved_empty_key_does_not_fallback_to_env(client, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-env-local")
    saved = client.put(
        "/api/ai/settings",
        json={
            "provider": "deepseek",
            "baseUrl": "https://api.deepseek.com",
            "model": "deepseek-v4-flash",
            "apiKey": "",
            "temperature": 0.3,
            "timeoutSeconds": 20,
        },
    )
    assert saved.status_code == 200
    assert saved.json()["hasApiKey"] is False
    assert client.get("/api/ai/settings").json()["hasApiKey"] is False


def test_legacy_cached_key_is_not_trusted(client):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO ai_settings(
              id, provider, base_url, model, api_key_encrypted,
              temperature, timeout_seconds, updated_at
            )
            VALUES (
              'local-default', 'deepseek', 'https://api.deepseek.com',
              'deepseek-v4-flash', 'sk-legacy-local', 0.3, 20, CURRENT_TIMESTAMP
            )
            """
        )

    loaded = client.get("/api/ai/settings")
    assert loaded.status_code == 200
    assert loaded.json()["hasApiKey"] is False


def test_deepseek_url_does_not_add_v1():
    assert _chat_completions_url("https://api.deepseek.com", "deepseek") == "https://api.deepseek.com/chat/completions"
    assert _chat_completions_url("https://api.deepseek.com/", "deepseek") == "https://api.deepseek.com/chat/completions"
    assert _chat_completions_url("https://api.deepseek.com/v1", "deepseek") == "https://api.deepseek.com/chat/completions"


def test_deepseek_reasoning_models_get_minimum_token_budget():
    settings = EffectiveAiSettings(
        provider="deepseek",
        base_url="https://api.deepseek.com",
        model="deepseek-v4-flash",
        api_key="sk-test-local",
        temperature=0.1,
        timeout_seconds=10,
        updated_at="",
    )
    assert _effective_max_tokens(settings, 32) == 512


def test_message_content_rejects_empty_text():
    assert _message_content({"content": ""}) == ""
    assert _message_content({"content": [{"type": "text", "text": "OK"}]}) == "OK"


def test_deepseek_key_stays_mock_without_real_llm_gate(client):
    saved = client.put(
        "/api/ai/settings",
        json={
            "provider": "deepseek",
            "baseUrl": "https://api.deepseek.com",
            "model": "deepseek-v4-flash",
            "apiKey": "sk-test-local",
            "temperature": 0.1,
            "timeoutSeconds": 10,
        },
    )
    assert saved.status_code == 200

    tested = client.post("/api/ai/test", json={"prompt": "ping"})
    assert tested.status_code == 200
    body = tested.json()
    assert body["ok"] is True
    assert body["mode"] == "mock"


def test_llm_rejects_invalid_key_format_before_request(monkeypatch):
    monkeypatch.setenv("USE_REAL_LLM", "1")
    monkeypatch.setattr(
        llm_module,
        "get_effective_ai_settings",
        lambda: EffectiveAiSettings(
            provider="deepseek",
            base_url="https://api.deepseek.com",
            model="deepseek-v4-flash",
            api_key="已保存 DeepSeek",
            temperature=0.1,
            timeout_seconds=10,
            updated_at="",
        ),
    )

    result, error = llm_module.LlmClient().complete("settings_test", "system", "user")

    assert result is None
    assert error is not None
    assert error.error_type == "invalid_key_format"
    assert "plain ASCII without spaces" in error.message
