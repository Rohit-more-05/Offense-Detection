"""Back up existing locally available uploads to durable image storage.

Preview by default; pass --apply to save the image bytes and content hashes.
"""
import argparse
import hashlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image
from sqlalchemy import select
from core.config import BACKEND_DIR, get_settings
from core.database import SessionLocal
from models.prediction import Prediction
from models.meme_image import MemeImage
from services.image_storage import save_image


def backfill(db, apply=False):
    settings = get_settings()
    roots = [settings.storage_path(settings.upload_dir), BACKEND_DIR / "storage/uploads", BACKEND_DIR / "app/storage/uploads"]
    result = {"saved" if apply else "eligible": 0, "already_stored": 0, "unavailable": 0}
    for row in db.execute(select(Prediction)).scalars().all():
        if row.image_sha256 and db.get(MemeImage, row.image_sha256):
            result["already_stored"] += 1
            continue
        path = Path(row.image_path)
        path = path if path.is_absolute() else BACKEND_DIR / path
        if not any(path.resolve().is_relative_to(root.resolve()) for root in roots) or not path.is_file():
            result["unavailable"] += 1
            continue
        if path.stat().st_size > settings.max_upload_bytes:
            result["unavailable"] += 1
            continue
        data = path.read_bytes()
        try:
            with Image.open(io.BytesIO(data)) as image:
                mime = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}.get(image.format)
                image.verify()
            if not mime:
                raise ValueError("unsupported format")
            digest = hashlib.sha256(data).hexdigest()
            if row.image_sha256 and row.image_sha256 != digest:
                raise ValueError("image changed")
        except (OSError, ValueError):
            result["unavailable"] += 1
            continue
        if apply:
            save_image(db, digest, mime, data)
            row.image_sha256 = digest
        result["saved" if apply else "eligible"] += 1
    if apply:
        db.commit()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as db:
        print(json.dumps(backfill(db, args.apply), indent=2))
