import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.review import ReviewCreate, ReviewRead
from app.services import review as review_service

router = APIRouter(prefix="/problems", tags=["human reviews"])


@router.post(
    "/{problem_id}/reviews", response_model=ReviewRead, status_code=status.HTTP_201_CREATED
)
def submit_review(
    problem_id: uuid.UUID, data: ReviewCreate, db: Session = Depends(get_db)
) -> ReviewRead:
    return review_service.submit_review(db, problem_id, data)


@router.get("/{problem_id}/reviews", response_model=list[ReviewRead])
def get_review_history(problem_id: uuid.UUID, db: Session = Depends(get_db)) -> list[ReviewRead]:
    return review_service.get_review_history(db, problem_id)


@router.get("/{problem_id}/reviews/latest", response_model=ReviewRead)
def get_latest_review(problem_id: uuid.UUID, db: Session = Depends(get_db)) -> ReviewRead:
    return review_service.get_latest_review(db, problem_id)
