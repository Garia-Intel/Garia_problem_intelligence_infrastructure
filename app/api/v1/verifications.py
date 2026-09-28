import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.verification import VerificationCreate, VerificationRead
from app.services import verification as verification_service

router = APIRouter(prefix="/problems", tags=["factual verification"])


@router.post(
    "/{problem_id}/claims/{claim_id}/verification",
    response_model=VerificationRead,
    status_code=status.HTTP_201_CREATED,
)
def verify_claim(
    problem_id: uuid.UUID,
    claim_id: uuid.UUID,
    data: VerificationCreate,
    db: Session = Depends(get_db),
) -> VerificationRead:
    return verification_service.verify_claim(db, problem_id, claim_id, data)


@router.get("/{problem_id}/claims/{claim_id}/verification", response_model=list[VerificationRead])
def claim_verification_history(
    problem_id: uuid.UUID, claim_id: uuid.UUID, db: Session = Depends(get_db)
) -> list[VerificationRead]:
    return verification_service.claim_history(db, problem_id, claim_id)


@router.post(
    "/{problem_id}/statistics/{statistic_id}/verification",
    response_model=VerificationRead,
    status_code=status.HTTP_201_CREATED,
)
def verify_statistic(
    problem_id: uuid.UUID,
    statistic_id: uuid.UUID,
    data: VerificationCreate,
    db: Session = Depends(get_db),
) -> VerificationRead:
    return verification_service.verify_statistic(db, problem_id, statistic_id, data)


@router.get(
    "/{problem_id}/statistics/{statistic_id}/verification", response_model=list[VerificationRead]
)
def statistic_verification_history(
    problem_id: uuid.UUID, statistic_id: uuid.UUID, db: Session = Depends(get_db)
) -> list[VerificationRead]:
    return verification_service.statistic_history(db, problem_id, statistic_id)
