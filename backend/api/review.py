"""Real human feedback, including corrections of automatically decided scans."""
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, select
from sqlalchemy.orm import Session

from core.database import get_db
from models.prediction import Prediction
from schemas.review import ReviewQueueItem, VerdictRequest, VerdictResponse

router = APIRouter(prefix="/review", tags=["Review Queue"])


@router.get("-queue", response_model=list[ReviewQueueItem])
def get_review_queue(
    scope: Literal["all", "flagged"] = "all", db: Session = Depends(get_db),
):
    try:
        # Historical auto-decisions used reviewed=True without a human verdict.
        # They remain correctable and must never count as human training labels.
        statement = select(Prediction).where(Prediction.human_verdict.is_(None))
        if scope == "flagged":
            statement = statement.where(Prediction.moderation_decision.in_(["HUMAN_REVIEW", "AUTO_FLAG"]))
        rows = db.execute(statement.order_by(
            case((Prediction.moderation_decision == "HUMAN_REVIEW", 0), else_=1),
            Prediction.created_at.asc(),
        ).limit(200)).scalars().all()
        return [ReviewQueueItem(
            prediction_id=row.id, filename=row.filename,
            image_url=f"/api/v1/images/{row.id}",
            label=row.label, confidence=row.confidence, created_at=row.created_at,
            extracted_text=row.extracted_text, content_type=row.content_type,
            reason=row.analysis_reason, decision_source=row.decision_source,
            moderation_decision=row.moderation_decision,
        ) for row in rows]
    except Exception:
        db.rollback()
        raise HTTPException(503, "Review database unavailable. Check DATABASE_URL and run alembic upgrade head. The queue could not be loaded.")


@router.post("/{item_id}/verdict", response_model=VerdictResponse)
def submit_verdict(item_id: UUID, body: VerdictRequest, db: Session = Depends(get_db)):
    try:
        row = db.get(Prediction, str(item_id))
    except Exception:
        db.rollback()
        raise HTTPException(503, "Review database unavailable. Verdict was not saved.")
    if row is None:
        raise HTTPException(404, "Prediction not found.")
    now = datetime.now(timezone.utc)
    try:
        row.reviewed = True
        row.human_verdict = body.human_verdict
        row.reviewer_notes = body.notes
        row.reviewed_at = now
        # Preserve original model output for error analysis; the ground truth
        # lives in human_verdict and never silently changes the model weights.
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(503, "Database update failed. Verdict was not saved; please retry.")
    return VerdictResponse(prediction_id=str(item_id), updated_at=now)
