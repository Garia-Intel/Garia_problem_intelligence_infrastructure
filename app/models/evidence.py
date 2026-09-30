from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDPrimaryKeyMixin
from app.models.enums import EvidenceType

if TYPE_CHECKING:
    from app.models.claim import Claim
    from app.models.document import Document


class Evidence(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "evidence"
    claim_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("claims.id", ondelete="RESTRICT"), index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"), index=True
    )
    evidence_type: Mapped[EvidenceType] = mapped_column(Enum(EvidenceType, native_enum=False))
    excerpt: Mapped[str | None] = mapped_column(Text)
    page_number: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(String(255))
    location: Mapped[str | None] = mapped_column(String(500))
    evidence_strength: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    claim: Mapped[Claim] = relationship(back_populates="evidence_items")
    document: Mapped[Document] = relationship(foreign_keys=[document_id])
