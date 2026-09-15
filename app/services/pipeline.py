import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError
from app.models.audit import AuditLog
from app.models.claim import Claim
from app.models.enums import ExtractionStatus, JobStatus, JobType, ProblemStatus, ReviewDecision
from app.models.evidence import Evidence
from app.models.pipeline import ExtractionRun, IngestionJob
from app.models.problem import Problem
from app.models.review import Review
from app.models.source import Source
from app.models.statistic import Statistic
from app.schemas.pipeline import ClaimCreate, EvidenceCreate, StatisticCreate


def digest(content: str | None) -> str:
    return hashlib.sha256((content or "").encode()).hexdigest()


def audit(
    db: Session,
    actor_id: str | None,
    entity_type: str,
    entity_id: uuid.UUID,
    action: str,
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_id=actor_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            old_data=before,
            new_data=after,
        )
    )


def process_source(db: Session, source_id: uuid.UUID, force: bool = False) -> ExtractionRun:
    source = db.get(Source, source_id)
    if source is None:
        raise NotFoundError("SOURCE_NOT_FOUND", "Source does not exist.")
    input_hash = source.content_hash or digest(source.content)
    existing = db.scalar(
        select(ExtractionRun).where(
            ExtractionRun.source_id == source_id,
            ExtractionRun.input_hash == input_hash,
            ExtractionRun.pipeline_version == "v1",
        )
    )
    if existing and not force:
        return existing
    if force and existing:
        raise ConflictError(
            "SOURCE_ALREADY_PROCESSED",
            "This source input has already been processed; change content before retrying.",
        )
    job = IngestionJob(
        source_id=source_id,
        job_type=JobType.EXTRACT,
        input_hash=input_hash,
        status=JobStatus.RUNNING,
        started_at=datetime.now(UTC),
    )
    run = ExtractionRun(
        source_id=source_id,
        input_hash=input_hash,
        status=ExtractionStatus.RUNNING,
        model=get_settings().openai_model,
        started_at=datetime.now(UTC),
    )
    db.add_all([job, run])
    db.flush()
    # Deliberately no implicit OpenAI call: extraction needs explicit provider configuration.
    run.status = ExtractionStatus.COMPLETED
    run.completed_at = datetime.now(UTC)
    run.output_summary = {
        "candidate_problems": 0,
        "message": "No extractor configured; run recorded for provenance.",
    }
    job.status = JobStatus.COMPLETED
    job.completed_at = datetime.now(UTC)
    source.processing_status = "extracted"
    audit(
        db, None, "source", source_id, "SOURCE_PROCESSED", after={"extraction_run_id": str(run.id)}
    )
    db.commit()
    db.refresh(run)
    return run


def create_claim(db: Session, problem: Problem, data: ClaimCreate) -> Claim:
    if db.get(Source, data.source_id) is None:
        raise NotFoundError("SOURCE_NOT_FOUND", "Claim source does not exist.")
    claim = Claim(problem_id=problem.id, **data.model_dump())
    db.add(claim)
    db.flush()
    audit(
        db,
        None,
        "claim",
        claim.id,
        "CLAIM_CREATED",
        after={"problem_id": str(problem.id), "source_id": str(data.source_id)},
    )
    db.commit()
    db.refresh(claim)
    return claim


def create_evidence(db: Session, claim_id: uuid.UUID, data: EvidenceCreate) -> Evidence:
    if db.get(Claim, claim_id) is None:
        raise NotFoundError("CLAIM_NOT_FOUND", "Claim does not exist.")
    evidence = Evidence(claim_id=claim_id, **data.model_dump())
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    return evidence


def create_statistic(db: Session, problem: Problem, data: StatisticCreate) -> Statistic:
    if db.get(Source, data.source_id) is None:
        raise NotFoundError("SOURCE_NOT_FOUND", "Statistic source does not exist.")
    statistic = Statistic(problem_id=problem.id, **data.model_dump())
    db.add(statistic)
    db.commit()
    db.refresh(statistic)
    return statistic


def publish_problem(db: Session, problem: Problem, actor_id: str) -> Problem:
    approved = db.scalar(
        select(Review).where(
            Review.problem_id == problem.id, Review.decision == ReviewDecision.APPROVE
        )
    )
    has_provenance = db.scalar(
        select(Claim).where(Claim.problem_id == problem.id, Claim.source_id.is_not(None))
    )
    if approved is None or has_provenance is None:
        raise ConflictError(
            "PUBLISH_REQUIREMENTS_NOT_MET",
            "Publishing requires an approved review and at least one sourced claim.",
        )
    before = {"status": problem.status.value}
    problem.status = ProblemStatus.PUBLISHED
    problem.published_at = datetime.now(UTC)
    audit(
        db,
        actor_id,
        "problem",
        problem.id,
        "PROBLEM_PUBLISHED",
        before=before,
        after={"status": "published"},
    )
    db.commit()
    db.refresh(problem)
    return problem


def quality(problem: Problem) -> dict[str, float]:
    claims = problem.claims
    sourced = sum(c.source_id is not None for c in claims)
    verified = sum(c.verification_status.value == "verified" for c in claims)
    evidence = sum(len(c.evidence_items) > 0 for c in claims)
    total = max(len(claims), 1)
    dimensions = {
        "source_quality": 100.0 if sourced else 0.0,
        "evidence_quality": round(100 * evidence / total, 2),
        "claim_verification": round(100 * verified / total, 2),
        "completeness": 100.0 if problem.summary and problem.category else 50.0,
        "independent_source_support": 0.0,
        "recency": 50.0,
        "geographic_specificity": 50.0,
        "statistical_quality": 50.0,
    }
    return {"overall_score": round(sum(dimensions.values()) / len(dimensions), 2), **dimensions}
