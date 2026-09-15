import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.qa import QAResult
from app.schemas.qa import QAResultRead
from app.services import qa as qa_service

router = APIRouter(prefix="/problems", tags=["automated quality assurance"])


def serialize(result: QAResult) -> dict:
    checks = result.checks
    return {
        "id": result.id,
        "problem_id": result.problem_id,
        "validator_version": result.validator_version,
        "passed": result.passed,
        "score": result.score,
        "checks": checks,
        "errors": [item for item in checks if not item["passed"] and item["severity"] == "error"],
        "warnings": [
            item for item in checks if not item["passed"] and item["severity"] == "warning"
        ],
        "created_at": result.created_at,
    }


@router.post("/{problem_id}/qa", response_model=QAResultRead)
def run_qa(problem_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    return serialize(qa_service.run_problem_qa(db, problem_id))


@router.get("/{problem_id}/qa", response_model=QAResultRead)
def get_latest_qa(problem_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    return serialize(qa_service.latest_problem_qa(db, problem_id))


@router.get("/{problem_id}/qa/history", response_model=list[QAResultRead])
def get_qa_history(problem_id: uuid.UUID, db: Session = Depends(get_db)) -> list[dict]:
    return [serialize(result) for result in qa_service.problem_qa_history(db, problem_id)]
