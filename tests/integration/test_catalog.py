from fastapi.testclient import TestClient


def create_source(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/v1/sources",
        json={
            "name": "Demo research source",
            "publisher": "Garia Demo",
            "source_type": "research_paper",
            "url": "https://example.org/demo",
            "country": "Uganda",
            "language": "en",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_create_and_retrieve_source(client: TestClient) -> None:
    source = create_source(client)

    response = client.get(f"/api/v1/sources/{source['id']}")

    assert response.status_code == 200
    assert response.json()["name"] == "Demo research source"


def test_create_document_for_source(client: TestClient) -> None:
    source = create_source(client)
    response = client.post(
        "/api/v1/documents",
        json={"source_id": source["id"], "title": "Demo document", "content": "Demo content."},
    )

    assert response.status_code == 201
    assert response.json()["source_id"] == source["id"]


def test_document_rejects_unknown_source(client: TestClient) -> None:
    response = client.post(
        "/api/v1/documents",
        json={"source_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "title": "Orphan"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SOURCE_NOT_FOUND"


def test_create_and_soft_delete_problem(client: TestClient) -> None:
    payload = {"problem_id": "PRB-DEMO-001", "title": "Demo problem", "slug": "demo-problem"}
    created = client.post("/api/v1/problems", json=payload)
    assert created.status_code == 201

    deleted = client.delete(f"/api/v1/problems/{created.json()['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/problems/{created.json()['id']}").status_code == 404


def test_validation_error_has_consistent_shape(client: TestClient) -> None:
    response = client.post("/api/v1/sources", json={"name": "Missing fields"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
