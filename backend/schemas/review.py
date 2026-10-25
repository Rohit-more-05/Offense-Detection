from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from schemas.predict import PredictionLabel


class ReviewQueueItem(BaseModel):
    prediction_id: str
    filename: str
    image_url: str
    label: PredictionLabel
    confidence: float | None = Field(None, ge=0, le=1)
    created_at: datetime
    extracted_text: str | None = None
    content_type: str | None = None
    reason: str | None = None
    decision_source: str | None = None
    moderation_decision: str


class VerdictRequest(BaseModel):
    human_verdict: Literal["Harmful", "Non-Harmful", "Not a meme"]
    notes: str | None = Field(None, max_length=2048)


class VerdictResponse(BaseModel):
    prediction_id: str
    status: Literal["reviewed"] = "reviewed"
    updated_at: datetime
