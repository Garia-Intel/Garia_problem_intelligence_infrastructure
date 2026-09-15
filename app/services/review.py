import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models.audit import AuditLog
from app.models.enums import ProblemStatus, ReviewDecision
from app.models.problem import Problem
from app.models.review import Review
from app.schemas.review import ReviewCreate

REVIEWABLE_STATUSES = {ProblemStatus.HUMAN_REVIEW}
TRANSITIONS = {
    ReviewDecision.APPROVE: ProblemStatus.VERIFICATION_REQUIRED,
    ReviewDecision.NEEDS_REVISION: ProblemStatus.HUMAN_REVIEW,
    ReviewDecision.REJECT: ProblemStatus.REJECTED,
}


def get_problem(db: Session, problem_id: uuid.UUID) -> Problem:
    problem = db.get(Problem, problem_id)
    if problem is None or problem.deleted:
        raise NotFoundError("PROBLEM_NOT_FOUND", "Problem does not exist.")
    return problem


def submit_review(db: Session, problem_id: uuid.UUID, data: ReviewCreate) -> Review:
    problem = get_problem(db, problem_id)
    if problem.status not in REVIEWABLE_STATUSES:
        raise ConflictError(
            "INVALID_REVIEW_STATE",
            "A review can only be submitted when a problem is in human_review.",
        )
    reviewed_at = datetime.now(UTC)
    previous_status = problem.status.value
    review = Review(
        problem_id=problem.id,
        reviewer_id=data.reviewer_id,
        decision=data.decision,
        notes=data.notes,
        changes=data.changes,
        reviewed_at=reviewed_at,
    )
    db.add(review)
    problem.reviewed_by = data.reviewer_id
    problem.reviewed_at = reviewed_at
    problem.status = TRANSITIONS[data.decision]
    db.add(
        AuditLog(
            actor_id=data.reviewer_id,
            entity_type="problem",
            entity_id=problem.id,
            action="REVIEW_COMPLETED",
            old_data={"status": previous_status},
            new_data={"status": problem.status.value, "decision": data.decision.value},
        )
    )
    db.commit()
    db.refresh(review)
    return review


def get_review_history(db: Session, problem_id: uuid.UUID) -> list[Review]:
    get_problem(db, problem_id)
    return list(
        db.scalars(
            select(Review)
            .where(Review.problem_id == problem_id)
            .order_by(Review.reviewed_at.desc(), Review.id.desc())
        )
    )


def get_latest_review(db: Session, problem_id: uuid.UUID) -> Review:
    get_problem(db, problem_id)
    review = db.scalar(
        select(Review)
        .where(Review.problem_id == problem_id)
        .order_by(Review.reviewed_at.desc(), Review.id.desc())
    )
    if review is None:
        raise NotFoundError("REVIEW_NOT_FOUND", "No review exists for this problem.")
    return review
