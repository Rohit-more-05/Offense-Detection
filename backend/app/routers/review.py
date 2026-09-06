"""
routers/review.py
=================
GET  /api/v1/review-queue          — List pending HUMAN_REVIEW items
POST /api/v1/review/{item_id}/verdict — Submit human verdict for one item
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.logger import get_logger
from app.models.prediction import Prediction
from app.schemas.review import ReviewQueueItem, VerdictRequest, VerdictResponse

logger = get_logger(__name__)
router = APIRouter(prefix="/review", tags=["Review Queue"])

BASE_IMAGE_URL = "/static/uploads"


@router.get(
    "-queue",
    response_model=List[ReviewQueueItem],
    summary="Fetch all items pending human review",
    responses={
        500: {"description": "Database query failed"},
    },
)
def get_review_queue(db: Session = Depends(get_db)) -> List[ReviewQueueItem]:
    """
    Returns all prediction rows where:
    - `moderation_decision == 'HUMAN_REVIEW'`
    - `reviewed == False`

    Ordered by `created_at` ascending (oldest first).
    """
    logger.info("[get_review_queue] START — querying HUMAN_REVIEW pending items")

    try:
        stmt = (
            select(Prediction)
            .where(
                Prediction.moderation_decision == "HUMAN_REVIEW",
                Prediction.reviewed == False,  # noqa: E712
            )
            .order_by(Prediction.created_at.asc())
        )
        rows = db.execute(stmt).scalars().all()
        logger.info("[get_review_queue] SUCCESS — found %d pending items", len(rows))

        result = [
            ReviewQueueItem(
                prediction_id=row.id,
                filename=row.filename,
                image_url=f"{BASE_IMAGE_URL}/{row.filename}",
                label=row.label,
                confidence=row.confidence,
                created_at=row.created_at,
            )
            for row in rows
        ]
        logger.info("[get_review_queue] Returning %d items", len(result))
        return result

    except Exception as exc:
        logger.error(
            "[get_review_queue] FAILED — reason: %s", str(exc), exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Failed to fetch review queue: {exc}")


@router.post(
    "/{item_id}/verdict",
    response_model=VerdictResponse,
    summary="Submit a human verdict for a pending review item",
    responses={
        404: {"description": "Prediction item not found"},
        500: {"description": "Database update failed"},
    },
)
def submit_verdict(
    item_id: str,
    body: VerdictRequest,
    db: Session = Depends(get_db),
) -> VerdictResponse:
    """
    Record a human moderator's verdict on a flagged item.

    - **human_verdict**: `"Harmful"` or `"Non-Harmful"`
    - **notes**: optional reviewer notes (max 2048 chars)
    """
    logger.info(
        "[submit_verdict] START — item_id=%r | verdict=%r | notes=%r",
        item_id,
        body.human_verdict,
        body.notes,
    )

    # ── Lookup ────────────────────────────────────────────────────────────────
    try:
        row = db.get(Prediction, item_id)
    except Exception as exc:
        logger.error(
            "[submit_verdict] DB lookup FAILED — item_id=%r | reason: %s",
            item_id,
            str(exc),
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Database lookup failed: {exc}")

    if row is None:
        logger.warning("[submit_verdict] 404 — item_id=%r not found", item_id)
        raise HTTPException(status_code=404, detail=f"Prediction '{item_id}' not found.")

    logger.info(
        "[submit_verdict] Found prediction — label=%r | confidence=%s | reviewed=%s",
        row.label,
        row.confidence,
        row.reviewed,
    )

    # ── Update ────────────────────────────────────────────────────────────────
    now = datetime.now(timezone.utc)
    try:
        row.reviewed = True
        row.human_verdict = body.human_verdict
        row.reviewer_notes = body.notes
        row.reviewed_at = now
        db.commit()
        db.refresh(row)
        logger.info(
            "[submit_verdict] SUCCESS — item_id=%r | verdict=%r | reviewed_at=%s",
            item_id,
            body.human_verdict,
            now.isoformat(),
        )
    except Exception as exc:
        db.rollback()
        logger.error(
            "[submit_verdict] DB update FAILED — rolling back — reason: %s",
            str(exc),
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Failed to save verdict: {exc}")

    return VerdictResponse(
        prediction_id=item_id,
        status="reviewed",
        updated_at=now,
    )
