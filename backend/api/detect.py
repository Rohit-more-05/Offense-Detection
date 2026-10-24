import os
from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException
from sqlalchemy.orm import Session
from pathlib import Path
from pydantic import BaseModel

from core.database import get_db
from core.logger import get_logger
from services.model_service import predict, preprocess_image, preprocess_text
from services.ocr_service import extract_text
from models.scan_history import ScanHistory
import shutil

router = APIRouter()
logger = get_logger(__name__)

# Basic schema for response
class DetectResponse(BaseModel):
    harmful_probability: float
    extracted_text: str

UPLOAD_DIR = Path("storage/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@router.post("/detect", response_model=DetectResponse)
async def detect_meme(
    file: UploadFile = File(...),
    text: str = Form(None),
    db: Session = Depends(get_db)
):
    try:
        # Save image temporarily
        file_ext = os.path.splitext(file.filename)[1]
        if not file_ext:
            file_ext = ".jpg"
        temp_path = UPLOAD_DIR / f"temp_{os.urandom(8).hex()}{file_ext}"
        
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # If no text provided, use OCR
        final_text = text
        if not final_text or not final_text.strip():
            logger.info("No text provided. Running OCR.")
            final_text = extract_text(str(temp_path))
        
        # Inference
        probability = predict(str(temp_path), final_text)
        
        # Log via ORM
        scan = ScanHistory(
            image_path=str(temp_path),
            extracted_text=final_text,
            harmful_probability=probability
        )
        db.add(scan)
        db.commit()
        db.refresh(scan)
        
        return DetectResponse(
            harmful_probability=probability,
            extracted_text=final_text or ""
        )
        
    except Exception as e:
        logger.error(f"Error in /detect endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")
