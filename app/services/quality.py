from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import ConflictError, NotFoundError
from app.models.audit import AuditLog
from app.models.claim import Claim
from app.models.enums import ProblemStatus, ReviewDecision, VerificationStatus
from app.models.problem import Problem
from app.models.quality import QualityScore
from app.models.review import Review
from app.models.source import Source

METHODOLOGY_VERSION = "1.0"
WEIGHTS = {
    "source_quality": 0.15,
    "evidence_coverage": 0.20,
    "claim_verification": 0.20,
    "source_independence": 0.10,
    "completeness": 0.15,
    "freshness": 0.10,
    "human_review": 0.10,
}
VERIFICATION_VALUES = {
    VerificationStatus.VERIFIED: 100.0,
    VerificationStatus.PARTIALLY_VERIFIED: 50.0,
    VerificationStatus.UNVERIFIED: 0.0,
    VerificationStatus.DISPUTED: 25.0,
    VerificationStatus.REJECTED: 0.0,
}


def calculate_source_quality(sources: list[Source]) -> tuple[float, list[str]]:
    if not sources:
        return 0.0, ["No linked sources are available."]
    complete = sum(
        bool(source.name and source.publisher and source.publication_date) for source in sources
    )
    return round(100 * complete / len(sources), 2), [
        f"{complete} of {len(sources)} linked sources have name, publisher, and publication date."
    ]


def calculate_evidence_coverage(problem: Problem) -> tuple[float, list[str]]:
    claims = problem.claims
    if not claims:
        return 0.0, ["No claims are available for evidence coverage."]
    supported = sum(bool(claim.evidence_items) for claim in claims)
    return round(100 * supported / len(claims), 2), [
        f"{supported} of {len(claims)} claims have attached evidence."
    ]


def calculate_claim_verification(problem: Problem) -> tuple[float, dict[str, int]]:
    claims = problem.claims
    breakdown = {status.value: 0 for status in VerificationStatus}
    if not claims:
        return 0.0, breakdown
    for claim in claims:
        breakdown[claim.verification_status.value] += 1
    return (
        round(
            sum(VERIFICATION_VALUES[claim.verification_status] for claim in claims) / len(claims), 2
        ),
        breakdown,
    )


def calculate_source_independence(sources: list[Source]) -> tuple[float, list[str]]:
    count = len({source.id for source in sources})
    score = 0.0 if count == 0 else 40.0 if count == 1 else 70.0 if count == 2 else 100.0
    return score, [f"{count} distinct linked source(s) support the record."]


def calculate_completeness(problem: Problem) -> tuple[float, list[str]]:
    checks: list[tuple[str, bool]] = [
        ("problem.summary", bool(problem.summary)),
        ("problem.category", bool(problem.category)),
    ]
    for claim in problem.claims:
        checks.extend(
            [
                (f"claim.{claim.id}.statement", bool(claim.statement)),
                (f"claim.{claim.id}.source_id", claim.source_id is not None),
                (f"claim.{claim.id}.document_id", claim.document_id is not None),
            ]
        )
    for statistic in problem.statistics:
        checks.extend(
            [
                (f"statistic.{statistic.id}.indicator", bool(statistic.indicator)),
                (
                    f"statistic.{statistic.id}.value",
                    statistic.value_numeric is not None or bool(statistic.value_text),
                ),
                (f"statistic.{statistic.id}.unit", bool(statistic.unit)),
                (f"statistic.{statistic.id}.year", statistic.year is not None),
                (f"statistic.{statistic.id}.source_id", statistic.source_id is not None),
                (f"statistic.{statistic.id}.document_id", statistic.document_id is not None),
            ]
        )
    missing = [name for name, exists in checks if not exists]
    return round(100 * (len(checks) - len(missing)) / len(checks), 2), missing


def calculate_freshness(sources: list[Source], now: datetime) -> tuple[float, list[str]]:
    dates = [source.publication_date for source in sources if source.publication_date]
    if not dates:
        return 0.0, ["No source publication date is available."]
    age_days = (now.date() - max(dates)).days
    score = (
        100.0
        if age_days <= 365
        else (
            90.0
            if age_days <= 730
            else (
                80.0
                if age_days <= 1095
                else 65.0 if age_days <= 1825 else 45.0 if age_days <= 3650 else 25.0
            )
        )
    )
    return score, [f"Most recent linked source is {age_days} days old."]


def calculate_human_review(problem: Problem, reviews: list[Review]) -> tuple[float, list[str]]:
    approved = any(review.decision == ReviewDecision.APPROVE for review in reviews)
    return (
        (100.0, ["An approved human review exists."])
        if approved
        else (0.0, ["No approved human review exists."])
    )


def generate_quality_score(db: Session, problem_id: object) -> QualityScore:
    problem = db.scalar(
        select(Problem)
        .options(
            selectinload(Problem.claims).selectinload(Claim.evidence_items),
            selectinload(Problem.statistics),
            selectinload(Problem.reviews),
        )
        .where(Problem.id == problem_id)
    )
    if problem is None or problem.deleted:
        raise NotFoundError("PROBLEM_NOT_FOUND", "Problem does not exist.")
    if problem.status != ProblemStatus.VERIFICATION_REQUIRED:
        raise ConflictError(
            "INVALID_QUALITY_SCORE_STATE",
            "Quality scoring requires problem status verification_required.",
        )
    source_ids = {claim.source_id for claim in problem.claims if claim.source_id} | {
        statistic.source_id for statistic in problem.statistics if statistic.source_id
    }
    sources = (
        list(db.scalars(select(Source).where(Source.id.in_(source_ids)))) if source_ids else []
    )
    now = datetime.now(UTC)
    source_quality, source_reasons = calculate_source_quality(sources)
    evidence_coverage, evidence_reasons = calculate_evidence_coverage(problem)
    claim_verification, verification_breakdown = calculate_claim_verification(problem)
    source_independence, independence_reasons = calculate_source_independence(sources)
    completeness, missing = calculate_completeness(problem)
    freshness, freshness_reasons = calculate_freshness(sources, now)
    human_review, review_reasons = calculate_human_review(problem, problem.reviews)
    scores = {
        "source_quality": source_quality,
        "evidence_coverage": evidence_coverage,
        "claim_verification": claim_verification,
        "source_independence": source_independence,
        "completeness": completeness,
        "freshness": freshness,
        "human_review": human_review,
    }
    reasons = {
        "source_quality": source_reasons,
        "evidence_coverage": evidence_reasons,
        "claim_verification": verification_breakdown,
        "source_independence": independence_reasons,
        "completeness": {"missing": missing},
        "freshness": freshness_reasons,
        "human_review": review_reasons,
    }
    overall = round(sum(scores[key] * WEIGHTS[key] for key in WEIGHTS), 2)
    previous = db.scalar(
        select(QualityScore)
        .where(QualityScore.problem_id == problem.id)
        .order_by(QualityScore.generated_at.desc())
    )
    result = QualityScore(
        problem_id=problem.id,
        methodology_version=METHODOLOGY_VERSION,
        overall_score=overall,
        dimension_scores=scores,
        dimension_reasons=reasons,
        generated_at=now,
    )
    db.add(result)
    db.flush()
    db.add(
        AuditLog(
            actor_id=None,
            entity_type="problem",
            entity_id=problem.id,
            action="QUALITY_SCORE_GENERATED",
            old_data={"previous_quality_score_id": str(previous.id) if previous else None},
            new_data={
                "quality_score_id": str(result.id),
                "overall_score": overall,
                "methodology_version": METHODOLOGY_VERSION,
            },
        )
    )
    db.commit()
    db.refresh(result)
    return result


def latest_quality_score(db: Session, problem_id: object) -> QualityScore:
    result = db.scalar(
        select(QualityScore)
        .where(QualityScore.problem_id == problem_id)
        .order_by(QualityScore.generated_at.desc(), QualityScore.id.desc())
    )
    if result is None:
        raise NotFoundError("QUALITY_SCORE_NOT_FOUND", "No quality score exists for this problem.")
    return result


def quality_history(db: Session, problem_id: object) -> list[QualityScore]:
    if db.get(Problem, problem_id) is None:
        raise NotFoundError("PROBLEM_NOT_FOUND", "Problem does not exist.")
    return list(
        db.scalars(
            select(QualityScore)
            .where(QualityScore.problem_id == problem_id)
            .order_by(QualityScore.generated_at.desc(), QualityScore.id.desc())
        )
    )
