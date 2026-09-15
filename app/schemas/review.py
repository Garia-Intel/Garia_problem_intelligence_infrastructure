import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ReviewDecision


class ReviewCreate(BaseModel):
    reviewer_id: str = Field(min_length=1, max_length=255)
    decision: ReviewDecision
    notes: str | None = None
    changes: dict[str, Any] | None = None


class ReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    problem_id: uuid.UUID
    reviewer_id: str
    decision: ReviewDecision
    notes: str | None
    changes: dict[str, Any] | None
    reviewed_at: datetime
    created_at: datetime
