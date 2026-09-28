import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def create_problem(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/v1/problems",
        json={
            "problem_id": "PRB-VERSION-001",
            "title": "Original water access problem",
            "slug": "original-water-access-problem",
            "summary": "Original summary",
            "category": "demo",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_problem_version_snapshots_are_immutable_and_audited(
    client: TestClient, db_session: Session
) -> None:
    problem = create_problem(client)
    first = client.post(
        f"/api/v1/problems/{problem['id']}/versions",
        json={"created_by": "reviewer-1", "change_reason": "Initial canonical problem creation"},
    )
    assert first.status_code == 201
    assert first.json()["version_number"] == 1
    assert first.json()["snapshot"]["id"] == problem["id"]
    assert first.json()["snapshot"]["status"] == "draft"
    assert isinstance(first.json()["snapshot"]["created_at"], str)
    assert (
        client.patch(
            f"/api/v1/problems/{problem['id']}", json={"title": "Updated water access problem"}
        ).status_code
        == 200
    )
    second = client.post(
        f"/api/v1/problems/{problem['id']}/versions",
        json={"created_by": "reviewer-2", "change_reason": "Editorial correction"},
    )
    assert second.json()["version_number"] == 2
    assert (
        client.get(f"/api/v1/problems/{problem['id']}/versions/1").json()["snapshot"]["title"]
        == "Original water access problem"
    )
    assert (
        client.get(f"/api/v1/problems/{problem['id']}/versions/latest").json()["id"]
        == second.json()["id"]
    )
    history = client.get(f"/api/v1/problems/{problem['id']}/versions").json()
    assert [item["version_number"] for item in history] == [2, 1]
    audits = list(
        db_session.scalars(
            select(AuditLog).where(
                AuditLog.entity_id == uuid.UUID(problem["id"]),
                AuditLog.action == "PROBLEM_VERSION_CREATED",
            )
        )
    )
    assert len(audits) == 2
    assert any(audit.new_data["version_number"] == 2 for audit in audits)
    assert any(audit.old_data["previous_version_number"] == 1 for audit in audits)


def test_problem_version_validation_and_not_found(client: TestClient) -> None:
    problem = create_problem(client)
    assert (
        client.post(
            f"/api/v1/problems/{problem['id']}/versions",
            json={"created_by": "", "change_reason": "reason"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/v1/problems/{problem['id']}/versions",
            json={"created_by": "user", "change_reason": ""},
        ).status_code
        == 422
    )
    missing = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert (
        client.post(
            f"/api/v1/problems/{missing}/versions",
            json={"created_by": "user", "change_reason": "reason"},
        ).status_code
        == 404
    )
