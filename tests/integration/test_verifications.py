import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from tests.integration.test_catalog import create_source


def verification_required_problem(
    client: TestClient, suffix: str
) -> tuple[str, dict[str, object], dict[str, object], dict[str, object]]:
    problem = client.post(
        "/api/v1/problems",
        json={
            "problem_id": f"PRB-VER-{suffix}",
            "title": "Verification candidate",
            "slug": f"verification-candidate-{suffix.lower()}",
            "summary": "Candidate ready for factual verification.",
            "category": "demo",
            "ai_generated": True,
        },
    ).json()
    source = create_source(client)
    document = client.post(
        "/api/v1/documents",
        json={
            "source_id": source["id"],
            "title": "Verification document",
            "content": "Demo source text.",
        },
    ).json()
    claim = client.post(
        f"/api/v1/problems/{problem['id']}/claims",
        json={
            "claim_id": f"CLM-VER-{suffix}",
            "statement": "A source linked assertion.",
            "claim_type": "fact",
            "source_id": source["id"],
            "document_id": document["id"],
        },
    ).json()
    assert client.post(f"/api/v1/problems/{problem['id']}/qa").json()["passed"]
    assert (
        client.post(
            f"/api/v1/problems/{problem['id']}/reviews",
            json={"reviewer_id": "reviewer", "decision": "approve"},
        ).status_code
        == 201
    )
    return problem["id"], source, document, claim


def payload(status: str) -> dict[str, str]:
    return {
        "verifier_id": "verifier-1",
        "status": status,
        "method": "document_check",
        "notes": "Checked against cited document.",
    }


def test_claim_verification_history_status_and_audit(
    client: TestClient, db_session: Session
) -> None:
    problem_id, _, _, claim = verification_required_problem(client, "CLAIM")
    first = client.post(
        f"/api/v1/problems/{problem_id}/claims/{claim['id']}/verification",
        json=payload("partially_verified"),
    )
    second = client.post(
        f"/api/v1/problems/{problem_id}/claims/{claim['id']}/verification", json=payload("verified")
    )
    assert first.status_code == second.status_code == 201
    assert (
        client.get(f"/api/v1/problems/{problem_id}/claims").json()[0]["verification_status"]
        == "verified"
    )
    history = client.get(f"/api/v1/problems/{problem_id}/claims/{claim['id']}/verification")
    assert [item["id"] for item in history.json()] == [second.json()["id"], first.json()["id"]]
    audits = list(
        db_session.scalars(
            select(AuditLog).where(
                AuditLog.entity_id == uuid.UUID(claim["id"]),
                AuditLog.action == "CLAIM_VERIFIED",
            )
        )
    )
    assert any(audit.new_data["verification_status"] == "verified" for audit in audits)


def test_claim_disputed_and_rejected_are_supported(client: TestClient) -> None:
    problem_id, _, _, claim = verification_required_problem(client, "DISPUTE")
    assert (
        client.post(
            f"/api/v1/problems/{problem_id}/claims/{claim['id']}/verification",
            json=payload("disputed"),
        ).status_code
        == 201
    )
    rejected = client.post(
        f"/api/v1/problems/{problem_id}/claims/{claim['id']}/verification", json=payload("rejected")
    )
    assert rejected.status_code == 201


def test_statistic_verification_and_ownership_state_guards(client: TestClient) -> None:
    problem_id, source, document, claim = verification_required_problem(client, "STAT")
    statistic = client.post(
        f"/api/v1/problems/{problem_id}/statistics",
        json={
            "indicator": "Demo percentage",
            "source_id": source["id"],
            "document_id": document["id"],
            "claim_id": claim["id"],
            "value_numeric": 41,
            "unit": "%",
            "year": 2025,
        },
    ).json()
    verified = client.post(
        f"/api/v1/problems/{problem_id}/statistics/{statistic['id']}/verification",
        json=payload("verified"),
    )
    assert verified.status_code == 201
    assert (
        client.get(f"/api/v1/problems/{problem_id}/statistics").json()[0]["verification_status"]
        == "verified"
    )
    other_problem = client.post(
        "/api/v1/problems",
        json={
            "problem_id": "PRB-VER-OTHER",
            "title": "Other",
            "slug": "other-verification-candidate",
        },
    ).json()
    assert (
        client.post(
            f"/api/v1/problems/{other_problem['id']}/statistics/{statistic['id']}/verification",
            json=payload("disputed"),
        ).status_code
        == 409
    )


def test_verification_validation_and_invalid_state(client: TestClient) -> None:
    problem_id, _, _, claim = verification_required_problem(client, "INVALID")
    assert (
        client.post(
            f"/api/v1/problems/{problem_id}/claims/{claim['id']}/verification",
            json=payload("unverified"),
        ).status_code
        == 422
    )
    missing = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert (
        client.post(
            f"/api/v1/problems/{problem_id}/claims/{missing}/verification", json=payload("verified")
        ).status_code
        == 404
    )
    draft = client.post(
        "/api/v1/problems",
        json={
            "problem_id": "PRB-VER-DRAFT",
            "title": "Draft",
            "slug": "draft-verification-candidate",
        },
    ).json()
    assert (
        client.post(
            f"/api/v1/problems/{draft['id']}/claims/{claim['id']}/verification",
            json=payload("verified"),
        ).status_code
        == 409
    )
