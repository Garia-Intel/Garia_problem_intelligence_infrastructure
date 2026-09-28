import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models.audit import AuditLog
from app.models.claim import Claim
from app.models.enums import ProblemStatus
from app.models.problem import Problem
from app.models.statistic import Statistic
from app.models.verification import Verification
from app.schemas.verification import VerificationCreate


def get_verifiable_problem(db: Session, problem_id: uuid.UUID) -> Problem:
    problem = db.get(Problem, problem_id)
    if problem is None or problem.deleted:
        raise NotFoundError("PROBLEM_NOT_FOUND", "Problem does not exist.")
    if problem.status != ProblemStatus.VERIFICATION_REQUIRED:
        raise ConflictError(
            "INVALID_VERIFICATION_STATE",
            "Verification requires problem status verification_required.",
        )
    return problem


def verify_claim(
    db: Session, problem_id: uuid.UUID, claim_id: uuid.UUID, data: VerificationCreate
) -> Verification:
    get_verifiable_problem(db, problem_id)
    claim = db.get(Claim, claim_id)
    if claim is None:
        raise NotFoundError("CLAIM_NOT_FOUND", "Claim does not exist.")
    if claim.problem_id != problem_id:
        raise ConflictError("CLAIM_PROBLEM_MISMATCH", "Claim does not belong to this problem.")
    return _record(db, claim=claim, statistic=None, data=data)


def verify_statistic(
    db: Session, problem_id: uuid.UUID, statistic_id: uuid.UUID, data: VerificationCreate
) -> Verification:
    get_verifiable_problem(db, problem_id)
    statistic = db.get(Statistic, statistic_id)
    if statistic is None:
        raise NotFoundError("STATISTIC_NOT_FOUND", "Statistic does not exist.")
    if statistic.problem_id != problem_id:
        raise ConflictError(
            "STATISTIC_PROBLEM_MISMATCH", "Statistic does not belong to this problem."
        )
    return _record(db, claim=None, statistic=statistic, data=data)


def _record(
    db: Session, claim: Claim | None, statistic: Statistic | None, data: VerificationCreate
) -> Verification:
    target = claim or statistic
    assert target is not None
    old_status = target.verification_status.value
    verification = Verification(
        claim_id=claim.id if claim else None,
        statistic_id=statistic.id if statistic else None,
        verifier_id=data.verifier_id,
        status=data.status,
        method=data.method,
        notes=data.notes,
        verified_at=datetime.now(UTC),
    )
    db.add(verification)
    target.verification_status = data.status
    action = "CLAIM_VERIFIED" if claim else "STATISTIC_VERIFIED"
    entity_type = "claim" if claim else "statistic"
    db.flush()
    db.add(
        AuditLog(
            actor_id=data.verifier_id,
            entity_type=entity_type,
            entity_id=target.id,
            action=action,
            old_data={"verification_status": old_status},
            new_data={
                "verification_status": data.status.value,
                "verification_id": str(verification.id),
                "verifier_id": data.verifier_id,
            },
        )
    )
    db.commit()
    db.refresh(verification)
    return verification


def claim_history(db: Session, problem_id: uuid.UUID, claim_id: uuid.UUID) -> list[Verification]:
    _claim_for_history(db, problem_id, claim_id)
    return list(
        db.scalars(
            select(Verification)
            .where(Verification.claim_id == claim_id)
            .order_by(Verification.verified_at.desc(), Verification.id.desc())
        )
    )


def statistic_history(
    db: Session, problem_id: uuid.UUID, statistic_id: uuid.UUID
) -> list[Verification]:
    statistic = db.get(Statistic, statistic_id)
    if statistic is None:
        raise NotFoundError("STATISTIC_NOT_FOUND", "Statistic does not exist.")
    if statistic.problem_id != problem_id:
        raise ConflictError(
            "STATISTIC_PROBLEM_MISMATCH", "Statistic does not belong to this problem."
        )
    return list(
        db.scalars(
            select(Verification)
            .where(Verification.statistic_id == statistic_id)
            .order_by(Verification.verified_at.desc(), Verification.id.desc())
        )
    )


def _claim_for_history(db: Session, problem_id: uuid.UUID, claim_id: uuid.UUID) -> Claim:
    claim = db.get(Claim, claim_id)
    if claim is None:
        raise NotFoundError("CLAIM_NOT_FOUND", "Claim does not exist.")
    if claim.problem_id != problem_id:
        raise ConflictError("CLAIM_PROBLEM_MISMATCH", "Claim does not belong to this problem.")
    return claim
