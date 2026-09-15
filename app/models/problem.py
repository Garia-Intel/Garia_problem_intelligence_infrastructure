from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ProblemStatus, ProblemType, SystemLevel

if TYPE_CHECKING:
    from app.models.claim import Claim
    from app.models.review import Review
    from app.models.statistic import Statistic


class Problem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "problems"
    problem_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500))
    slug: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    summary: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(100), index=True)
    status: Mapped[ProblemStatus] = mapped_column(
        Enum(ProblemStatus, native_enum=False), default=ProblemStatus.DRAFT, index=True
    )
    problem_type: Mapped[ProblemType] = mapped_column(
        Enum(ProblemType, native_enum=False), default=ProblemType.UNKNOWN
    )
    system_level: Mapped[SystemLevel] = mapped_column(
        Enum(SystemLevel, native_enum=False), default=SystemLevel.SYSTEMIC
    )
    confidence_score: Mapped[float | None] = mapped_column(Float)
    severity_score: Mapped[float | None] = mapped_column(Float)
    solvability_score: Mapped[float | None] = mapped_column(Float)
    trend_score: Mapped[float | None] = mapped_column(Float)
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_by: Mapped[str | None] = mapped_column(String(255))
    reviewed_by: Mapped[str | None] = mapped_column(String(255))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claims: Mapped[list[Claim]] = relationship(back_populates="problem")
    statistics: Mapped[list[Statistic]] = relationship(back_populates="problem")
    reviews: Mapped[list[Review]] = relationship(back_populates="problem")
