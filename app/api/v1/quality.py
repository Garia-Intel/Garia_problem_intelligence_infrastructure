import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.quality import QualityScoreRead
from app.services import quality as quality_service

router = APIRouter(prefix="/problems", tags=["quality scoring"])


@router.post(
    "/{problem_id}/quality-score",
    response_model=QualityScoreRead,
    status_code=status.HTTP_201_CREATED,
)
def generate_quality_score(
    problem_id: uuid.UUID, db: Session = Depends(get_db)
) -> QualityScoreRead:
    return quality_service.generate_quality_score(db, problem_id)


@router.get("/{problem_id}/quality-score", response_model=QualityScoreRead)
def get_latest_quality_score(
    problem_id: uuid.UUID, db: Session = Depends(get_db)
) -> QualityScoreRead:
    return quality_service.latest_quality_score(db, problem_id)


@router.get("/{problem_id}/quality-scores", response_model=list[QualityScoreRead])
def get_quality_history(
    problem_id: uuid.UUID, db: Session = Depends(get_db)
) -> list[QualityScoreRead]:
    return quality_service.quality_history(db, problem_id)
