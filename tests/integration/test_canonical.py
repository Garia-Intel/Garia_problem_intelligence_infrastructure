import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.canonical import CanonicalProblem, ProblemCanonicalization
from app.models.enums import CanonicalizationDecision


def create_candidate(client: TestClient, suffix: str = "001") -> dict[str, object]:
    response = client.post(
        "/api/v1/problems",
        json={
            "problem_id": f"PRB-CANONICAL-{suffix}",
            "title": "Candidate water access problem",
            "slug": f"candidate-water-access-problem-{suffix}",
            "summary": "Candidate evidence remains separately owned.",
        },
    )
    assert response.status_code == 201
    return response.json()


def create_canonical(client: TestClient, suffix: str = "one") -> dict[str, object]:
    response = client.post(
        "/api/v1/canonical-problems",
        json={
            "title": "Unequal water access in Kampala",
            "slug": f"unequal-water-access-kampala-{suffix}",
            "problem_statement": "Households experience unequal access to safe water.",
            "actor_id": "curator-1",
            "change_reason": "Initial canonical identity creation.",
        },
    )
    assert response.status_code == 201
    return response.json()


def lifecycle_payload(reason: str = "Lifecycle decision") -> dict[str, str]:
    return {"actor_id": "curator-1", "change_reason": reason}


def activate(client: TestClient, canonical: dict[str, object]) -> dict[str, object]:
    response = client.post(
        f"/api/v1/canonical-problems/{canonical['id']}/activate", json=lifecycle_payload()
    )
    assert response.status_code == 200
    return response.json()


def test_canonical_creation_identity_versions_and_audit(
    client: TestClient, db_session: Session
) -> None:
    canonical = create_canonical(client)
    assert canonical["canonical_id"].startswith("CP-")
    assert canonical["status"] == "draft"
    assert canonical["canonical_key"]
    detail = client.get(f"/api/v1/canonical-problems/{canonical['id']}").json()
    assert {key: detail[key] for key in canonical} == canonical
    assert detail["linked_candidates"] == []

    update = client.patch(
        f"/api/v1/canonical-problems/{canonical['id']}",
        json={
            "title": "Persistent unequal water access in Kampala",
            "actor_id": "curator-2",
            "change_reason": "Editorial clarification",
        },
    )
    assert update.status_code == 200
    assert update.json()["canonical_id"] == canonical["canonical_id"]
    assert update.json()["canonical_key"] == canonical["canonical_key"]

    history = client.get(f"/api/v1/canonical-problems/{canonical['id']}/versions")
    assert history.status_code == 200
    assert [item["version_number"] for item in history.json()] == [2, 1]
    assert history.json()[1]["snapshot"]["title"] == canonical["title"]
    assert history.json()[0]["snapshot"]["canonical_id"] == canonical["canonical_id"]
    assert (
        client.get(f"/api/v1/canonical-problems/{canonical['id']}/versions/latest").json()[
            "version_number"
        ]
        == 2
    )

    actions = set(
        db_session.scalars(
            select(AuditLog.action).where(AuditLog.entity_id == uuid.UUID(str(canonical["id"])))
        )
    )
    assert {"CANONICAL_PROBLEM_CREATED", "CANONICAL_PROBLEM_UPDATED"} <= actions
    assert "CANONICAL_PROBLEM_VERSION_CREATED" in actions


def test_lifecycle_transitions_and_invalid_states(client: TestClient) -> None:
    canonical = create_canonical(client)
    assert (
        client.post(
            f"/api/v1/canonical-problems/{canonical['id']}/archive", json=lifecycle_payload()
        ).status_code
        == 409
    )
    active = activate(client, canonical)
    assert active["status"] == "active"
    archived = client.post(
        f"/api/v1/canonical-problems/{canonical['id']}/archive", json=lifecycle_payload()
    )
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    assert archived.json()["archived_at"] is not None
    restored = client.post(
        f"/api/v1/canonical-problems/{canonical['id']}/restore", json=lifecycle_payload()
    )
    assert restored.status_code == 200
    assert restored.json()["status"] == "active"
    assert restored.json()["archived_at"] is None
    assert (
        client.post(
            f"/api/v1/canonical-problems/{canonical['id']}/retire", json=lifecycle_payload()
        ).status_code
        == 409
    )

    retired = create_canonical(client, "retired")
    assert (
        client.post(
            f"/api/v1/canonical-problems/{retired['id']}/retire", json=lifecycle_payload()
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/canonical-problems/{retired['id']}/activate", json=lifecycle_payload()
        ).status_code
        == 409
    )


def test_canonicalization_history_current_mapping_and_provenance(
    client: TestClient, db_session: Session
) -> None:
    candidate = create_candidate(client)
    canonical = activate(client, create_canonical(client))
    proposed = client.post(
        f"/api/v1/canonical-problems/{canonical['id']}/canonicalizations",
        json={
            "problem_id": candidate["id"],
            "decision": "link_proposed",
            "match_confidence": 0.72,
            "reason": "Similar affected population and location.",
            "actor_type": "deterministic_system",
            "actor_id": "resolver-1",
            "methodology_version": "canonicalization-v1",
        },
    )
    assert proposed.status_code == 201
    assert proposed.json()["is_current"] is True
    confirmed = client.post(
        f"/api/v1/canonical-problems/{canonical['id']}/canonicalizations",
        json={
            "problem_id": candidate["id"],
            "decision": "link_confirmed",
            "match_confidence": 0.94,
            "reason": "Human confirmed the candidate supports this identity.",
            "actor_type": "human",
            "actor_id": "curator-1",
            "supersedes_id": proposed.json()["id"],
        },
    )
    assert confirmed.status_code == 201
    current = client.get(f"/api/v1/problems/{candidate['id']}/canonicalization")
    assert current.status_code == 200
    assert current.json()["id"] == confirmed.json()["id"]
    history = client.get(f"/api/v1/canonical-problems/{canonical['id']}/canonicalizations")
    assert len(history.json()) == 2
    assert history.json()[1]["is_current"] is False

    # Linking does not alter the evidence-bearing candidate record or its provenance ownership.
    unchanged = client.get(f"/api/v1/problems/{candidate['id']}").json()
    assert unchanged["id"] == candidate["id"]
    assert unchanged["title"] == candidate["title"]
    mapping = db_session.get(ProblemCanonicalization, uuid.UUID(confirmed.json()["id"]))
    assert mapping is not None
    assert mapping.problem_id == uuid.UUID(candidate["id"])


def test_mapping_rejects_invalid_target_and_multiple_current_confirmed_links(
    client: TestClient,
) -> None:
    candidate = create_candidate(client)
    draft = create_canonical(client)
    payload = {
        "problem_id": candidate["id"],
        "decision": "link_confirmed",
        "reason": "Confirmed by a curator.",
        "actor_type": "human",
        "actor_id": "curator-1",
    }
    assert (
        client.post(
            f"/api/v1/canonical-problems/{draft['id']}/canonicalizations", json=payload
        ).status_code
        == 409
    )
    first = activate(client, draft)
    assert (
        client.post(
            f"/api/v1/canonical-problems/{first['id']}/canonicalizations", json=payload
        ).status_code
        == 201
    )
    second = activate(client, create_canonical(client, "second"))
    assert (
        client.post(
            f"/api/v1/canonical-problems/{second['id']}/canonicalizations", json=payload
        ).status_code
        == 409
    )
    missing_payload = {**payload, "problem_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"}
    assert (
        client.post(
            f"/api/v1/canonical-problems/{second['id']}/canonicalizations", json=missing_payload
        ).status_code
        == 404
    )


def test_merge_preserves_identities_candidate_mapping_and_versions(
    client: TestClient, db_session: Session
) -> None:
    candidate = create_candidate(client)
    source = activate(client, create_canonical(client, "source"))
    target = activate(client, create_canonical(client, "target"))
    link = client.post(
        f"/api/v1/canonical-problems/{source['id']}/canonicalizations",
        json={
            "problem_id": candidate["id"],
            "decision": "link_confirmed",
            "reason": "Candidate supports source identity.",
            "actor_type": "human",
            "actor_id": "curator-1",
        },
    )
    assert link.status_code == 201
    assert (
        client.post(
            f"/api/v1/canonical-problems/{source['id']}/merge",
            json={
                "target_canonical_problem_id": source["id"],
                "rationale": "Invalid self merge.",
                "actor_id": "curator-1",
            },
        ).status_code
        == 409
    )
    merge = client.post(
        f"/api/v1/canonical-problems/{source['id']}/merge",
        json={
            "target_canonical_problem_id": target["id"],
            "rationale": "Both identities represent the same persistent access problem.",
            "actor_id": "curator-1",
            "methodology_version": "merge-policy-v1",
        },
    )
    assert merge.status_code == 201
    source_after = client.get(f"/api/v1/canonical-problems/{source['id']}").json()
    assert source_after["id"] == source["id"]
    assert source_after["canonical_id"] == source["canonical_id"]
    assert source_after["status"] == "merged"
    assert source_after["merged_into_id"] == target["id"]
    assert (
        client.get(f"/api/v1/problems/{candidate['id']}/canonicalization").json()[
            "canonical_problem_id"
        ]
        == source["id"]
    )
    assert len(client.get(f"/api/v1/canonical-problems/{source['id']}/versions").json()) >= 3
    assert db_session.get(CanonicalProblem, uuid.UUID(source["id"])) is not None
    actions = set(
        db_session.scalars(
            select(AuditLog.action).where(AuditLog.entity_id == uuid.UUID(source["id"]))
        )
    )
    assert {"CANONICAL_MERGE_APPROVED", "CANONICAL_MERGE_EXECUTED"} <= actions


def test_database_partial_index_prevents_racing_current_confirmed_mappings(
    client: TestClient, db_session: Session
) -> None:
    candidate = create_candidate(client)
    canonical = activate(client, create_canonical(client))
    first = ProblemCanonicalization(
        problem_id=uuid.UUID(candidate["id"]),
        canonical_problem_id=uuid.UUID(canonical["id"]),
        decision=CanonicalizationDecision.LINK_CONFIRMED,
        reason="First concurrent decision.",
        actor_type="human",
        created_at=datetime.now(UTC),
        is_current=True,
    )
    second = ProblemCanonicalization(
        problem_id=uuid.UUID(candidate["id"]),
        canonical_problem_id=uuid.UUID(canonical["id"]),
        decision=CanonicalizationDecision.LINK_CONFIRMED,
        reason="Second concurrent decision.",
        actor_type="human",
        created_at=datetime.now(UTC),
        is_current=True,
    )
    db_session.add_all([first, second])
    try:
        db_session.commit()
    except IntegrityError:
        db_session.rollback()
    else:
        raise AssertionError(
            "Partial unique index must prevent duplicate current confirmed mappings."
        )
