from fastapi.testclient import TestClient

from tests.integration.test_catalog import create_source


def create_problem(client: TestClient) -> str:
    response = client.post(
        "/api/v1/problems",
        json={
            "problem_id": "PRB-PIPE-001",
            "title": "Pipeline problem",
            "slug": "pipeline-problem",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_processing_is_idempotent(client: TestClient) -> None:
    source = create_source(client)
    first = client.post(f"/api/v1/sources/{source['id']}/process", json={})
    second = client.post(f"/api/v1/sources/{source['id']}/process", json={})
    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


def test_publish_requires_review_and_sourced_claim(client: TestClient) -> None:
    problem_id = create_problem(client)
    assert (
        client.post(f"/api/v1/problems/{problem_id}/publish?reviewer_id=reviewer").status_code
        == 409
    )
    source = create_source(client)
    claim = client.post(
        f"/api/v1/problems/{problem_id}/claims",
        json={
            "claim_id": "CLM-1",
            "statement": "Demo supported assertion.",
            "claim_type": "fact",
            "source_id": source["id"],
        },
    )
    assert claim.status_code == 201
    assert client.post(f"/api/v1/problems/{problem_id}/qa").status_code == 200
    review = client.post(
        f"/api/v1/problems/{problem_id}/review",
        json={"reviewer_id": "reviewer", "decision": "approve"},
    )
    assert review.status_code == 201
    assert (
        client.post(f"/api/v1/problems/{problem_id}/publish?reviewer_id=reviewer").status_code
        == 200
    )


def test_statistic_rejects_invalid_percentage(client: TestClient) -> None:
    source = create_source(client)
    problem_id = create_problem(client)
    response = client.post(
        f"/api/v1/problems/{problem_id}/statistics",
        json={
            "indicator": "demo",
            "source_id": source["id"],
            "document_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "value_numeric": 101,
            "unit": "%",
        },
    )
    assert response.status_code == 422
