import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.errors import NotFoundError
from app.models.claim import Claim
from app.models.evidence import Evidence
from app.models.pipeline import ExtractionRun
from app.models.problem import Problem
from app.models.statistic import Statistic
from app.schemas.pipeline import (
    ClaimCreate,
    ClaimRead,
    EvidenceCreate,
    ExtractionRunRead,
    ProcessSourceRequest,
    QualityScore,
    StatisticCreate,
    StatisticRead,
)
from app.schemas.problem import ProblemRead
from app.schemas.review import ReviewCreate
from app.services import catalog
from app.services import pipeline as pipeline_service
from app.services import review as review_service

router = APIRouter(tags=["pipeline"])


@router.post("/sources/{source_id}/process", response_model=ExtractionRunRead)
def process_source(
    source_id: uuid.UUID, data: ProcessSourceRequest, db: Session = Depends(get_db)
) -> ExtractionRunRead:
    return pipeline_service.process_source(db, source_id, data.force)


@router.post(
    "/extraction-runs", response_model=ExtractionRunRead, status_code=status.HTTP_201_CREATED
)
def create_extraction_run(source_id: uuid.UUID, db: Session = Depends(get_db)) -> ExtractionRunRead:
    return pipeline_service.process_source(db, source_id)


@router.get("/extraction-runs/{run_id}", response_model=ExtractionRunRead)
def get_extraction_run(run_id: uuid.UUID, db: Session = Depends(get_db)) -> ExtractionRunRead:
    run = db.get(ExtractionRun, run_id)
    if run is None:
        raise NotFoundError("EXTRACTION_RUN_NOT_FOUND", "Extraction run does not exist.")
    return run


@router.post(
    "/problems/{problem_id}/claims", response_model=ClaimRead, status_code=status.HTTP_201_CREATED
)
def add_claim(problem_id: uuid.UUID, data: ClaimCreate, db: Session = Depends(get_db)) -> ClaimRead:
    return pipeline_service.create_claim(db, catalog.get_problem(db, problem_id), data)


@router.get("/problems/{problem_id}/claims", response_model=list[ClaimRead])
def list_claims(problem_id: uuid.UUID, db: Session = Depends(get_db)) -> list[ClaimRead]:
    catalog.get_problem(db, problem_id)
    return list(db.scalars(select(Claim).where(Claim.problem_id == problem_id)))


@router.post("/claims/{claim_id}/evidence", status_code=status.HTTP_201_CREATED)
def add_evidence(
    claim_id: uuid.UUID, data: EvidenceCreate, db: Session = Depends(get_db)
) -> dict[str, str]:
    evidence = pipeline_service.create_evidence(db, claim_id, data)
    return {"id": str(evidence.id)}


@router.get("/problems/{problem_id}/evidence", response_model=None)
def list_evidence(
    problem_id: uuid.UUID, db: Session = Depends(get_db)
) -> list[dict[str, str | None]]:
    catalog.get_problem(db, problem_id)
    evidence_items = db.scalars(select(Evidence).join(Claim).where(Claim.problem_id == problem_id))
    return [
        {"id": str(item.id), "claim_id": str(item.claim_id), "excerpt": item.excerpt}
        for item in evidence_items
    ]


@router.post(
    "/problems/{problem_id}/statistics",
    response_model=StatisticRead,
    status_code=status.HTTP_201_CREATED,
)
def add_statistic(
    problem_id: uuid.UUID, data: StatisticCreate, db: Session = Depends(get_db)
) -> StatisticRead:
    return pipeline_service.create_statistic(db, catalog.get_problem(db, problem_id), data)


@router.get("/problems/{problem_id}/statistics", response_model=list[StatisticRead])
def list_statistics(problem_id: uuid.UUID, db: Session = Depends(get_db)) -> list[StatisticRead]:
    catalog.get_problem(db, problem_id)
    return list(db.scalars(select(Statistic).where(Statistic.problem_id == problem_id)))


@router.post("/problems/{problem_id}/review", status_code=status.HTTP_201_CREATED)
def review_problem(
    problem_id: uuid.UUID, data: ReviewCreate, db: Session = Depends(get_db)
) -> dict[str, str]:
    review = review_service.submit_review(db, problem_id, data)
    return {"id": str(review.id)}


@router.post("/problems/{problem_id}/publish", response_model=ProblemRead)
def publish_problem(
    problem_id: uuid.UUID, reviewer_id: str, db: Session = Depends(get_db)
) -> ProblemRead:
    return pipeline_service.publish_problem(db, catalog.get_problem(db, problem_id), reviewer_id)


@router.get("/problems/{problem_id}/quality", response_model=QualityScore)
def get_quality(problem_id: uuid.UUID, db: Session = Depends(get_db)) -> QualityScore:
    problem = db.scalar(
        select(Problem)
        .options(selectinload(Problem.claims).selectinload(Claim.evidence_items))
        .where(Problem.id == problem_id)
    )
    if problem is None:
        raise NotFoundError("PROBLEM_NOT_FOUND", "Problem does not exist.")
    result = pipeline_service.quality(problem)
    return QualityScore(
        overall_score=result.pop("overall_score"),
        dimensions=result,
        calculated_at=datetime.now(UTC),
    )
