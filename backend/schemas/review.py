from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ReviewQueueItem(BaseModel):
    """Represents a single pending HUMAN_REVIEW item returned from GET /api/v1/review-queue."""

    prediction_id: str
    filename: str
    image_url: str
    label: Literal["Harmful", "Safe"]
    confidence: float = Field(..., ge=0.0, le=1.0)
    created_at: datetime

    model_config = {"from_attributes": True}


class VerdictRequest(BaseModel):
    """Request body for POST /api/v1/review/{item_id}/verdict."""

    human_verdict: Literal["Harmful", "Non-Harmful"] = Field(
        ..., description="Human moderator's final decision"
    )
    notes: Optional[str] = Field(
        None, max_length=2048, description="Optional reviewer notes"
    )

    model_config = {"json_schema_extra": {
        "example": {
            "human_verdict": "Harmful",
            "notes": "Contains explicit hate speech targeting protected group.",
        }
    }}


class VerdictResponse(BaseModel):
    """Response confirming a verdict has been recorded."""

    prediction_id: str
    status: str = Field(..., description="Always 'reviewed' on success")
    updated_at: datetime

    model_config = {"json_schema_extra": {
        "example": {
            "prediction_id": "550e8400-e29b-41d4-a716-446655440000",
            "status": "reviewed",
            "updated_at": "2026-09-06T10:00:00Z",
        }
    }}
