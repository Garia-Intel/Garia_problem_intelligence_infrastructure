import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models.audit import AuditLog
from app.models.canonical import CanonicalProblem, ProblemCanonicalization
from app.models.enums import CanonicalizationDecision, CanonicalProblemStatus
from app.models.problem import Problem
from app.schemas.canonical import CanonicalResolutionCreate
from app.services.canonical import _add_version, _commit

TARGETED_DECISIONS = {
    CanonicalizationDecision.LINK_PROPOSED,
    CanonicalizationDecision.LINK_CONFIRMED,
    CanonicalizationDecision.NOT_SAME_PROBLEM,
    CanonicalizationDecision.RELATED_ONLY,
    CanonicalizationDecision.INSUFFICIENT_EVIDENCE,
}
ELIGIBLE_ASSESSMENT_STATUSES = {CanonicalProblemStatus.DRAFT, CanonicalProblemStatus.ACTIVE}


def _candidate(db: Session, problem_id: uuid.UUID) -> Problem:
    candidate = db.get(Problem, problem_id)
    if candidate is None or candidate.deleted:
        raise NotFoundError("PROBLEM_NOT_FOUND", "Candidate problem does not exist.")
    return candidate


def _target(
    db: Session, canonical_problem_id: uuid.UUID | None, decision: CanonicalizationDecision
) -> CanonicalProblem | None:
    if decision in TARGETED_DECISIONS and canonical_problem_id is None:
        raise ConflictError(
            "CANONICAL_TARGET_REQUIRED",
            "This resolution decision requires a canonical problem target.",
        )
    if decision == CanonicalizationDecision.CANDIDATE_REJECTED:
        if canonical_problem_id is not None:
            raise ConflictError(
                "CANONICAL_TARGET_NOT_ALLOWED",
                "A rejected candidate decision must not create a canonical mapping.",
            )
        return None
    if decision == CanonicalizationDecision.CREATE_CANONICAL:
        if canonical_problem_id is not None:
            raise ConflictError(
                "CANONICAL_TARGET_NOT_ALLOWED",
                "Create-canonical decisions create their own canonical identity.",
            )
        return None
    target = db.get(CanonicalProblem, canonical_problem_id)
    if target is None:
        raise NotFoundError("CANONICAL_PROBLEM_NOT_FOUND", "Canonical problem does not exist.")
    if target.status not in ELIGIBLE_ASSESSMENT_STATUSES:
        raise ConflictError(
            "INVALID_CANONICAL_TARGET_STATE",
            "Canonical targets must be draft or active for identity resolution.",
        )
    if (
        decision == CanonicalizationDecision.LINK_CONFIRMED
        and target.status != CanonicalProblemStatus.ACTIVE
    ):
        raise ConflictError(
            "INVALID_CANONICAL_TARGET_STATE", "Confirmed links require an active canonical problem."
        )
    return target


def _superseded_decision(
    db: Session, candidate: Problem, supersedes_id: uuid.UUID | None
) -> ProblemCanonicalization | None:
    if supersedes_id is None:
        return None
    previous = db.get(ProblemCanonicalization, supersedes_id)
    if previous is None or previous.problem_id != candidate.id or not previous.is_current:
        raise ConflictError(
            "INVALID_CANONICAL_SUPERSESSION",
            "Superseded decision must be a current decision for this candidate.",
        )
    return previous


def _current_confirmed_mapping(
    db: Session, candidate_id: uuid.UUID
) -> ProblemCanonicalization | None:
    return db.scalar(
        select(ProblemCanonicalization).where(
            ProblemCanonicalization.problem_id == candidate_id,
            ProblemCanonicalization.decision == CanonicalizationDecision.LINK_CONFIRMED,
            ProblemCanonicalization.is_current.is_(True),
        )
    )


def current_mapping(db: Session, problem_id: uuid.UUID) -> ProblemCanonicalization:
    _candidate(db, problem_id)
    mapping = _current_confirmed_mapping(db, problem_id)
    if mapping is None:
        raise NotFoundError(
            "CANONICAL_MAPPING_NOT_FOUND", "No current confirmed canonical mapping exists."
        )
    return mapping


def _audit_action(decision: CanonicalizationDecision) -> str:
    if decision == CanonicalizationDecision.LINK_PROPOSED:
        return "CANONICAL_LINK_PROPOSED"
    if decision == CanonicalizationDecision.LINK_CONFIRMED:
        return "CANONICAL_LINK_CONFIRMED"
    if decision == CanonicalizationDecision.RELATED_ONLY:
        return "CANONICAL_RELATION_ASSESSED"
    if decision in {
        CanonicalizationDecision.NOT_SAME_PROBLEM,
        CanonicalizationDecision.INSUFFICIENT_EVIDENCE,
        CanonicalizationDecision.CANDIDATE_REJECTED,
    }:
        return "CANONICAL_LINK_REJECTED"
    return "CANONICAL_RESOLUTION_COMPLETED"


def resolve_candidate(
    db: Session, problem_id: uuid.UUID, data: CanonicalResolutionCreate
) -> ProblemCanonicalization:
    """Record one human-controlled deterministic identity-resolution decision atomically."""
    candidate = _candidate(db, problem_id)
    if data.decision == CanonicalizationDecision.CREATE_CANONICAL:
        if data.canonical_identity is None:
            raise ConflictError(
                "CANONICAL_IDENTITY_REQUIRED",
                "Create-canonical decisions require curated canonical identity metadata.",
            )
    elif data.canonical_identity is not None:
        raise ConflictError(
            "CANONICAL_IDENTITY_NOT_ALLOWED",
            "Canonical identity metadata is only valid for create-canonical decisions.",
        )
    target = _target(db, data.canonical_problem_id, data.decision)
    previous = _superseded_decision(db, candidate, data.supersedes_id)
    existing = _current_confirmed_mapping(db, candidate.id)
    if data.decision == CanonicalizationDecision.LINK_CONFIRMED and existing is not None:
        if previous is None or previous.id != existing.id:
            raise ConflictError(
                "CURRENT_CANONICAL_MAPPING_EXISTS",
                "Candidate already has a current confirmed canonical mapping; "
                "explicitly supersede it.",
            )
    if previous is not None:
        previous.is_current = False
    if data.decision == CanonicalizationDecision.CREATE_CANONICAL:
        identity = data.canonical_identity
        assert identity is not None
        target = CanonicalProblem(
            canonical_id=f"CP-{uuid.uuid4().hex[:12].upper()}",
            canonical_key=secrets.token_urlsafe(24),
            title=identity.title,
            slug=identity.slug,
            problem_statement=identity.problem_statement,
        )
        db.add(target)
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            raise ConflictError(
                "CANONICAL_CONSTRAINT_VIOLATION",
                "The canonical operation conflicts with existing data.",
            ) from exc
        _add_version(db, target, data.actor_id, data.reason)
        db.add(
            AuditLog(
                actor_id=data.actor_id,
                entity_type="canonical_problem",
                entity_id=target.id,
                action="CANONICAL_PROBLEM_CREATED",
                old_data=None,
                new_data={
                    "canonical_id": target.canonical_id,
                    "canonical_key": target.canonical_key,
                    "status": target.status.value,
                    "created_from_problem_id": str(candidate.id),
                },
            )
        )
    mapping = ProblemCanonicalization(
        problem_id=candidate.id,
        canonical_problem_id=target.id if target else None,
        decision=data.decision,
        match_confidence=data.match_confidence,
        reason=data.reason,
        actor_type=data.actor_type,
        actor_id=data.actor_id,
        methodology_version=data.methodology_version,
        created_at=datetime.now(UTC),
        supersedes_id=previous.id if previous else None,
        is_current=True,
    )
    db.add(mapping)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            "CURRENT_CANONICAL_MAPPING_EXISTS",
            "Candidate already has a current confirmed canonical mapping.",
        ) from exc
    db.add(
        AuditLog(
            actor_id=data.actor_id,
            entity_type="problem_canonicalization",
            entity_id=mapping.id,
            action=_audit_action(data.decision),
            old_data={
                "superseded_decision_id": str(previous.id) if previous else None,
                "previous_current_mapping_id": str(existing.id) if existing else None,
            },
            new_data={
                "problem_id": str(candidate.id),
                "canonical_problem_id": str(target.id) if target else None,
                "decision": data.decision.value,
                "match_confidence": data.match_confidence,
                "reason": data.reason,
                "methodology_version": data.methodology_version,
            },
        )
    )
    if previous is not None:
        db.add(
            AuditLog(
                actor_id=data.actor_id,
                entity_type="problem_canonicalization",
                entity_id=previous.id,
                action="CANONICAL_LINK_SUPERSEDED",
                old_data={"is_current": True},
                new_data={"is_current": False, "superseded_by_id": str(mapping.id)},
            )
        )
    return _commit(db, mapping)  # type: ignore[return-value]


def resolution_history(db: Session, problem_id: uuid.UUID) -> list[ProblemCanonicalization]:
    _candidate(db, problem_id)
    return list(
        db.scalars(
            select(ProblemCanonicalization)
            .where(ProblemCanonicalization.problem_id == problem_id)
            .order_by(ProblemCanonicalization.created_at.desc(), ProblemCanonicalization.id.desc())
        )
    )
