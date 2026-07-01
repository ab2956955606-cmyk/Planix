def test_goal_plan_returns_and_persists_mock_result(client):
    response = client.post(
        "/api/planning/goal-plan",
        json={
            "goal": "3 months to land a Beijing AI application internship",
            "deadline": "2026-09-30",
            "dailyHours": 3,
            "materials": "FastAPI React RAG Agent",
            "preferences": "Deep work in the morning",
            "date": "2026-07-01",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"]
    assert body["mode"] == "mock"
    assert body["summary"]
    assert len(body["phases"]) >= 1
    assert len(body["tasks"]) >= 1


def test_goal_plan_returns_rag_sources_when_documents_match(client):
    document = client.post(
        "/api/rag/documents",
        json={
            "title": "AI internship JD",
            "content": "AI application internships value RAG, FastAPI, React, Agent tools, and evaluation.",
        },
    ).json()

    response = client.post(
        "/api/planning/goal-plan",
        json={
            "goal": "Build a strong AI application internship portfolio",
            "deadline": "2026-09-30",
            "dailyHours": 3,
            "materials": "RAG FastAPI Agent evaluation",
            "preferences": "Deep work in the morning",
            "date": "2026-07-01",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["sources"]
    assert body["sources"][0]["documentId"] == document["id"]


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
