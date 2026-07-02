def test_health_endpoint(client):
    for path in ("/health", "/api/health"):
        body = client.get(path).json()
        assert body["status"] == "ok"
        assert body["app"] == "mynotes-api"
        assert isinstance(body["pid"], int)
        assert body["version"] == "1.1.4"
