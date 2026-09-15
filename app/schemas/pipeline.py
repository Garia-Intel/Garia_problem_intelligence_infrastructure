import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import (
    ClaimType,
    ExtractionStatus,
    ReviewDecision,
    VerificationStatus,
)


class ProcessSourceRequest(BaseModel):
    force: bool = False


class ExtractionRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    source_id: uuid.UUID
    status: ExtractionStatus
    model: str | None
    prompt_version: str
    pipeline_version: str
    input_hash: str
    output_summary: dict[str, Any] | None
    errors: str | None
    created_at: datetime


class ClaimCreate(BaseModel):
    claim_id: str = Field(min_length=1, max_length=64)
    statement: str = Field(min_length=1)
    claim_type: ClaimType
    source_id: uuid.UUID
    document_id: uuid.UUID | None = None
    page_number: int | None = Field(default=None, ge=1)
    section: str | None = None
    location: str | None = None
    source_text_reference: str | None = Field(default=None, max_length=500)
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED


class ClaimRead(ClaimCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    problem_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class EvidenceCreate(BaseModel):
    document_id: uuid.UUID
    evidence_type: str = Field(min_length=1, max_length=50)
    excerpt: str | None = Field(default=None, max_length=1000)
    page_number: int | None = Field(default=None, ge=1)
    section: str | None = None
    location: str | None = None
    evidence_strength: float | None = Field(default=None, ge=0, le=100)


class StatisticCreate(BaseModel):
    indicator: str = Field(min_length=1, max_length=255)
    source_id: uuid.UUID
    document_id: uuid.UUID
    claim_id: uuid.UUID | None = None
    value_numeric: float | None = None
    value_text: str | None = Field(default=None, max_length=255)
    unit: str | None = Field(default=None, max_length=64)
    year: int | None = Field(default=None, ge=1900, le=2100)
    geographic_scope: str | None = None
    population: str | None = None
    denominator: str | None = None
    methodology: str | None = None
    page_number: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def has_value(self) -> "StatisticCreate":
        if self.value_numeric is None and not self.value_text:
            raise ValueError("A statistic requires value_numeric or value_text.")
        if (
            self.unit == "%"
            and self.value_numeric is not None
            and not 0 <= self.value_numeric <= 100
        ):
            raise ValueError("Percentage values must be between 0 and 100.")
        return self


class StatisticRead(StatisticCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    problem_id: uuid.UUID
    verification_status: VerificationStatus
    created_at: datetime
    updated_at: datetime


class ReviewCreate(BaseModel):
    reviewer_id: str = Field(min_length=1, max_length=255)
    decision: ReviewDecision
    notes: str | None = None
    changes: dict[str, Any] | None = None


class QualityScore(BaseModel):
    overall_score: float
    dimensions: dict[str, float]
    methodology_version: str = "v1"
    calculated_at: datetime
