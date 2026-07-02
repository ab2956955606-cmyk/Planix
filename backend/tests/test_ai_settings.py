from backend.app.services.llm import _chat_completions_url


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

    tested = client.post("/api/ai/test", json={"prompt": "ping"})
    assert tested.status_code == 200
    body = tested.json()
    assert body["ok"] is True
    assert body["mode"] == "mock"


def test_deepseek_url_does_not_add_v1():
    assert _chat_completions_url("https://api.deepseek.com", "deepseek") == "https://api.deepseek.com/chat/completions"
    assert _chat_completions_url("https://api.deepseek.com/", "deepseek") == "https://api.deepseek.com/chat/completions"
    assert _chat_completions_url("https://api.deepseek.com/v1", "deepseek") == "https://api.deepseek.com/chat/completions"


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
