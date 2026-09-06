"""
decision_router.py
==================
Maps an inference confidence score to an automated moderation decision.

Thresholds are read from config.py (not hard-coded) so Phase 2 can tune
them after real model calibration without touching business logic.

SRS FR6:
  confidence < AUTO_APPROVE_THRESHOLD  → AUTO_APPROVE
  confidence > AUTO_FLAG_THRESHOLD     → AUTO_FLAG
  otherwise                            → HUMAN_REVIEW
"""

from __future__ import annotations

from typing import Literal

from app.config import get_settings
from app.logger import get_logger

logger = get_logger(__name__)

ModerationDecision = Literal["AUTO_APPROVE", "AUTO_FLAG", "HUMAN_REVIEW"]


def route(confidence: float) -> ModerationDecision:
    """
    Derive the moderation decision from a confidence score.

    Parameters
    ----------
    confidence : float
        Model confidence in range [0.0, 1.0].

    Returns
    -------
    ModerationDecision
        One of "AUTO_APPROVE", "AUTO_FLAG", or "HUMAN_REVIEW".

    Raises
    ------
    ValueError
        If confidence is outside [0.0, 1.0].
    """
    logger.info("[decision_router.route] START — confidence=%s", confidence)

    try:
        if not (0.0 <= confidence <= 1.0):
            raise ValueError(
                f"confidence must be in [0.0, 1.0], got {confidence}"
            )

        settings = get_settings()
        lo = settings.auto_approve_threshold
        hi = settings.auto_flag_threshold

        if confidence < lo:
            decision: ModerationDecision = "AUTO_APPROVE"
        elif confidence > hi:
            decision = "AUTO_FLAG"
        else:
            decision = "HUMAN_REVIEW"

        logger.info(
            "[decision_router.route] SUCCESS — confidence=%s | thresholds=[%.2f, %.2f] | decision=%r",
            confidence,
            lo,
            hi,
            decision,
        )
        return decision

    except ValueError as exc:
        logger.error(
            "[decision_router.route] FAILED — invalid confidence value: %s", str(exc), exc_info=True
        )
        raise
    except Exception as exc:
        logger.error(
            "[decision_router.route] FAILED — unexpected error: %s", str(exc), exc_info=True
        )
        raise
