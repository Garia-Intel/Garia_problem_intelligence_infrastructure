import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class QACheck(BaseModel):
    check_code: str
    category: str
    severity: Literal["error", "warning", "info"]
    passed: bool
    message: str
    field: str | None = None
    metadata: dict[str, Any] | None = None


class QAResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    problem_id: uuid.UUID
    validator_version: str
    passed: bool
    score: float
    checks: list[QACheck]
    errors: list[QACheck]
    warnings: list[QACheck]
    created_at: datetime
