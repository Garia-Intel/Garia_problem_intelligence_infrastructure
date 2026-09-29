import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models.audit import AuditLog
from app.models.canonical import (
    CanonicalProblem,
    CanonicalProblemMerge,
    CanonicalProblemVersion,
    ProblemCanonicalization,
)
from app.models.enums import CanonicalProblemStatus
from app.schemas.canonical import (
    CanonicalizationCreate,
    CanonicalLifecycleChange,
    CanonicalMergeCreate,
    CanonicalProblemCreate,
    CanonicalProblemUpdate,
    CanonicalVersionCreate,
)

TRANSITIONS = {
    CanonicalProblemStatus.DRAFT: {
        CanonicalProblemStatus.ACTIVE,
        CanonicalProblemStatus.RETIRED,
    },
    CanonicalProblemStatus.ACTIVE: {CanonicalProblemStatus.ARCHIVED, CanonicalProblemStatus.MERGED},
    CanonicalProblemStatus.ARCHIVED: {CanonicalProblemStatus.ACTIVE},
    CanonicalProblemStatus.MERGED: set(),
    CanonicalProblemStatus.RETIRED: set(),
}


def _snapshot(problem: CanonicalProblem) -> dict[str, object]:
    def serialize(value: object) -> object:
        if isinstance(value, uuid.UUID):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if hasattr(value, "value"):
            return value.value  # type: ignore[union-attr]
        return value

    fields = (
        "id",
        "canonical_id",
        "canonical_key",
        "title",
        "slug",
        "problem_statement",
        "status",
        "activated_at",
        "merged_at",
        "archived_at",
        "merged_into_id",
        "created_at",
        "updated_at",
    )
    return {field: serialize(getattr(problem, field)) for field in fields}


def _get(db: Session, canonical_problem_id: uuid.UUID) -> CanonicalProblem:
    result = db.get(CanonicalProblem, canonical_problem_id)
    if result is None:
        raise NotFoundError("CANONICAL_PROBLEM_NOT_FOUND", "Canonical problem does not exist.")
    return result


def _add_version(
    db: Session, problem: CanonicalProblem, actor_id: str, change_reason: str
) -> CanonicalProblemVersion:
    previous = db.scalar(
        select(CanonicalProblemVersion)
        .where(CanonicalProblemVersion.canonical_problem_id == problem.id)
        .order_by(CanonicalProblemVersion.version_number.desc())
    )
    version = CanonicalProblemVersion(
        canonical_problem_id=problem.id,
        version_number=1 if previous is None else previous.version_number + 1,
        snapshot=_snapshot(problem),
        created_by=actor_id,
        change_reason=change_reason,
        created_at=datetime.now(UTC),
    )
    db.add(version)
    db.flush()
    db.add(
        AuditLog(
            actor_id=actor_id,
            entity_type="canonical_problem",
            entity_id=problem.id,
            action="CANONICAL_PROBLEM_VERSION_CREATED",
            old_data={"previous_version_number": previous.version_number if previous else None},
            new_data={
                "version_id": str(version.id),
                "version_number": version.version_number,
                "change_reason": change_reason,
            },
        )
    )
    return version


def _commit(db: Session, instance: object) -> object:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            "CANONICAL_CONSTRAINT_VIOLATION",
            "The canonical operation conflicts with existing data.",
        ) from exc
    db.refresh(instance)
    return instance


def create_canonical_problem(db: Session, data: CanonicalProblemCreate) -> CanonicalProblem:
    problem = CanonicalProblem(
        canonical_id=f"CP-{uuid.uuid4().hex[:12].upper()}",
        canonical_key=secrets.token_urlsafe(24),
        title=data.title,
        slug=data.slug,
        problem_statement=data.problem_statement,
    )
    db.add(problem)
    db.flush()
    _add_version(db, problem, data.actor_id, data.change_reason)
    db.add(
        AuditLog(
            actor_id=data.actor_id,
            entity_type="canonical_problem",
            entity_id=problem.id,
            action="CANONICAL_PROBLEM_CREATED",
            old_data=None,
            new_data={
                "canonical_id": problem.canonical_id,
                "canonical_key": problem.canonical_key,
                "status": problem.status.value,
            },
        )
    )
    return _commit(db, problem)  # type: ignore[return-value]


def get_canonical_problem(db: Session, canonical_problem_id: uuid.UUID) -> CanonicalProblem:
    return _get(db, canonical_problem_id)


def update_canonical_problem(
    db: Session, canonical_problem_id: uuid.UUID, data: CanonicalProblemUpdate
) -> CanonicalProblem:
    problem = _get(db, canonical_problem_id)
    if problem.status in {CanonicalProblemStatus.MERGED, CanonicalProblemStatus.RETIRED}:
        raise ConflictError(
            "INVALID_CANONICAL_STATE", "Merged or retired canonical problems cannot be updated."
        )
    values = data.model_dump(exclude={"actor_id", "change_reason"}, exclude_none=True)
    if not values:
        raise ConflictError(
            "NO_CANONICAL_CHANGES", "At least one canonical metadata field must change."
        )
    old_data = {name: getattr(problem, name) for name in values}
    for name, value in values.items():
        setattr(problem, name, value)
    db.flush()
    _add_version(db, problem, data.actor_id, data.change_reason)
    db.add(
        AuditLog(
            actor_id=data.actor_id,
            entity_type="canonical_problem",
            entity_id=problem.id,
            action="CANONICAL_PROBLEM_UPDATED",
            old_data=old_data,
            new_data=values,
        )
    )
    return _commit(db, problem)  # type: ignore[return-value]


def transition_canonical_problem(
    db: Session,
    canonical_problem_id: uuid.UUID,
    target: CanonicalProblemStatus,
    data: CanonicalLifecycleChange,
) -> CanonicalProblem:
    problem = _get(db, canonical_problem_id)
    if target not in TRANSITIONS[problem.status]:
        raise ConflictError(
            "INVALID_CANONICAL_LIFECYCLE_TRANSITION",
            "This canonical lifecycle transition is not allowed.",
        )
    old_status = problem.status.value
    now = datetime.now(UTC)
    problem.status = target
    if target == CanonicalProblemStatus.ACTIVE:
        problem.activated_at = now
        problem.archived_at = None
        action = (
            "CANONICAL_PROBLEM_ACTIVATED"
            if old_status == CanonicalProblemStatus.DRAFT.value
            else "CANONICAL_PROBLEM_RESTORED"
        )
    elif target == CanonicalProblemStatus.ARCHIVED:
        problem.archived_at = now
        action = "CANONICAL_PROBLEM_ARCHIVED"
    else:
        action = "CANONICAL_PROBLEM_RETIRED"
    db.flush()
    _add_version(db, problem, data.actor_id, data.change_reason)
    db.add(
        AuditLog(
            actor_id=data.actor_id,
            entity_type="canonical_problem",
            entity_id=problem.id,
            action=action,
            old_data={"status": old_status},
            new_data={"status": target.value},
        )
    )
    return _commit(db, problem)  # type: ignore[return-value]


def create_canonical_version(
    db: Session, canonical_problem_id: uuid.UUID, data: CanonicalVersionCreate
) -> CanonicalProblemVersion:
    problem = _get(db, canonical_problem_id)
    version = _add_version(db, problem, data.actor_id, data.change_reason)
    return _commit(db, version)  # type: ignore[return-value]


def canonical_version_history(
    db: Session, canonical_problem_id: uuid.UUID
) -> list[CanonicalProblemVersion]:
    _get(db, canonical_problem_id)
    return list(
        db.scalars(
            select(CanonicalProblemVersion)
            .where(CanonicalProblemVersion.canonical_problem_id == canonical_problem_id)
            .order_by(
                CanonicalProblemVersion.version_number.desc(),
                CanonicalProblemVersion.id.desc(),
            )
        )
    )


def get_canonical_version(
    db: Session, canonical_problem_id: uuid.UUID, version_number: int
) -> CanonicalProblemVersion:
    _get(db, canonical_problem_id)
    version = db.scalar(
        select(CanonicalProblemVersion).where(
            CanonicalProblemVersion.canonical_problem_id == canonical_problem_id,
            CanonicalProblemVersion.version_number == version_number,
        )
    )
    if version is None:
        raise NotFoundError(
            "CANONICAL_PROBLEM_VERSION_NOT_FOUND", "Canonical problem version does not exist."
        )
    return version


def latest_canonical_version(
    db: Session, canonical_problem_id: uuid.UUID
) -> CanonicalProblemVersion:
    versions = canonical_version_history(db, canonical_problem_id)
    if not versions:
        raise NotFoundError(
            "CANONICAL_PROBLEM_VERSION_NOT_FOUND", "No canonical problem version exists."
        )
    return versions[0]


def create_canonicalization(
    db: Session, canonical_problem_id: uuid.UUID, data: CanonicalizationCreate
) -> ProblemCanonicalization:
    from app.schemas.canonical import CanonicalResolutionCreate
    from app.services import resolution

    return resolution.resolve_candidate(
        db,
        data.problem_id,
        CanonicalResolutionCreate(
            decision=data.decision,
            canonical_problem_id=canonical_problem_id,
            match_confidence=data.match_confidence,
            reason=data.reason,
            actor_type=data.actor_type,
            actor_id=data.actor_id,
            methodology_version=data.methodology_version,
            supersedes_id=data.supersedes_id,
        ),
    )


def canonicalization_history(
    db: Session, canonical_problem_id: uuid.UUID
) -> list[ProblemCanonicalization]:
    _get(db, canonical_problem_id)
    return list(
        db.scalars(
            select(ProblemCanonicalization)
            .where(ProblemCanonicalization.canonical_problem_id == canonical_problem_id)
            .order_by(ProblemCanonicalization.created_at.desc(), ProblemCanonicalization.id.desc())
        )
    )


def current_canonical_mapping(db: Session, problem_id: uuid.UUID) -> ProblemCanonicalization:
    from app.services import resolution

    return resolution.current_mapping(db, problem_id)


def execute_merge(
    db: Session, source_id: uuid.UUID, data: CanonicalMergeCreate
) -> CanonicalProblemMerge:
    source = _get(db, source_id)
    target = _get(db, data.target_canonical_problem_id)
    if source.id == target.id:
        raise ConflictError("SELF_CANONICAL_MERGE", "A canonical problem cannot merge into itself.")
    if (
        source.status not in {CanonicalProblemStatus.DRAFT, CanonicalProblemStatus.ACTIVE}
        or target.status != CanonicalProblemStatus.ACTIVE
    ):
        raise ConflictError(
            "INVALID_CANONICAL_MERGE_STATE",
            "Only draft or active records may merge into an active target.",
        )
    cursor = target
    while cursor.merged_into_id is not None:
        if cursor.merged_into_id == source.id:
            raise ConflictError("CANONICAL_MERGE_CYCLE", "Canonical merges cannot create cycles.")
        cursor = _get(db, cursor.merged_into_id)
    now = datetime.now(UTC)
    old_status = source.status.value
    merge = CanonicalProblemMerge(
        source_canonical_problem_id=source.id,
        target_canonical_problem_id=target.id,
        rationale=data.rationale,
        actor_id=data.actor_id,
        methodology_version=data.methodology_version,
        created_at=now,
    )
    source.status = CanonicalProblemStatus.MERGED
    source.merged_into_id = target.id
    source.merged_at = now
    db.add(merge)
    db.flush()
    _add_version(db, source, data.actor_id, data.rationale)
    _add_version(
        db,
        target,
        data.actor_id,
        f"Absorbed merge from {source.canonical_id}: {data.rationale}",
    )
    db.add(
        AuditLog(
            actor_id=data.actor_id,
            entity_type="canonical_problem",
            entity_id=source.id,
            action="CANONICAL_MERGE_APPROVED",
            old_data={"status": old_status},
            new_data={"target_id": str(target.id)},
        )
    )
    db.add(
        AuditLog(
            actor_id=data.actor_id,
            entity_type="canonical_problem",
            entity_id=source.id,
            action="CANONICAL_MERGE_EXECUTED",
            old_data={"status": old_status},
            new_data={"target_id": str(target.id), "merge_id": str(merge.id)},
        )
    )
    return _commit(db, merge)  # type: ignore[return-value]
