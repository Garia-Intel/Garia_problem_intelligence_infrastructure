from fastapi.testclient import TestClient

from tests.integration.test_verifications import payload, verification_required_problem


def test_quality_score_is_persisted_and_has_exact_weighted_result(client: TestClient) -> None:
    problem_id, _, _, claim = verification_required_problem(client, "QUALITY")
    assert (
        client.post(
            f"/api/v1/problems/{problem_id}/claims/{claim['id']}/verification",
            json=payload("verified"),
        ).status_code
        == 201
    )
    first = client.post(f"/api/v1/problems/{problem_id}/quality-score")
    assert first.status_code == 201
    result = first.json()
    assert set(result["dimension_scores"]) == {
        "source_quality",
        "evidence_coverage",
        "claim_verification",
        "source_independence",
        "completeness",
        "freshness",
        "human_review",
    }
    scores = result["dimension_scores"]
    expected = round(
        sum(
            scores[key] * weight
            for key, weight in {
                "source_quality": 0.15,
                "evidence_coverage": 0.20,
                "claim_verification": 0.20,
                "source_independence": 0.10,
                "completeness": 0.15,
                "freshness": 0.10,
                "human_review": 0.10,
            }.items()
        ),
        2,
    )
    assert result["overall_score"] == expected
    assert result["methodology_version"] == "1.0"
    assert "missing" in result["dimension_reasons"]["completeness"]
    second = client.post(f"/api/v1/problems/{problem_id}/quality-score")
    history = client.get(f"/api/v1/problems/{problem_id}/quality-scores")
    assert (
        client.get(f"/api/v1/problems/{problem_id}/quality-score").json()["id"]
        == second.json()["id"]
    )
    assert [entry["id"] for entry in history.json()] == [second.json()["id"], first.json()["id"]]


def test_quality_scores_are_conservative_and_lifecycle_gated(client: TestClient) -> None:
    draft = client.post(
        "/api/v1/problems",
        json={"problem_id": "PRB-QUALITY-DRAFT", "title": "Draft", "slug": "quality-draft"},
    ).json()
    assert client.post(f"/api/v1/problems/{draft['id']}/quality-score").status_code == 409
    problem_id, _, _, _ = verification_required_problem(client, "EMPTY")
    result = client.post(f"/api/v1/problems/{problem_id}/quality-score").json()
    assert result["dimension_scores"]["evidence_coverage"] == 0
    assert result["dimension_scores"]["claim_verification"] == 0
    assert result["dimension_scores"]["freshness"] == 0


def test_source_independence_counts_distinct_sources(client: TestClient) -> None:
    problem_id, source, _, claim = verification_required_problem(client, "INDEPENDENCE")
    assert (
        client.post(
            f"/api/v1/problems/{problem_id}/claims/{claim['id']}/verification",
            json=payload("partially_verified"),
        ).status_code
        == 201
    )
    # The fixture has exactly one linked source, regardless of claim count.
    result = client.post(f"/api/v1/problems/{problem_id}/quality-score").json()
    assert result["dimension_scores"]["source_independence"] == 40
    assert source["id"]
