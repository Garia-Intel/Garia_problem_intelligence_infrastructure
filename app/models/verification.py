from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import UUIDPrimaryKeyMixin
from app.models.enums import VerificationMethod, VerificationStatus


class Verification(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "verifications"
    __table_args__ = (
        CheckConstraint(
            "(claim_id IS NOT NULL AND statistic_id IS NULL) OR "
            "(claim_id IS NULL AND statistic_id IS NOT NULL)",
            name="exactly_one_verification_target",
        ),
    )
    claim_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("claims.id", ondelete="RESTRICT"), index=True
    )
    statistic_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("statistics.id", ondelete="RESTRICT"), index=True
    )
    verifier_id: Mapped[str] = mapped_column(String(255), index=True)
    status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, native_enum=False), index=True
    )
    method: Mapped[VerificationMethod] = mapped_column(Enum(VerificationMethod, native_enum=False))
    notes: Mapped[str | None] = mapped_column(Text)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
