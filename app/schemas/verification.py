import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import VerificationMethod, VerificationStatus


class VerificationCreate(BaseModel):
    verifier_id: str = Field(min_length=1, max_length=255)
    status: VerificationStatus
    method: VerificationMethod
    notes: str | None = None

    @model_validator(mode="after")
    def completed_decision(self) -> "VerificationCreate":
        if self.status == VerificationStatus.UNVERIFIED:
            raise ValueError("A completed verification cannot have unverified status.")
        return self


class VerificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    claim_id: uuid.UUID | None
    statistic_id: uuid.UUID | None
    verifier_id: str
    status: VerificationStatus
    method: VerificationMethod
    notes: str | None
    verified_at: datetime
    created_at: datetime
