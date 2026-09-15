from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import VerificationStatus

if TYPE_CHECKING:
    from app.models.problem import Problem


class Statistic(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "statistics"
    problem_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("problems.id", ondelete="RESTRICT"), index=True
    )
    claim_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("claims.id", ondelete="RESTRICT"))
    indicator: Mapped[str] = mapped_column(String(255), index=True)
    label: Mapped[str | None] = mapped_column(String(500))
    value_numeric: Mapped[float | None] = mapped_column()
    value_text: Mapped[str | None] = mapped_column(String(255))
    unit: Mapped[str | None] = mapped_column(String(64))
    year: Mapped[int | None] = mapped_column(Integer, index=True)
    geographic_scope: Mapped[str | None] = mapped_column(String(255), index=True)
    methodology: Mapped[str | None] = mapped_column(Text)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id", ondelete="RESTRICT"))
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="RESTRICT"))
    page_number: Mapped[int | None] = mapped_column(Integer)
    population: Mapped[str | None] = mapped_column(String(255))
    denominator: Mapped[str | None] = mapped_column(String(255))
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evidence.id", ondelete="RESTRICT")
    )
    extraction_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("extraction_runs.id", ondelete="RESTRICT"), index=True
    )
    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, native_enum=False), default=VerificationStatus.UNVERIFIED
    )
    problem: Mapped[Problem] = relationship(back_populates="statistics")
