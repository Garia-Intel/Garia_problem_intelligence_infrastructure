import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentCreate(BaseModel):
    source_id: uuid.UUID
    title: str = Field(min_length=1, max_length=500)
    document_type: str | None = Field(default=None, max_length=100)
    language: str | None = Field(default=None, max_length=16)
    content: str | None = None
    file_url: str | None = Field(default=None, max_length=2048)
    content_hash: str | None = Field(default=None, min_length=64, max_length=64)
    page_count: int | None = Field(default=None, ge=1)


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    source_id: uuid.UUID
    title: str
    document_type: str | None
    content_hash: str | None
    page_count: int | None
    created_at: datetime
    updated_at: datetime
