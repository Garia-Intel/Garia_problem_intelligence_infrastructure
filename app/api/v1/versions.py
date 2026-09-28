import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.problem_version import ProblemVersionCreate, ProblemVersionRead
from app.services import versioning

router = APIRouter(prefix="/problems", tags=["problem versions"])


@router.post(
    "/{problem_id}/versions", response_model=ProblemVersionRead, status_code=status.HTTP_201_CREATED
)
def create_version(
    problem_id: uuid.UUID, data: ProblemVersionCreate, db: Session = Depends(get_db)
) -> ProblemVersionRead:
    return versioning.create_problem_version(db, problem_id, data)


@router.get("/{problem_id}/versions", response_model=list[ProblemVersionRead])
def version_history(
    problem_id: uuid.UUID, db: Session = Depends(get_db)
) -> list[ProblemVersionRead]:
    return versioning.get_problem_version_history(db, problem_id)


@router.get("/{problem_id}/versions/latest", response_model=ProblemVersionRead)
def latest_version(problem_id: uuid.UUID, db: Session = Depends(get_db)) -> ProblemVersionRead:
    return versioning.get_latest_problem_version(db, problem_id)


@router.get("/{problem_id}/versions/{version_number}", response_model=ProblemVersionRead)
def version_by_number(
    problem_id: uuid.UUID, version_number: int, db: Session = Depends(get_db)
) -> ProblemVersionRead:
    return versioning.get_problem_version(db, problem_id, version_number)
