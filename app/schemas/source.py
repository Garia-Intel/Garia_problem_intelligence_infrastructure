import uuid
from datetime import date, datetime
from typing import Any

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field

from app.models.enums import ProcessingStatus, SourceType


class SourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    publisher: str | None = Field(default=None, max_length=255)
    source_type: SourceType
    url: AnyHttpUrl | None = None
    country: str | None = Field(default=None, max_length=100)
    language: str | None = Field(default=None, max_length=16)
    publication_date: date | None = None
    description: str | None = None
    metadata: dict[str, Any] | None = None
    author: str | None = Field(default=None, max_length=255)
    content: str | None = None
    ingestion_method: str = Field(default="manual", max_length=50)
    copyright_status: str | None = Field(default=None, max_length=100)


class SourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    publisher: str | None = Field(default=None, max_length=255)
    country: str | None = Field(default=None, max_length=100)
    language: str | None = Field(default=None, max_length=16)
    description: str | None = None


class SourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    publisher: str | None
    source_type: SourceType
    url: str | None
    country: str | None
    language: str | None
    publication_date: date | None
    description: str | None
    content_hash: str | None
    processing_status: ProcessingStatus
    created_at: datetime
    updated_at: datetime
