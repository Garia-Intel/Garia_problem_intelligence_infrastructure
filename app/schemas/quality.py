import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class QualityScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    problem_id: uuid.UUID
    methodology_version: str
    overall_score: float
    dimension_scores: dict[str, float]
    dimension_reasons: dict[str, Any]
    generated_at: datetime
    created_at: datetime
