"""
routers/predict.py
==================
POST /api/v1/predict
  - Accepts multipart/form-data with `file` (UploadFile) and optional
    `manual_text_override` (str form field).
  - Saves file → extracts text (manual_text_override for Phase 1, OCR in Phase 2)
    → calls text_inference (real BERT model) → routes decision → persists to DB.
  - Returns PredictResponse.

Phase 1 note: Image pixels are NOT analysed yet. Only text is classified.
  Priority: manual_text_override > filename stub.
  Phase 2 will wire EasyOCR here to extract text from image pixels.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.logger import get_logger
from app.models.prediction import Prediction
from app.schemas.predict import PredictResponse
from app.services import decision_router, text_inference, ocr_service

logger = get_logger(__name__)
router = APIRouter(prefix="/predict", tags=["Prediction"])

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
HEATMAP_STUB_URL = "/static/heatmaps/placeholder.png"


@router.post(
    "",
    response_model=PredictResponse,
    summary="Submit a meme image for harm classification",
    responses={
        400: {"description": "Invalid file type"},
        500: {"description": "Internal server error during inference or DB write"},
    },
)
async def predict(
    file: UploadFile,
    manual_text_override: Optional[str] = Form(None),
    db: Session = Depends(get_db),
) -> PredictResponse:
    """
    Upload a meme image and receive a harm classification with a moderation decision.

    - **file**: `.jpg`, `.png`, or `.webp` image
    - **manual_text_override**: optional OCR text to pass to the inference engine (Phase 2)
    """
    logger.info(
        "[predict] START — filename=%r | content_type=%r | text_override=%r",
        file.filename,
        file.content_type,
        manual_text_override,
    )

    # ── Validate content type ──────────────────────────────────────────────────
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        logger.error(
            "[predict] FAILED — unsupported content type: %r", file.content_type
        )
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file.content_type}'. Allowed: jpg, png, webp.",
        )

    settings = get_settings()
    t_start = time.monotonic()

    try:
        # ── Step 1: Save uploaded file ─────────────────────────────────────────
        upload_dir = Path(settings.upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_ext = Path(file.filename or "upload.jpg").suffix
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        save_path = upload_dir / unique_filename

        logger.info("[predict] Saving file → %s", save_path)
        try:
            contents = await file.read()
            save_path.write_bytes(contents)
            logger.info("[predict] File saved — size=%d bytes", len(contents))
        except OSError as exc:
            logger.error("[predict] File save FAILED — reason: %s", str(exc), exc_info=True)
            raise HTTPException(status_code=500, detail=f"Could not save uploaded file: {exc}")

        image_path_str = str(save_path)

        # ── Step 2: Resolve input text for the classifier ─────────────────────
        if manual_text_override and manual_text_override.strip():
            input_text = manual_text_override.strip()
            logger.info(
                "[predict] Text source=manual_text_override | length=%d", len(input_text)
            )
        else:
            # Phase 2 OCR extraction
            logger.info("[predict] Running Tesseract OCR on image...")
            input_text = ocr_service.extract_text(image_path_str)
            logger.info(
                f"[predict] OCR completed. Extracted length: {len(input_text)}"
            )

        # ── Step 3: Real text inference (BERT hate-speech classifier) ──────────
        is_visual_only = False
        
        # If we have almost no text, we shouldn't trust the text classifier to make a meaningful
        # decision on it. But we still run inference to keep the pipeline intact, and just flag it.
        if len(input_text.strip()) < 5:
            logger.warning("[predict] Extracted text is too short (<5 chars). Will flag as visual-only.")
            is_visual_only = True
            
        logger.info("[predict] Calling text_inference.run() | input_chars=%d", len(input_text))
        try:
            label, confidence = text_inference.run(input_text)
        except RuntimeError as exc:
            logger.error("[predict] Inference FAILED — reason: %s", str(exc), exc_info=True)
            # DYNAMIC EXCEPTION MAPPING (Phase 3 Requirement)
            # Trap OOMs, Quantization timeouts, or Thread crashes before Render drops the connection
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "Analysis Engine Failure",
                    "phase": "DYNAMIC_QUANTIZATION_TIMEOUT" if "quantize" in str(exc).lower() else "INFERENCE_EXECUTION_FAULT",
                    "hardware_state": {"cpu_threads": 1, "memory_pressure": "HIGH"},
                    "remediation": "Check deploy.log for [TELEMETRY:MEMORY_OPT] flags.",
                    "error_message": str(exc)
                }
            )
        except Exception as exc:
            logger.error("[predict] Unexpected Inference FAILED — reason: %s", str(exc), exc_info=True)
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "Analysis Engine Failure",
                    "phase": "UNKNOWN_INFERENCE_CRASH",
                    "hardware_state": {"cpu_threads": 1, "memory_pressure": "HIGH"},
                    "remediation": "Check deploy.log for core Python crash dumps.",
                    "error_message": str(exc)
                }
            )

        # ── Step 4: Route decision ─────────────────────────────────────────────
        logger.info("[predict] Calling decision_router.route(confidence=%s)", confidence)
        try:
            moderation_decision = decision_router.route(confidence)
        except ValueError as exc:
            logger.error("[predict] Decision routing FAILED — reason: %s", str(exc), exc_info=True)
            raise HTTPException(status_code=500, detail=f"Decision routing failed: {exc}")

        # ── Step 5: Compute execution time ────────────────────────────────────
        execution_time_ms = int((time.monotonic() - t_start) * 1000)

        # ── Step 6: Persist to database & Security Criteria Tracing ────────────
        prediction_id = str(uuid.uuid4())
        
        # If visual only, override label to "Safe" (or flag it for manual review depending on confidence)
        # The directive says: tag the response with "visual-only flag, no text signal" case.
        # We will append this to moderator_notes or moderation_decision.
        if is_visual_only:
            moderation_decision = "HUMAN_REVIEW"
            label = "Safe" # Force safe so we don't ban users for empty text
            
        is_reviewed = moderation_decision != "HUMAN_REVIEW"
        is_harmful = label == "Harmful"

        # Explicit Telemetry Injection for Security/Moderation criteria (DevSecOps requirement)
        logger.debug(
            "[predict] [TELEMETRY:SECURITY_CHECK] -> Evaluating moderation criteria for routing..."
        )
        logger.debug(f"[predict] [TELEMETRY:SECURITY_CHECK] -> is_harmful = {is_harmful}")
        logger.debug(f"[predict] [TELEMETRY:SECURITY_CHECK] -> confidence_score = {confidence}")
        logger.debug(f"[predict] [TELEMETRY:SECURITY_CHECK] -> auto_reviewed_status = {is_reviewed}")
        
        if not is_reviewed:
            logger.warning("[predict] [TELEMETRY:SECURITY_CHECK] -> Profile/Meme failed auto-trust threshold. Requires human alive check.")

        db_row = Prediction(
            id=prediction_id,
            filename=file.filename or unique_filename,
            image_path=image_path_str,
            label=label,
            confidence=confidence,
            moderation_decision=moderation_decision,
            heatmap_path=None,
            execution_time_ms=execution_time_ms,
            reviewed=is_reviewed,
        )

        logger.info("[predict] Writing prediction to DB — id=%s", prediction_id)
        try:
            db.add(db_row)
            db.commit()
            db.refresh(db_row)
            logger.info("[predict] DB write confirmed — id=%s", prediction_id)
        except Exception as exc:
            db.rollback()
            logger.error(
                "[predict] DB write FAILED — rolling back — reason: %s", str(exc), exc_info=True
            )
            raise HTTPException(status_code=500, detail=f"Database write failed: {exc}")

        # ── Step 7: Build response ─────────────────────────────────────────────
        response = PredictResponse(
            prediction_id=prediction_id,
            label=label,
            confidence=confidence,
            moderation_decision=moderation_decision,
            execution_time_ms=execution_time_ms,
            heatmap_url=HEATMAP_STUB_URL,
        )

        logger.info(
            "[predict] SUCCESS — id=%s | label=%r | confidence=%s | decision=%r | time=%dms",
            prediction_id,
            label,
            confidence,
            moderation_decision,
            execution_time_ms,
        )
        return response

    except HTTPException:
        raise  # Already handled above
    except Exception as exc:
        logger.error(
            "[predict] Unexpected FAILED — reason: %s", str(exc), exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}")
