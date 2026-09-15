from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.database import Base
from app.models.base import UUIDPrimaryKeyMixin
from app.models.enums import ReviewDecision

if TYPE_CHECKING:
    from app.models.problem import Problem


class Review(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "reviews"
    problem_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("problems.id", ondelete="RESTRICT"), index=True
    )
    reviewer_id: Mapped[str] = mapped_column(String(255), index=True)
    decision: Mapped[ReviewDecision] = mapped_column(Enum(ReviewDecision, native_enum=False))
    notes: Mapped[str | None] = mapped_column(Text)
    changes: Mapped[dict | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    problem: Mapped[Problem] = relationship(back_populates="reviews")
