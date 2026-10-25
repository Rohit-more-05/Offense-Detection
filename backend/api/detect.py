"""Compatibility endpoint using the same inference and persistence as /predict."""
from fastapi import APIRouter, Depends, Form, UploadFile
from sqlalchemy.orm import Session

from api.predict import process_upload
from core.database import get_db
from schemas.predict import PredictResponse

router = APIRouter(tags=["Prediction"])


@router.post("/detect", response_model=PredictResponse)
async def detect_meme(
    file: UploadFile, text: str | None = Form(None, max_length=20000),
    db: Session = Depends(get_db),
):
    return await process_upload(file, text, db)
