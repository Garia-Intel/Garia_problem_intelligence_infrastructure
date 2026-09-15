from fastapi.testclient import TestClient

from tests.integration.test_catalog import create_source


def human_review_problem(client: TestClient, suffix: str) -> str:
    problem = client.post(
        "/api/v1/problems",
        json={
            "problem_id": f"PRB-REV-{suffix}",
            "title": "Review candidate",
            "slug": f"review-candidate-{suffix.lower()}",
            "summary": "A reviewed candidate.",
            "category": "demo",
            "ai_generated": True,
        },
    ).json()
    source = create_source(client)
    client.post(
        f"/api/v1/problems/{problem['id']}/claims",
        json={
            "claim_id": f"CLM-REV-{suffix}",
            "statement": "Source-linked claim.",
            "claim_type": "fact",
            "source_id": source["id"],
        },
    )
    qa = client.post(f"/api/v1/problems/{problem['id']}/qa")
    assert qa.status_code == 200 and qa.json()["passed"]
    return problem["id"]


def test_approve_transitions_to_verification_required(client: TestClient) -> None:
    problem_id = human_review_problem(client, "APPROVE")
    response = client.post(
        f"/api/v1/problems/{problem_id}/reviews",
        json={
            "reviewer_id": "reviewer-1",
            "decision": "approve",
            "notes": "Structure is acceptable.",
            "changes": {"summary": "Reviewed."},
        },
    )
    assert response.status_code == 201
    assert response.json()["reviewer_id"] == "reviewer-1"
    assert response.json()["decision"] == "approve"
    problem = client.get(f"/api/v1/problems/{problem_id}").json()
    assert problem["status"] == "verification_required"


def test_needs_revision_remains_in_human_review_and_history_is_preserved(
    client: TestClient,
) -> None:
    problem_id = human_review_problem(client, "REVISE")
    first = client.post(
        f"/api/v1/problems/{problem_id}/reviews",
        json={"reviewer_id": "reviewer-1", "decision": "needs_revision", "notes": "Clarify scope."},
    )
    second = client.post(
        f"/api/v1/problems/{problem_id}/reviews",
        json={"reviewer_id": "reviewer-2", "decision": "needs_revision"},
    )
    history = client.get(f"/api/v1/problems/{problem_id}/reviews")
    latest = client.get(f"/api/v1/problems/{problem_id}/reviews/latest")
    assert client.get(f"/api/v1/problems/{problem_id}").json()["status"] == "human_review"
    assert [item["id"] for item in history.json()] == [second.json()["id"], first.json()["id"]]
    assert latest.json()["id"] == second.json()["id"]


def test_reject_and_invalid_states_are_blocked(client: TestClient) -> None:
    problem_id = human_review_problem(client, "REJECT")
    assert (
        client.post(
            f"/api/v1/problems/{problem_id}/reviews",
            json={"reviewer_id": "reviewer-1", "decision": "reject"},
        ).status_code
        == 201
    )
    assert client.get(f"/api/v1/problems/{problem_id}").json()["status"] == "rejected"
    blocked = client.post(
        f"/api/v1/problems/{problem_id}/reviews",
        json={"reviewer_id": "reviewer-2", "decision": "approve"},
    )
    assert blocked.status_code == 409


def test_review_validation_and_missing_problem(client: TestClient) -> None:
    missing = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert (
        client.post(
            f"/api/v1/problems/{missing}/reviews", json={"reviewer_id": "r", "decision": "approve"}
        ).status_code
        == 404
    )
    problem_id = human_review_problem(client, "EMPTY")
    assert (
        client.post(
            f"/api/v1/problems/{problem_id}/reviews",
            json={"reviewer_id": "", "decision": "approve"},
        ).status_code
        == 422
    )
