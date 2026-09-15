import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.problem import ProblemCreate, ProblemRead, ProblemUpdate
from app.services import catalog

router = APIRouter(prefix="/problems", tags=["problems"])


@router.post("", response_model=ProblemRead, status_code=status.HTTP_201_CREATED)
def create_problem(data: ProblemCreate, db: Session = Depends(get_db)) -> ProblemRead:
    return catalog.create_problem(db, data)


@router.get("", response_model=list[ProblemRead])
def list_problems(db: Session = Depends(get_db)) -> list[ProblemRead]:
    return catalog.list_problems(db)


@router.get("/{problem_id}", response_model=ProblemRead)
def get_problem(problem_id: uuid.UUID, db: Session = Depends(get_db)) -> ProblemRead:
    return catalog.get_problem(db, problem_id)


@router.patch("/{problem_id}", response_model=ProblemRead)
def update_problem(
    problem_id: uuid.UUID, data: ProblemUpdate, db: Session = Depends(get_db)
) -> ProblemRead:
    return catalog.update_problem(db, problem_id, data)


@router.delete("/{problem_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_problem(problem_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    catalog.delete_problem(db, problem_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
