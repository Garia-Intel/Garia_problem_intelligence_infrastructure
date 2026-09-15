from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.database import Base
from app.models.base import UUIDPrimaryKeyMixin


class QAResult(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "qa_results"
    problem_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("problems.id", ondelete="RESTRICT"), index=True
    )
    validator_version: Mapped[str] = mapped_column(String(32), default="v1", nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    checks: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )
