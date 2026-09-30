from fastapi.testclient import TestClient

from tests.integration.test_canonical import activate, create_candidate, create_canonical
from tests.integration.test_verifications import payload, verification_required_problem


def link(client: TestClient, canonical: dict[str, object], candidate: dict[str, object]) -> None:
    response = client.post(
        f"/api/v1/canonical-problems/{canonical['id']}/canonicalizations",
        json={
            "problem_id": candidate["id"],
            "decision": "link_confirmed",
            "reason": "Confirmed current candidate.",
            "actor_type": "human",
            "actor_id": "curator-1",
        },
    )
    assert response.status_code == 201


def test_canonical_list_is_paginated_stable_and_filterable(client: TestClient) -> None:
    active = activate(client, create_canonical(client, "read-active"))
    draft = create_canonical(client, "read-draft")
    listed = client.get("/api/v1/canonical-problems?page=1&page_size=1")
    assert listed.status_code == 200
    assert listed.json()["page_size"] == 1
    assert listed.json()["total"] == 2
    filtered = client.get("/api/v1/canonical-problems?status=active")
    assert [item["id"] for item in filtered.json()["items"]] == [active["id"]]
    assert draft["id"] not in [item["id"] for item in filtered.json()["items"]]
    assert client.get("/api/v1/canonical-problems?page_size=101").status_code == 422


def test_detail_and_empty_read_summaries_do_not_mutate_state(client: TestClient) -> None:
    canonical = activate(client, create_canonical(client, "read-empty"))
    before = client.get(f"/api/v1/canonical-problems/{canonical['id']}").json()
    provenance = client.get(f"/api/v1/canonical-problems/{canonical['id']}/provenance")
    quality = client.get(f"/api/v1/canonical-problems/{canonical['id']}/quality")
    after = client.get(f"/api/v1/canonical-problems/{canonical['id']}").json()
    assert provenance.status_code == 200
    assert provenance.json()["candidate_count"] == 0
    assert quality.json()["items"] == []
    assert before["updated_at"] == after["updated_at"]


def test_detail_includes_only_current_confirmed_candidates(client: TestClient) -> None:
    canonical = activate(client, create_canonical(client, "read-linked"))
    confirmed = create_candidate(client, "read-confirmed")
    proposed = create_candidate(client, "read-proposed")
    link(client, canonical, confirmed)
    proposal = client.post(
        f"/api/v1/canonical-problems/{canonical['id']}/canonicalizations",
        json={
            "problem_id": proposed["id"],
            "decision": "link_proposed",
            "reason": "Proposal only.",
            "actor_type": "human",
            "actor_id": "curator-1",
        },
    )
    assert proposal.status_code == 201
    detail = client.get(f"/api/v1/canonical-problems/{canonical['id']}").json()
    assert [item["problem_id"] for item in detail["linked_candidates"]] == [confirmed["id"]]
    assert detail["provenance"]["candidate_count"] == 1


def test_provenance_and_quality_are_derived_from_linked_candidate_domains(
    client: TestClient,
) -> None:
    problem_id, source, document, claim = verification_required_problem(client, "CANONICAL-READ")
    canonical = activate(client, create_canonical(client, "read-provenance"))
    linked = client.post(
        f"/api/v1/canonical-problems/{canonical['id']}/canonicalizations",
        json={
            "problem_id": problem_id,
            "decision": "link_confirmed",
            "reason": "Candidate has an authoritative provenance chain.",
            "actor_type": "human",
            "actor_id": "curator-1",
        },
    )
    assert linked.status_code == 201
    evidence = client.post(
        f"/api/v1/claims/{claim['id']}/evidence",
        json={
            "document_id": document["id"],
            "evidence_type": "direct_quote",
            "excerpt": "Evidence remains attached to the claim.",
            "page_number": 1,
        },
    )
    assert evidence.status_code == 201
    assert (
        client.post(
            f"/api/v1/problems/{problem_id}/claims/{claim['id']}/verification",
            json=payload("verified"),
        ).status_code
        == 201
    )
    generated = client.post(f"/api/v1/problems/{problem_id}/quality-score")
    assert generated.status_code == 201
    provenance = client.get(f"/api/v1/canonical-problems/{canonical['id']}/provenance").json()
    assert provenance["claim_count"] == 1
    assert provenance["evidence_count"] == 1
    assert provenance["documents"][0]["id"] == document["id"]
    assert provenance["sources"][0]["id"] == source["id"]
    quality = client.get(f"/api/v1/canonical-problems/{canonical['id']}/quality").json()
    assert quality["items"][0]["problem_id"] == problem_id
    assert quality["items"][0]["quality_score_id"] == generated.json()["id"]
