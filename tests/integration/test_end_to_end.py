import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.claim import Claim
from app.models.evidence import Evidence
from app.models.pipeline import ExtractionRun
from app.models.problem_version import ProblemVersion
from app.models.quality import QualityScore
from app.models.statistic import Statistic
from app.models.verification import Verification


def verification_payload(status: str) -> dict[str, str]:
    return {
        "verifier_id": "verifier-e2e",
        "status": status,
        "method": "document_check",
        "notes": "Checked against the cited research document.",
    }


def create_e2e_record(client: TestClient, db_session: Session) -> dict[str, str]:
    source = client.post(
        "/api/v1/sources",
        json={
            "name": "E2E research source",
            "publisher": "Garia Demo Research",
            "source_type": "research_report",
            "url": "https://example.org/e2e-report",
            "country": "Uganda",
            "language": "en",
            "publication_date": "2025-01-01",
            "content": "Demo research content for extraction provenance.",
        },
    ).json()
    document = client.post(
        "/api/v1/documents",
        json={
            "source_id": source["id"],
            "title": "E2E research document",
            "content": "Traceable demo content.",
        },
    ).json()
    extraction = client.post(f"/api/v1/sources/{source['id']}/process", json={}).json()
    problem = client.post(
        "/api/v1/problems",
        json={
            "problem_id": "PRB-E2E-001",
            "title": "Demo access constraint",
            "slug": "demo-access-constraint",
            "summary": "A traceable research-derived candidate.",
            "category": "demo",
            "ai_generated": True,
        },
    ).json()
    assert (
        client.patch(
            f"/api/v1/problems/{problem['id']}", json={"status": "ai_extracted"}
        ).status_code
        == 200
    )
    claim = client.post(
        f"/api/v1/problems/{problem['id']}/claims",
        json={
            "claim_id": "CLM-E2E-001",
            "statement": "The demo source reports an access constraint.",
            "claim_type": "fact",
            "source_id": source["id"],
            "document_id": document["id"],
            "page_number": 1,
        },
    ).json()
    evidence = client.post(
        f"/api/v1/claims/{claim['id']}/evidence",
        json={
            "document_id": document["id"],
            "evidence_type": "reported_finding",
            "excerpt": "Short demo evidence reference.",
            "page_number": 1,
        },
    ).json()
    statistic = client.post(
        f"/api/v1/problems/{problem['id']}/statistics",
        json={
            "indicator": "Demo affected share",
            "source_id": source["id"],
            "document_id": document["id"],
            "claim_id": claim["id"],
            "value_numeric": 41,
            "unit": "%",
            "year": 2025,
            "geographic_scope": "Uganda",
        },
    ).json()
    claim_model = db_session.get(Claim, uuid.UUID(claim["id"]))
    statistic_model = db_session.get(Statistic, uuid.UUID(statistic["id"]))
    assert claim_model is not None and statistic_model is not None
    claim_model.extraction_run_id = uuid.UUID(extraction["id"])
    statistic_model.extraction_run_id = uuid.UUID(extraction["id"])
    statistic_model.evidence_id = uuid.UUID(evidence["id"])
    db_session.commit()
    return {
        "source": source["id"],
        "document": document["id"],
        "extraction": extraction["id"],
        "problem": problem["id"],
        "claim": claim["id"],
        "evidence": evidence["id"],
        "statistic": statistic["id"],
    }


def test_complete_problem_intelligence_lifecycle(client: TestClient, db_session: Session) -> None:
    ids = create_e2e_record(client, db_session)
    qa = client.post(f"/api/v1/problems/{ids['problem']}/qa")
    assert qa.status_code == 200 and qa.json()["passed"]
    assert client.get(f"/api/v1/problems/{ids['problem']}").json()["status"] == "human_review"
    review = client.post(
        f"/api/v1/problems/{ids['problem']}/reviews",
        json={
            "reviewer_id": "reviewer-e2e",
            "decision": "approve",
            "notes": "Ready for factual verification.",
        },
    )
    assert review.status_code == 201
    claims_before = client.get(f"/api/v1/problems/{ids['problem']}/claims").json()
    assert claims_before[0]["verification_status"] == "unverified"
    baseline = client.post(f"/api/v1/problems/{ids['problem']}/quality-score").json()
    claim_verification = client.post(
        f"/api/v1/problems/{ids['problem']}/claims/{ids['claim']}/verification",
        json=verification_payload("verified"),
    )
    statistic_verification = client.post(
        f"/api/v1/problems/{ids['problem']}/statistics/{ids['statistic']}/verification",
        json=verification_payload("verified"),
    )
    assert claim_verification.status_code == statistic_verification.status_code == 201
    scored = client.post(f"/api/v1/problems/{ids['problem']}/quality-score").json()
    assert (
        scored["dimension_scores"]["claim_verification"]
        > baseline["dimension_scores"]["claim_verification"]
    )
    version_one = client.post(
        f"/api/v1/problems/{ids['problem']}/versions",
        json={"created_by": "reviewer-e2e", "change_reason": "Verified canonical state"},
    ).json()
    assert (
        client.patch(
            f"/api/v1/problems/{ids['problem']}", json={"title": "Updated demo access constraint"}
        ).status_code
        == 200
    )
    version_two = client.post(
        f"/api/v1/problems/{ids['problem']}/versions",
        json={"created_by": "reviewer-e2e", "change_reason": "Editorial title correction"},
    ).json()
    assert version_one["snapshot"]["title"] == "Demo access constraint"
    assert version_two["snapshot"]["title"] == "Updated demo access constraint"
    assert [
        item["version_number"]
        for item in client.get(f"/api/v1/problems/{ids['problem']}/versions").json()
    ] == [2, 1]
    assert (
        client.get(f"/api/v1/problems/{ids['problem']}/claims/{ids['claim']}/verification").json()[
            0
        ]["id"]
        == claim_verification.json()["id"]
    )
    assert (
        client.get(f"/api/v1/problems/{ids['problem']}/quality-score").json()["id"] == scored["id"]
    )

    problem_id = uuid.UUID(ids["problem"])
    claim = db_session.get(Claim, uuid.UUID(ids["claim"]))
    statistic = db_session.get(Statistic, uuid.UUID(ids["statistic"]))
    evidence = db_session.get(Evidence, uuid.UUID(ids["evidence"]))
    assert claim and statistic and evidence
    assert claim.problem_id == problem_id and claim.source_id == uuid.UUID(ids["source"])
    assert claim.document_id == evidence.document_id == uuid.UUID(ids["document"])
    assert claim.extraction_run_id == statistic.extraction_run_id == uuid.UUID(ids["extraction"])
    assert statistic.claim_id == claim.id and statistic.evidence_id == evidence.id
    assert db_session.get(ExtractionRun, uuid.UUID(ids["extraction"])) is not None
    assert (
        len(list(db_session.scalars(select(Verification).where(Verification.claim_id == claim.id))))
        == 1
    )
    assert (
        len(
            list(
                db_session.scalars(
                    select(QualityScore).where(QualityScore.problem_id == problem_id)
                )
            )
        )
        == 2
    )
    assert (
        len(
            list(
                db_session.scalars(
                    select(ProblemVersion).where(ProblemVersion.problem_id == problem_id)
                )
            )
        )
        == 2
    )
    actions = set(
        db_session.scalars(
            select(AuditLog.action).where(
                AuditLog.entity_id.in_([problem_id, claim.id, statistic.id])
            )
        )
    )
    assert {
        "REVIEW_COMPLETED",
        "CLAIM_VERIFIED",
        "STATISTIC_VERIFIED",
        "QUALITY_SCORE_GENERATED",
        "PROBLEM_VERSION_CREATED",
    }.issubset(actions)


def test_trust_boundary_and_cross_problem_ownership(
    client: TestClient, db_session: Session
) -> None:
    incomplete = client.post(
        "/api/v1/problems",
        json={
            "problem_id": "PRB-E2E-BROKEN",
            "title": "Incomplete",
            "slug": "incomplete-e2e",
            "ai_generated": True,
        },
    ).json()
    failed_qa = client.post(f"/api/v1/problems/{incomplete['id']}/qa").json()
    assert not failed_qa["passed"]
    assert client.get(f"/api/v1/problems/{incomplete['id']}").json()["status"] == "qa_failed"
    assert (
        client.post(
            f"/api/v1/problems/{incomplete['id']}/reviews",
            json={"reviewer_id": "reviewer", "decision": "approve"},
        ).status_code
        == 409
    )

    ids = create_e2e_record(client, db_session)
    assert client.post(f"/api/v1/problems/{ids['problem']}/qa").json()["passed"]
    assert (
        client.post(
            f"/api/v1/problems/{ids['problem']}/reviews",
            json={"reviewer_id": "reviewer", "decision": "approve"},
        ).status_code
        == 201
    )
    other = client.post(
        "/api/v1/problems",
        json={
            "problem_id": "PRB-E2E-OTHER",
            "title": "Other candidate",
            "slug": "other-e2e-candidate",
        },
    ).json()
    response = client.post(
        f"/api/v1/problems/{other['id']}/claims/{ids['claim']}/verification",
        json=verification_payload("verified"),
    )
    assert response.status_code == 409
    claim = db_session.get(Claim, uuid.UUID(ids["claim"]))
    assert claim is not None and claim.verification_status.value == "unverified"
    assert db_session.scalar(select(Verification).where(Verification.claim_id == claim.id)) is None
    assert (
        db_session.scalar(
            select(AuditLog).where(
                AuditLog.entity_id == claim.id, AuditLog.action == "CLAIM_VERIFIED"
            )
        )
        is None
    )
