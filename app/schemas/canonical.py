import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    CanonicalizationDecision,
    CanonicalMergeStatus,
    CanonicalProblemStatus,
)


class CanonicalProblemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=512)
    problem_statement: str = Field(min_length=1)
    actor_id: str = Field(min_length=1, max_length=255)
    change_reason: str = Field(min_length=1)


class CanonicalProblemUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=512)
    problem_statement: str | None = Field(default=None, min_length=1)
    actor_id: str = Field(min_length=1, max_length=255)
    change_reason: str = Field(min_length=1)


class CanonicalLifecycleChange(BaseModel):
    actor_id: str = Field(min_length=1, max_length=255)
    change_reason: str = Field(min_length=1)


class CanonicalVersionCreate(BaseModel):
    actor_id: str = Field(min_length=1, max_length=255)
    change_reason: str = Field(min_length=1)


class CanonicalizationCreate(BaseModel):
    problem_id: uuid.UUID
    decision: CanonicalizationDecision
    match_confidence: float | None = Field(default=None, ge=0, le=1)
    reason: str = Field(min_length=1)
    actor_type: str = Field(min_length=1, max_length=64)
    actor_id: str | None = Field(default=None, max_length=255)
    methodology_version: str | None = Field(default=None, max_length=64)
    supersedes_id: uuid.UUID | None = None


class CanonicalMergeCreate(BaseModel):
    target_canonical_problem_id: uuid.UUID
    rationale: str = Field(min_length=1)
    actor_id: str = Field(min_length=1, max_length=255)
    methodology_version: str | None = Field(default=None, max_length=64)


class CanonicalProblemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    canonical_id: str
    canonical_key: str
    title: str
    slug: str
    problem_statement: str
    status: CanonicalProblemStatus
    activated_at: datetime | None
    merged_at: datetime | None
    archived_at: datetime | None
    merged_into_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class CanonicalProblemVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    canonical_problem_id: uuid.UUID
    version_number: int
    snapshot: dict[str, Any]
    created_by: str
    change_reason: str
    created_at: datetime


class ProblemCanonicalizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    problem_id: uuid.UUID
    canonical_problem_id: uuid.UUID
    decision: CanonicalizationDecision
    match_confidence: float | None
    reason: str
    actor_type: str
    actor_id: str | None
    methodology_version: str | None
    created_at: datetime
    supersedes_id: uuid.UUID | None
    is_current: bool


class CanonicalProblemMergeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    source_canonical_problem_id: uuid.UUID
    target_canonical_problem_id: uuid.UUID
    rationale: str
    actor_id: str
    methodology_version: str | None
    status: CanonicalMergeStatus
    created_at: datetime
