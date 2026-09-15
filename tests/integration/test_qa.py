from fastapi.testclient import TestClient

from tests.integration.test_catalog import create_source


def create_problem(client: TestClient, suffix: str) -> str:
    response = client.post(
        "/api/v1/problems",
        json={
            "problem_id": f"PRB-QA-{suffix}",
            "title": "QA candidate",
            "slug": f"qa-candidate-{suffix.lower()}",
            "summary": "A candidate with source provenance.",
            "category": "demo",
            "ai_generated": True,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_valid_candidate_passes_qa_and_enters_review(client: TestClient) -> None:
    problem_id = create_problem(client, "PASS")
    source = create_source(client)
    client.post(
        f"/api/v1/problems/{problem_id}/claims",
        json={
            "claim_id": "QA-CLAIM-PASS",
            "statement": "Source-linked candidate claim.",
            "claim_type": "fact",
            "source_id": source["id"],
        },
    )
    result = client.post(f"/api/v1/problems/{problem_id}/qa")
    assert result.status_code == 200
    assert result.json()["passed"] is True
    assert client.get(f"/api/v1/problems/{problem_id}").json()["status"] == "human_review"


def test_missing_provenance_fails_and_history_is_preserved(client: TestClient) -> None:
    problem_id = create_problem(client, "FAIL")
    first = client.post(f"/api/v1/problems/{problem_id}/qa")
    second = client.post(f"/api/v1/problems/{problem_id}/qa")
    assert first.json()["passed"] is False
    assert any(item["check_code"] == "SOURCE_NOT_FOUND" for item in first.json()["errors"])
    assert first.json()["id"] != second.json()["id"]
    assert client.get(f"/api/v1/problems/{problem_id}").json()["status"] == "qa_failed"
    history = client.get(f"/api/v1/problems/{problem_id}/qa/history")
    assert history.status_code == 200
    assert [item["id"] for item in history.json()] == [second.json()["id"], first.json()["id"]]


def test_missing_claim_document_and_evidence_document_fail(client: TestClient) -> None:
    problem_id = create_problem(client, "DOC")
    source = create_source(client)
    missing_document = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    claim = client.post(
        f"/api/v1/problems/{problem_id}/claims",
        json={
            "claim_id": "QA-CLAIM-DOC",
            "statement": "Claim with broken document reference.",
            "claim_type": "fact",
            "source_id": source["id"],
            "document_id": missing_document,
        },
    ).json()
    client.post(
        f"/api/v1/claims/{claim['id']}/evidence",
        json={
            "document_id": missing_document,
            "evidence_type": "other",
            "excerpt": "Short reference.",
        },
    )
    result = client.post(f"/api/v1/problems/{problem_id}/qa").json()
    codes = {item["check_code"] for item in result["errors"]}
    assert {"CLAIM_DOCUMENT_MISSING", "EVIDENCE_DOCUMENT_MISSING"}.issubset(codes)


def test_statistic_references_and_blank_geography_are_checked(client: TestClient) -> None:
    problem_id = create_problem(client, "STAT")
    source = create_source(client)
    client.post(
        f"/api/v1/problems/{problem_id}/claims",
        json={
            "claim_id": "QA-CLAIM-STAT",
            "statement": "Supported claim.",
            "claim_type": "fact",
            "source_id": source["id"],
        },
    )
    client.post(
        f"/api/v1/problems/{problem_id}/statistics",
        json={
            "indicator": "Rate",
            "source_id": source["id"],
            "document_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "claim_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "value_numeric": 10,
            "unit": "%",
            "year": 2025,
            "geographic_scope": "   ",
        },
    )
    result = client.post(f"/api/v1/problems/{problem_id}/qa").json()
    codes = {item["check_code"] for item in result["errors"]}
    assert {"STATISTIC_DOCUMENT_MISSING", "STATISTIC_CLAIM_MISSING"}.issubset(codes)
    assert any(item["check_code"] == "INVALID_GEOGRAPHY" for item in result["warnings"])


def test_duplicate_statistic_is_warning_not_blocking_error(client: TestClient) -> None:
    problem_id = create_problem(client, "DUP")
    source = create_source(client)
    claim = client.post(
        f"/api/v1/problems/{problem_id}/claims",
        json={
            "claim_id": "QA-CLAIM-DUP",
            "statement": "Source linked.",
            "claim_type": "fact",
            "source_id": source["id"],
        },
    ).json()
    for _ in range(2):
        client.post(
            f"/api/v1/problems/{problem_id}/statistics",
            json={
                "indicator": "demo rate",
                "source_id": source["id"],
                "document_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "claim_id": claim["id"],
                "value_numeric": 50,
                "unit": "%",
                "year": 2025,
            },
        )
    result = client.post(f"/api/v1/problems/{problem_id}/qa").json()
    assert any(item["check_code"] == "DUPLICATE_STATISTIC" for item in result["warnings"])
