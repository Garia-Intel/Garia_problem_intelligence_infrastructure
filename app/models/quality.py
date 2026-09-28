from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.database import Base
from app.models.base import UUIDPrimaryKeyMixin


class QualityScore(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "quality_scores"
    problem_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("problems.id", ondelete="RESTRICT"), index=True
    )
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    dimension_scores: Mapped[dict[str, float]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    dimension_reasons: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
