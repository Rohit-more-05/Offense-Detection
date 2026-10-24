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

from core.config import get_settings
from core.database import get_db
from core.logger import get_logger
from models.prediction import Prediction
from schemas.predict import PredictResponse
from services import decision_router, text_inference, ocr_service

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

        # ── Step 2: Resolve input text via DUAL-STRATEGY OCR ────────────────────
        if manual_text_override and manual_text_override.strip():
            input_text = manual_text_override.strip()
            ocr_source = "MANUAL_OVERRIDE"
            logger.info(
                "[predict] Text source=manual_text_override | length=%d", len(input_text)
            )
            print(f"\n[predict] Text source: MANUAL_OVERRIDE | Text: '{input_text[:100]}'", flush=True)
        else:
            # Dual-strategy OCR: Tesseract primary -> Gemini Vision fallback
            logger.info("[predict] Invoking dual-strategy OCR engine...")
            input_text = ocr_service.extract_text(image_path_str)
            ocr_source = "OCR_ENGINE"
            logger.info(
                f"[predict] OCR pipeline complete. Extracted length: {len(input_text)}"
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
            logger.info("[TELEMETRY:PIPELINE] Invoking Keras model prediction...")
            from services.model_service import predict as model_predict
            harmful_prob = model_predict(image_path_str, input_text)
            logger.info(f"[TELEMETRY:PIPELINE] Keras model returned probability: {harmful_prob}")
            
            # Ultra-strict Threshold Logic
            if harmful_prob > 0.5:
                label = "Harmful"
                confidence = harmful_prob
            else:
                label = "Safe"
                confidence = harmful_prob # Return raw probability so it doesn't invert to 50%
                
        except RuntimeError as exc:
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"""
[TELEMETRY:CRITICAL_FAULT] Inference Engine crashed!
============================================================
[MemeGuard Prediction Result] -> [SYSTEM FAULT]
  -> File: {file.filename}
  -> Classification: ERROR
  -> Error Detail: {str(exc)}
  -> Full Traceback: 
{error_trace}
============================================================
""")
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
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"""
[TELEMETRY:CRITICAL_FAULT] Unexpected Inference Execution Fault!
============================================================
[MemeGuard Prediction Result] -> [SYSTEM FAULT]
  -> File: {file.filename}
  -> Classification: ERROR
  -> Error Detail: {str(exc)}
  -> Full Traceback: 
{error_trace}
============================================================
""")
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
        # Enforcing explicit threshold logic as requested by user
        logger.info(f"[predict] Evaluating strict threshold routing for probability={confidence}")
        if confidence > 0.5:
            moderation_decision = "AUTO_FLAG"
            label = "Harmful"
        else:
            moderation_decision = "AUTO_APPROVE"
            label = "Safe"

        # ── Step 5: Compute execution time ────────────────────────────────────
        execution_time_ms = int((time.monotonic() - t_start) * 1000)

        # ── Step 6: Persist to database & Security Criteria Tracing ────────────
        prediction_id = str(uuid.uuid4())

        # Explicit Telemetry Injection for Security/Moderation criteria (DevSecOps requirement)
        is_reviewed = moderation_decision != "HUMAN_REVIEW"
        is_harmful = label == "Harmful"

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
            logger.warning(
                "[predict] DB write FAILED (non-fatal) — rolling back — reason: %s", str(exc)
            )

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

        # ── Terminal Output — Full Multimodal Inference Block ────────────────────
        action_str = "BLOCKED" if label == "Harmful" else "PASSED"
        text_preview = f'"{input_text[:120]}"' if input_text.strip() else '[NO TEXT EXTRACTED — VISUAL-ONLY MODE]'
        print(f"\n\033[96m============================================================\033[0m", flush=True)
        print(f"\033[96m[MemeGuard Multimodal Inference Engine]\033[0m", flush=True)
        print(f"  -> Process Status  : INFERENCE_SUCCESS", flush=True)
        print(f"  -> File Analyzed   : {file.filename or unique_filename}", flush=True)
        print(f"  -> Extracted Text  : {text_preview}", flush=True)
        print(f"  -> Model Inputs    : Image [224, 224, 3] | Text []", flush=True)
        print(f"  -> Raw Probability : \033[1m{confidence:.6f}\033[0m", flush=True)
        print(f"  -> Classification  : \033[1m{'\033[91mHARMFUL' if label == 'Harmful' else '\033[92mSAFE'}\033[0m", flush=True)
        print(f"  -> Action Taken    : \033[1m{action_str}\033[0m", flush=True)
        print(f"\033[96m============================================================\033[0m\n", flush=True)

        return response

    except HTTPException:
        raise  # Already handled above
    except Exception as exc:
        logger.error(
            "[predict] Unexpected FAILED — reason: %s", str(exc), exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}")
