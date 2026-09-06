"""
mock_inference.py
=================
Pure-Python fake inference pipeline — no ML dependencies.
Returns randomised label + confidence values with a realistic distribution:

  ─────────────────────────────────────────────────────
  Band              Confidence range   Target frequency
  ─────────────────────────────────────────────────────
  AUTO_APPROVE      [0.00, 0.10)       ~40 %
  HUMAN_REVIEW      [0.10, 0.90]       ~20 %
  AUTO_FLAG         (0.90, 1.00]       ~40 %
  ─────────────────────────────────────────────────────

This module must remain free of PyTorch / transformers imports so Phase 1
can run without a GPU or heavy downloads.  Swap run() in Phase 2.
"""

from __future__ import annotations

import random
from typing import Optional, Tuple

from app.logger import get_logger

logger = get_logger(__name__)


def run(
    image_path: str,
    manual_text_override: Optional[str] = None,
) -> Tuple[str, float]:
    """
    Simulate model inference.

    Parameters
    ----------
    image_path : str
        Path to the saved upload (logged but not read in Phase 1).
    manual_text_override : str | None
        Optional OCR-override text (reserved for Phase 2; logged here).

    Returns
    -------
    (label, confidence) : (str, float)
        label      — "Harmful" | "Safe"
        confidence — float in [0.0, 1.0]
    """
    logger.info(
        "[mock_inference.run] START — image_path=%r | text_override=%r",
        image_path,
        manual_text_override,
    )

    try:
        # ── Band selection (weighted) ──────────────────────────────────────────
        # Weights: 40 % AUTO_APPROVE, 20 % HUMAN_REVIEW, 40 % AUTO_FLAG
        band = random.choices(
            population=["approve", "review", "flag"],
            weights=[40, 20, 40],
            k=1,
        )[0]

        if band == "approve":
            confidence = round(random.uniform(0.00, 0.099), 4)
        elif band == "review":
            confidence = round(random.uniform(0.10, 0.90), 4)
        else:  # flag
            confidence = round(random.uniform(0.901, 1.00), 4)

        # ── Label: correlated loosely with confidence ──────────────────────────
        # High confidence → likely harmful; low confidence → likely safe.
        # HUMAN_REVIEW band is genuinely ambiguous, so 50/50.
        if confidence > 0.90:
            label = "Harmful"
        elif confidence < 0.10:
            label = "Safe"
        else:
            label = random.choice(["Harmful", "Safe"])

        logger.info(
            "[mock_inference.run] SUCCESS — label=%r | confidence=%s | band=%s",
            label,
            confidence,
            band,
        )
        return label, confidence

    except Exception as exc:
        logger.error(
            "[mock_inference.run] FAILED — reason: %s", str(exc), exc_info=True
        )
        raise RuntimeError(f"Mock inference failed: {exc}") from exc
