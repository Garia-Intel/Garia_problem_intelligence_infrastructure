from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Date, DateTime, Enum, Float, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ProcessingStatus, SourceType

if TYPE_CHECKING:
    from app.models.document import Document


class Source(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sources"
    name: Mapped[str] = mapped_column(String(255), index=True)
    publisher: Mapped[str | None] = mapped_column(String(255), index=True)
    source_type: Mapped[SourceType] = mapped_column(Enum(SourceType, native_enum=False), index=True)
    url: Mapped[str | None] = mapped_column(String(2048))
    country: Mapped[str | None] = mapped_column(String(100), index=True)
    language: Mapped[str | None] = mapped_column(String(16))
    publication_date: Mapped[date | None] = mapped_column(Date)
    accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    license: Mapped[str | None] = mapped_column(String(255))
    reliability_score: Mapped[float | None] = mapped_column(Float)
    description: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(255))
    content: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    ingestion_method: Mapped[str] = mapped_column(String(50), default="manual", nullable=False)
    copyright_status: Mapped[str | None] = mapped_column(String(100))
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus, native_enum=False), default=ProcessingStatus.PENDING, index=True
    )
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSON().with_variant(JSONB, "postgresql")
    )
    documents: Mapped[list[Document]] = relationship(back_populates="source")
