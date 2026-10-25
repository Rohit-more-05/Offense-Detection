"""Validated uploads -> shared analysis -> durable prediction/review record."""
from __future__ import annotations

import hashlib
import io
import logging
import time
import uuid
import warnings

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from core.config import get_settings
from core.database import get_db
from models.prediction import Prediction
from schemas.predict import PredictResponse
from services import analysis_service
from services.image_storage import save_image

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/predict", tags=["Prediction"])
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}


async def process_upload(file: UploadFile, manual_text: str | None, db: Session) -> PredictResponse:
    settings = get_settings()
    start = time.monotonic()
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(400, "Unsupported file type. Upload a JPEG, PNG or WebP image.")
    contents = await file.read(settings.max_upload_bytes + 1)
    if len(contents) > settings.max_upload_bytes:
        raise HTTPException(413, "Image exceeds the upload size limit.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(contents)) as image:
                suffix = FORMATS.get(image.format)
                if not suffix or getattr(image, "n_frames", 1) != 1:
                    raise HTTPException(400, "Upload a single-frame JPEG, PNG or WebP image.")
                if image.width * image.height > settings.max_image_pixels:
                    raise HTTPException(413, "Image dimensions exceed the limit.")
                image.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(400, "The uploaded file is not a valid supported image.")

    prediction_id = str(uuid.uuid4())
    directory = settings.storage_path(settings.upload_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (prediction_id + suffix)
    path.write_bytes(contents)
    # External OCR and CPU inference must not block the server's event loop.
    result = await run_in_threadpool(analysis_service.analyze, str(path), manual_text)
    elapsed = int((time.monotonic() - start) * 1000)
    row = Prediction(
        id=prediction_id, filename=(file.filename or path.name)[:512], image_path=str(path),
        image_sha256=hashlib.sha256(contents).hexdigest(), label=result.label,
        confidence=result.harmful_probability, moderation_decision=result.moderation_decision,
        execution_time_ms=elapsed, extracted_text=result.extracted_text,
        ocr_source=result.ocr_source, ocr_status=result.ocr_status,
        model_version=result.model_version, content_type=result.content_type,
        decision_source=result.decision_source, analysis_reason=result.reason,
        analysis_metadata={**result.diagnostics, "warnings": result.warnings},
        # An automated action is never a human-reviewed training label.
        reviewed=False,
    )
    persisted = False
    try:
        save_image(db, row.image_sha256, {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}[suffix], contents)
        db.add(row)
        db.commit()
        persisted = True
    except Exception as exc:
        db.rollback()
        logger.error("Prediction persistence failed (%s)", type(exc).__name__)
        result.warnings.append("Result was NOT saved. Database unavailable or migration missing; moderator feedback is unavailable for this upload.")

    return PredictResponse(
        prediction_id=prediction_id, label=result.label, confidence=result.harmful_probability,
        harmful_probability=result.harmful_probability, baseline_label=result.baseline_label,
        moderation_decision=result.moderation_decision, execution_time_ms=elapsed,
        image_url=(f"/api/v1/images/{prediction_id}" if persisted else f"/static/uploads/{path.name}"), extracted_text=result.extracted_text,
        ocr_source=result.ocr_source, ocr_status=result.ocr_status,
        content_type=result.content_type, decision_source=result.decision_source,
        reason=result.reason, model_version=result.model_version,
        persisted=persisted, warnings=result.warnings,
    )


@router.post("", response_model=PredictResponse)
async def predict(
    file: UploadFile, manual_text_override: str | None = Form(None, max_length=20000),
    db: Session = Depends(get_db),
) -> PredictResponse:
    return await process_upload(file, manual_text_override, db)
