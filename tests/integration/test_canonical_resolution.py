import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.canonical import CanonicalProblem, ProblemCanonicalization
from app.models.enums import CanonicalizationDecision


def candidate(client: TestClient, suffix: str) -> dict[str, object]:
    slug_suffix = suffix.replace("_", "-")
    response = client.post(
        "/api/v1/problems",
        json={
            "problem_id": f"PRB-RESOLUTION-{suffix}",
            "title": f"Candidate problem {suffix}",
            "slug": f"candidate-problem-{slug_suffix}",
            "summary": "Source-backed candidate metadata must remain unchanged.",
        },
    )
    assert response.status_code == 201
    return response.json()


def canonical(client: TestClient, suffix: str, activate: bool = True) -> dict[str, object]:
    created = client.post(
        "/api/v1/canonical-problems",
        json={
            "title": f"Canonical problem {suffix}",
            "slug": f"canonical-problem-{suffix}",
            "problem_statement": "A curated identity statement.",
            "actor_id": "curator-1",
            "change_reason": "Created for identity resolution.",
        },
    )
    assert created.status_code == 201
    if not activate:
        return created.json()
    active = client.post(
        f"/api/v1/canonical-problems/{created.json()['id']}/activate",
        json={"actor_id": "curator-1", "change_reason": "Ready for matching."},
    )
    assert active.status_code == 200
    return active.json()


def decision_payload(
    decision: str, canonical_problem_id: str | None = None, **extra: object
) -> dict[str, object]:
    result: dict[str, object] = {
        "decision": decision,
        "canonical_problem_id": canonical_problem_id,
        "match_confidence": 0.81,
        "reason": f"Controlled {decision} assessment.",
        "actor_type": "human",
        "actor_id": "curator-1",
        "methodology_version": "canonical-resolution-v1",
    }
    result.update(extra)
    return result


def resolve(client: TestClient, problem: dict[str, object], payload: dict[str, object]):
    return client.post(f"/api/v1/problems/{problem['id']}/canonicalization", json=payload)


def test_create_canonical_resolution_is_atomic_audited_and_preserves_candidate(
    client: TestClient, db_session: Session
) -> None:
    problem = candidate(client, "create")
    response = resolve(
        client,
        problem,
        decision_payload(
            "create_canonical",
            canonical_identity={
                "title": "New curated water identity",
                "slug": "new-curated-water-identity",
                "problem_statement": "Curated identity is created under human control.",
            },
        ),
    )
    assert response.status_code == 201
    mapping = response.json()
    assert mapping["decision"] == "create_canonical"
    assert mapping["canonical_problem_id"] is not None
    assert (
        client.get(f"/api/v1/problems/{problem['id']}/canonicalization/current").status_code == 404
    )
    created = client.get(f"/api/v1/canonical-problems/{mapping['canonical_problem_id']}").json()
    assert created["status"] == "draft"
    assert client.get(f"/api/v1/problems/{problem['id']}").json()["title"] == problem["title"]
    actions = set(
        db_session.scalars(
            select(AuditLog.action).where(AuditLog.entity_id == uuid.UUID(mapping["id"]))
        )
    )
    assert "CANONICAL_RESOLUTION_COMPLETED" in actions

    duplicate = resolve(
        client,
        candidate(client, "rollback"),
        decision_payload(
            "create_canonical",
            canonical_identity={
                "title": "Duplicate slug identity",
                "slug": "new-curated-water-identity",
                "problem_statement": "This must fail atomically.",
            },
        ),
    )
    assert duplicate.status_code == 409
    assert (
        db_session.scalar(
            select(CanonicalProblem).where(CanonicalProblem.title == "Duplicate slug identity")
        )
        is None
    )


def test_proposed_and_assessment_decisions_do_not_create_current_mapping(
    client: TestClient,
) -> None:
    target = canonical(client, "assessments")
    for decision in (
        "link_proposed",
        "not_same_problem",
        "related_only",
        "insufficient_evidence",
        "candidate_rejected",
    ):
        problem = candidate(client, decision)
        target_id = None if decision == "candidate_rejected" else target["id"]
        response = resolve(client, problem, decision_payload(decision, target_id))
        assert response.status_code == 201
        assert response.json()["decision"] == decision
        assert response.json()["canonical_problem_id"] == target_id
        assert (
            client.get(f"/api/v1/problems/{problem['id']}/canonicalization/current").status_code
            == 404
        )
        history = client.get(f"/api/v1/problems/{problem['id']}/canonicalization/history")
        assert history.status_code == 200
        assert len(history.json()) == 1


def test_confirmation_supersession_and_current_mapping_invariant(
    client: TestClient, db_session: Session
) -> None:
    problem = candidate(client, "confirmed")
    first_target = canonical(client, "first")
    second_target = canonical(client, "second")
    first = resolve(client, problem, decision_payload("link_confirmed", first_target["id"]))
    assert first.status_code == 201
    assert (
        client.get(f"/api/v1/problems/{problem['id']}/canonicalization").json()["id"]
        == first.json()["id"]
    )
    assert (
        resolve(
            client, problem, decision_payload("link_confirmed", second_target["id"])
        ).status_code
        == 409
    )
    replacement = resolve(
        client,
        problem,
        decision_payload("link_confirmed", second_target["id"], supersedes_id=first.json()["id"]),
    )
    assert replacement.status_code == 201
    assert replacement.json()["is_current"] is True
    history = client.get(f"/api/v1/problems/{problem['id']}/canonicalization/history").json()
    assert [item["is_current"] for item in history] == [True, False]
    assert (
        client.get(f"/api/v1/problems/{problem['id']}/canonicalization/current").json()[
            "canonical_problem_id"
        ]
        == second_target["id"]
    )
    actions = set(
        db_session.scalars(
            select(AuditLog.action).where(AuditLog.entity_id == uuid.UUID(first.json()["id"]))
        )
    )
    assert "CANONICAL_LINK_SUPERSEDED" in actions


@pytest.mark.parametrize("state", ["retired", "merged"])
def test_invalid_canonical_target_states_are_rejected(client: TestClient, state: str) -> None:
    problem = candidate(client, state)
    target = canonical(client, f"{state}-target")
    if state == "retired":
        target = canonical(client, "retired-draft", activate=False)
        assert (
            client.post(
                f"/api/v1/canonical-problems/{target['id']}/retire",
                json={"actor_id": "curator-1", "change_reason": "Not viable."},
            ).status_code
            == 200
        )
    else:
        survivor = canonical(client, "merge-survivor")
        assert (
            client.post(
                f"/api/v1/canonical-problems/{target['id']}/merge",
                json={
                    "target_canonical_problem_id": survivor["id"],
                    "rationale": "Duplicate identity.",
                    "actor_id": "curator-1",
                },
            ).status_code
            == 201
        )
    assert (
        resolve(client, problem, decision_payload("link_proposed", target["id"])).status_code == 409
    )


def test_target_validation_and_schema_validation(client: TestClient) -> None:
    problem = candidate(client, "validation")
    draft = canonical(client, "draft", activate=False)
    assert (
        resolve(client, problem, decision_payload("link_confirmed", draft["id"])).status_code == 409
    )
    assert (
        resolve(
            client,
            problem,
            decision_payload("link_proposed", "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        ).status_code
        == 404
    )
    invalid_confidence = decision_payload("candidate_rejected")
    invalid_confidence["match_confidence"] = 1.1
    assert resolve(client, problem, invalid_confidence).status_code == 422
    assert resolve(client, problem, decision_payload("link_proposed", None)).status_code == 409


@pytest.mark.parametrize(
    "decision",
    [
        "link_proposed",
        "link_confirmed",
        "not_same_problem",
        "related_only",
        "insufficient_evidence",
    ],
)
def test_targeted_resolution_decisions_require_a_canonical_target(
    client: TestClient, decision: str
) -> None:
    problem = candidate(client, f"target-required-{decision}")
    assert resolve(client, problem, decision_payload(decision, None)).status_code == 409


def test_database_constraint_allows_only_rejection_without_target(
    client: TestClient, db_session: Session
) -> None:
    problem = candidate(client, "database-constraint")
    target = canonical(client, "database-constraint")
    invalid_without_target = ProblemCanonicalization(
        problem_id=uuid.UUID(problem["id"]),
        canonical_problem_id=None,
        decision=CanonicalizationDecision.LINK_PROPOSED,
        reason="This relationship decision lacks a target.",
        actor_type="human",
        created_at=datetime.now(UTC),
        is_current=True,
    )
    db_session.add(invalid_without_target)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
    invalid_rejection_target = ProblemCanonicalization(
        problem_id=uuid.UUID(problem["id"]),
        canonical_problem_id=uuid.UUID(target["id"]),
        decision=CanonicalizationDecision.CANDIDATE_REJECTED,
        reason="A rejected candidate must not have a target.",
        actor_type="human",
        created_at=datetime.now(UTC),
        is_current=True,
    )
    db_session.add(invalid_rejection_target)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
    accepted = resolve(client, problem, decision_payload("candidate_rejected"))
    assert accepted.status_code == 201
    assert accepted.json()["canonical_problem_id"] is None


def test_legacy_endpoint_delegates_and_rejects_obsolete_decisions(
    client: TestClient, db_session: Session
) -> None:
    problem = candidate(client, "legacy-endpoint")
    target = canonical(client, "legacy-endpoint")
    endpoint = f"/api/v1/canonical-problems/{target['id']}/canonicalizations"
    common = {
        "problem_id": problem["id"],
        "reason": "Legacy compatibility request.",
        "actor_type": "human",
        "actor_id": "curator-1",
    }
    rejected = client.post(endpoint, json={**common, "decision": "candidate_rejected"})
    assert rejected.status_code == 409
    create = client.post(endpoint, json={**common, "decision": "create_canonical"})
    assert create.status_code == 409
    proposed = client.post(
        endpoint,
        json={**common, "decision": "link_proposed", "match_confidence": 0.7},
    )
    assert proposed.status_code == 201
    actions = set(
        db_session.scalars(
            select(AuditLog.action).where(AuditLog.entity_id == uuid.UUID(proposed.json()["id"]))
        )
    )
    assert "CANONICAL_LINK_PROPOSED" in actions
