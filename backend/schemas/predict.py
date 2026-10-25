from typing import Literal

from pydantic import BaseModel, Field

PredictionLabel = Literal["Harmful", "Safe", "Needs review", "Not a meme"]


class PredictResponse(BaseModel):
    prediction_id: str
    label: PredictionLabel
    # Legacy field retained as a raw harmful-class score, never label confidence.
    confidence: float | None = Field(None, ge=0, le=1)
    harmful_probability: float | None = Field(None, ge=0, le=1)
    baseline_label: Literal["Harmful", "Safe"] | None = None
    moderation_decision: Literal["AUTO_APPROVE", "AUTO_FLAG", "HUMAN_REVIEW"]
    execution_time_ms: int
    heatmap_url: str | None = None
    image_url: str
    extracted_text: str
    ocr_source: str
    ocr_status: str
    content_type: str
    decision_source: str
    reason: str
    model_version: str | None = None
    persisted: bool
    warnings: list[str] = Field(default_factory=list)
