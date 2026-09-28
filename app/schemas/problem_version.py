import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProblemVersionCreate(BaseModel):
    created_by: str = Field(min_length=1, max_length=255)
    change_reason: str = Field(min_length=1)


class ProblemVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    problem_id: uuid.UUID
    version_number: int
    snapshot: dict[str, Any]
    created_by: str
    change_reason: str
    created_at: datetime
