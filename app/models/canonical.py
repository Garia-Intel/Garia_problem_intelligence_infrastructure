from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    and_,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    CanonicalizationDecision,
    CanonicalMergeStatus,
    CanonicalProblemStatus,
)

if TYPE_CHECKING:
    from app.models.problem import Problem


class CanonicalProblem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "canonical_problems"

    canonical_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    canonical_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500))
    slug: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    problem_statement: Mapped[str] = mapped_column(Text)
    status: Mapped[CanonicalProblemStatus] = mapped_column(
        Enum(CanonicalProblemStatus, native_enum=False),
        default=CanonicalProblemStatus.DRAFT,
        index=True,
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    merged_into_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("canonical_problems.id", ondelete="RESTRICT"), index=True
    )
    merged_into: Mapped[CanonicalProblem | None] = relationship(
        remote_side="CanonicalProblem.id", foreign_keys=[merged_into_id]
    )
    canonicalizations: Mapped[list[ProblemCanonicalization]] = relationship(
        back_populates="canonical_problem"
    )
    versions: Mapped[list[CanonicalProblemVersion]] = relationship(
        back_populates="canonical_problem"
    )


class ProblemCanonicalization(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "problem_canonicalizations"
    __table_args__ = (
        CheckConstraint(
            "(decision = 'CANDIDATE_REJECTED' AND canonical_problem_id IS NULL) OR "
            "(decision <> 'CANDIDATE_REJECTED' AND canonical_problem_id IS NOT NULL)",
            name="canonicalization_target_matches_decision",
        ),
    )

    problem_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("problems.id", ondelete="RESTRICT"), index=True
    )
    canonical_problem_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("canonical_problems.id", ondelete="RESTRICT"), index=True
    )
    decision: Mapped[CanonicalizationDecision] = mapped_column(
        Enum(CanonicalizationDecision, native_enum=False), index=True
    )
    match_confidence: Mapped[float | None] = mapped_column()
    reason: Mapped[str] = mapped_column(Text)
    actor_type: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[str | None] = mapped_column(String(255), index=True)
    methodology_version: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("problem_canonicalizations.id", ondelete="RESTRICT"), index=True
    )
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    problem: Mapped[Problem] = relationship(back_populates="canonicalizations")
    canonical_problem: Mapped[CanonicalProblem | None] = relationship(
        back_populates="canonicalizations"
    )
    supersedes: Mapped[ProblemCanonicalization | None] = relationship(
        remote_side="ProblemCanonicalization.id", foreign_keys=[supersedes_id]
    )


Index(
    "uq_problem_canonicalizations_current_confirmed",
    ProblemCanonicalization.problem_id,
    unique=True,
    postgresql_where=and_(
        ProblemCanonicalization.is_current.is_(True),
        ProblemCanonicalization.decision == CanonicalizationDecision.LINK_CONFIRMED,
    ),
    sqlite_where=and_(
        ProblemCanonicalization.is_current.is_(True),
        ProblemCanonicalization.decision == CanonicalizationDecision.LINK_CONFIRMED,
    ),
)


class CanonicalProblemVersion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "canonical_problem_versions"
    __table_args__ = (
        Index(
            "uq_canonical_problem_versions_problem_version",
            "canonical_problem_id",
            "version_number",
            unique=True,
        ),
    )

    canonical_problem_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("canonical_problems.id", ondelete="RESTRICT"), index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    change_reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    canonical_problem: Mapped[CanonicalProblem] = relationship(back_populates="versions")


class CanonicalProblemMerge(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "canonical_problem_merges"

    source_canonical_problem_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("canonical_problems.id", ondelete="RESTRICT"), index=True
    )
    target_canonical_problem_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("canonical_problems.id", ondelete="RESTRICT"), index=True
    )
    rationale: Mapped[str] = mapped_column(Text)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    methodology_version: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[CanonicalMergeStatus] = mapped_column(
        Enum(CanonicalMergeStatus, native_enum=False), default=CanonicalMergeStatus.EXECUTED
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
