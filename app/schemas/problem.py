import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ProblemStatus, ProblemType, SystemLevel


class ProblemCreate(BaseModel):
    problem_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=500)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=512)
    summary: str | None = None
    category: str | None = Field(default=None, max_length=100)
    problem_type: ProblemType = ProblemType.UNKNOWN
    system_level: SystemLevel = SystemLevel.SYSTEMIC
    ai_generated: bool = False


class ProblemUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    summary: str | None = None
    category: str | None = Field(default=None, max_length=100)
    status: ProblemStatus | None = None


class ProblemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    problem_id: str
    title: str
    slug: str
    summary: str | None
    category: str | None
    status: ProblemStatus
    problem_type: ProblemType
    system_level: SystemLevel
    ai_generated: bool
    deleted: bool
    created_at: datetime
    updated_at: datetime
