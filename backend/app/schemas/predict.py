from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class PredictResponse(BaseModel):
    """
    Response payload for POST /api/v1/predict.
    Field names are locked to SRS contract — do NOT rename for Phase 2 compatibility.
    """

    prediction_id: str = Field(..., description="UUID of the persisted prediction row")
    label: Literal["Harmful", "Safe"] = Field(
        ..., description="Model classification label"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Model confidence score (0.0 – 1.0)"
    )
    moderation_decision: Literal["AUTO_APPROVE", "AUTO_FLAG", "HUMAN_REVIEW"] = Field(
        ..., description="Automated routing decision derived from confidence threshold"
    )
    execution_time_ms: int = Field(
        ..., description="End-to-end server-side processing time in milliseconds"
    )
    heatmap_url: Optional[str] = Field(
        None, description="URL to the attention heatmap image (Phase 2 stub for now)"
    )

    model_config = {"json_schema_extra": {
        "example": {
            "prediction_id": "550e8400-e29b-41d4-a716-446655440000",
            "label": "Harmful",
            "confidence": 0.93,
            "moderation_decision": "AUTO_FLAG",
            "execution_time_ms": 42,
            "heatmap_url": "/static/heatmaps/placeholder.png",
        }
    }}
