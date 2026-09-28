import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.audit import AuditLog
from app.models.problem import Problem
from app.models.problem_version import ProblemVersion
from app.schemas.problem_version import ProblemVersionCreate


def _serialize(value: object) -> object:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value  # type: ignore[union-attr]
    return value


def build_problem_snapshot(problem: Problem) -> dict[str, object]:
    fields = (
        "id",
        "problem_id",
        "title",
        "slug",
        "summary",
        "category",
        "status",
        "problem_type",
        "system_level",
        "confidence_score",
        "severity_score",
        "solvability_score",
        "trend_score",
        "ai_generated",
        "deleted",
        "created_by",
        "reviewed_by",
        "reviewed_at",
        "published_at",
        "created_at",
        "updated_at",
    )
    return {field: _serialize(getattr(problem, field)) for field in fields}


def _get_problem(db: Session, problem_id: uuid.UUID) -> Problem:
    problem = db.get(Problem, problem_id)
    if problem is None or problem.deleted:
        raise NotFoundError("PROBLEM_NOT_FOUND", "Problem does not exist.")
    return problem


def create_problem_version(
    db: Session, problem_id: uuid.UUID, data: ProblemVersionCreate
) -> ProblemVersion:
    problem = _get_problem(db, problem_id)
    previous = db.scalar(
        select(ProblemVersion)
        .where(ProblemVersion.problem_id == problem.id)
        .order_by(ProblemVersion.version_number.desc())
    )
    version_number = 1 if previous is None else previous.version_number + 1
    version = ProblemVersion(
        problem_id=problem.id,
        version_number=version_number,
        snapshot=build_problem_snapshot(problem),
        created_by=data.created_by,
        change_reason=data.change_reason,
    )
    db.add(version)
    db.flush()
    db.add(
        AuditLog(
            actor_id=data.created_by,
            entity_type="problem",
            entity_id=problem.id,
            action="PROBLEM_VERSION_CREATED",
            old_data={
                "previous_version_id": str(previous.id) if previous else None,
                "previous_version_number": previous.version_number if previous else None,
            },
            new_data={
                "version_id": str(version.id),
                "version_number": version_number,
                "change_reason": data.change_reason,
                "methodology": "problem_versioning_v1",
            },
        )
    )
    db.commit()
    db.refresh(version)
    return version


def get_problem_version_history(db: Session, problem_id: uuid.UUID) -> list[ProblemVersion]:
    _get_problem(db, problem_id)
    return list(
        db.scalars(
            select(ProblemVersion)
            .where(ProblemVersion.problem_id == problem_id)
            .order_by(ProblemVersion.version_number.desc())
        )
    )


def get_latest_problem_version(db: Session, problem_id: uuid.UUID) -> ProblemVersion:
    versions = get_problem_version_history(db, problem_id)
    if not versions:
        raise NotFoundError("PROBLEM_VERSION_NOT_FOUND", "No problem version exists.")
    return versions[0]


def get_problem_version(db: Session, problem_id: uuid.UUID, version_number: int) -> ProblemVersion:
    _get_problem(db, problem_id)
    version = db.scalar(
        select(ProblemVersion).where(
            ProblemVersion.problem_id == problem_id, ProblemVersion.version_number == version_number
        )
    )
    if version is None:
        raise NotFoundError("PROBLEM_VERSION_NOT_FOUND", "Problem version does not exist.")
    return version
