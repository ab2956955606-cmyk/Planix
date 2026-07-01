def test_rag_document_crud_and_bm25_query(client):
    created = client.post(
        "/api/rag/documents",
        json={
            "title": "Beijing AI application internship JD",
            "content": (
                "The role requires FastAPI, React, RAG, Agent workflow, Prompt Engineering, "
                "SQLite, and tool calling experience for AI application development."
            ),
            "sourceType": "paste",
        },
    )
    assert created.status_code == 200
    document = created.json()
    assert document["title"] == "Beijing AI application internship JD"
    assert document["chunks"] >= 1

    listed = client.get("/api/rag/documents")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [document["id"]]

    queried = client.post(
        "/api/rag/query",
        json={
            "goal": "prepare for AI application internship",
            "materials": "What should I improve first for RAG Agent FastAPI?",
            "date": "2026-07-01",
        },
    )
    assert queried.status_code == 200
    body = queried.json()
    assert body["mode"] == "mock"
    assert body["sources"]
    assert body["sources"][0]["documentId"] == document["id"]
    assert "FastAPI" in body["sources"][0]["chunk"]

    deleted = client.delete(f"/api/rag/documents/{document['id']}")
    assert deleted.status_code == 204

    queried_after_delete = client.post(
        "/api/rag/query",
        json={
            "goal": "prepare for AI application internship",
            "materials": "RAG Agent FastAPI",
            "date": "2026-07-01",
        },
    )
    assert queried_after_delete.status_code == 200
    assert queried_after_delete.json()["sources"] == []


def test_legacy_rag_ingest_still_writes_documents(client):
    response = client.post(
        "/api/rag/ingest",
        json={
            "title": "Course note",
            "content": "RAG retrieval should return source chunks with BM25 ranking.",
        },
    )
    assert response.status_code == 200
    assert response.json()["chunks"] >= 1

    listed = client.get("/api/rag/documents")
    assert listed.status_code == 200
    assert listed.json()[0]["title"] == "Course note"
