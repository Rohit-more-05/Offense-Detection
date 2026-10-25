from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from core.config import BACKEND_DIR, get_settings
from core.database import get_db
from models.meme_image import MemeImage
from models.prediction import Prediction

router = APIRouter(tags=["Images"])


@router.get("/images/{prediction_id}")
def get_image(prediction_id: UUID, db: Session = Depends(get_db)):
    try:
        row = db.get(Prediction, str(prediction_id))
        if row is None:
            raise HTTPException(404, "Image not found")
        stored = db.get(MemeImage, row.image_sha256) if row.image_sha256 else None
        if stored:
            return Response(stored.content, media_type=stored.content_type, headers={"Cache-Control": "private, max-age=3600"})
        # Older rows predate durable image storage. Serve them only from the
        # application's configured upload directories, never arbitrary paths.
        path = Path(row.image_path)
        path = path if path.is_absolute() else BACKEND_DIR / path
        roots = [get_settings().storage_path(get_settings().upload_dir), BACKEND_DIR / "storage/uploads", BACKEND_DIR / "app/storage/uploads"]
        if any(path.resolve().is_relative_to(root.resolve()) for root in roots) and path.is_file():
            return FileResponse(path)
        raise HTTPException(404, "Original image is no longer available")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, "Image storage unavailable")
