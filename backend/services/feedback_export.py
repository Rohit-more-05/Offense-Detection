"""Export only explicit human labels, with images and text kept together."""
import hashlib
import json
import io
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageOps
from sqlalchemy import select

from core.config import BACKEND_DIR
from models.prediction import Prediction
from models.meme_image import MemeImage


def export_feedback(db, output_dir: Path) -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    image_dir = output_dir / "images"
    image_dir.mkdir(exist_ok=True)
    rows = db.execute(select(Prediction).where(
        Prediction.reviewed.is_(True), Prediction.human_verdict.is_not(None),
        Prediction.reviewed_at.is_not(None),
    ).order_by(Prediction.reviewed_at.asc())).scalars().all()
    groups = defaultdict(list)
    skipped = []
    for row in rows:
        path = Path(row.image_path)
        if not path.is_absolute():
            path = BACKEND_DIR / path
        stored = db.get(MemeImage, row.image_sha256) if row.image_sha256 else None
        if not path.is_file() and stored is None:
            skipped.append({"prediction_id": row.id, "reason": "image_missing"})
            continue
        try:
            # Pixel hash deduplicates renamed images and containers with changed
            # metadata. Near-duplicate meme templates still need dataset review.
            payload = stored.content if stored else path.read_bytes()
            with Image.open(io.BytesIO(payload)) as source:
                image = ImageOps.exif_transpose(source).convert("RGB")
                digest = hashlib.sha256(str(image.size).encode() + image.tobytes()).hexdigest()
                suffix = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}.get(source.format, ".png")
        except (OSError, ValueError):
            skipped.append({"prediction_id": row.id, "reason": "image_invalid"})
            continue
        groups[digest].append((row, payload, suffix))
    examples = []
    for digest, members in groups.items():
        if len({row.human_verdict for row, _, _ in members}) > 1:
            skipped.extend({"prediction_id": row.id, "reason": "conflicting_human_labels"} for row, _, _ in members)
            continue
        row, payload, suffix = members[-1]
        if row.human_verdict not in {"Harmful", "Non-Harmful", "Not a meme"}:
            continue
        if row.human_verdict != "Not a meme" and not (row.extracted_text or "").strip():
            skipped.append({"prediction_id": row.id, "reason": "transcription_missing"})
            continue
        relative = f"images/{digest}{suffix}"
        (output_dir / relative).write_bytes(payload)
        examples.append({
            "id": row.id, "image": relative, "pixel_sha256": digest,
            "text": row.extracted_text or "", "human_verdict": row.human_verdict,
            "label": {"Non-Harmful": 0, "Harmful": 1}.get(row.human_verdict),
            "is_meme": row.human_verdict != "Not a meme",
            "split": "unassigned", "label_source": "human",
            "reviewed_at": row.reviewed_at.isoformat(), "notes": row.reviewer_notes,
        })
    (output_dir / "feedback.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in examples), encoding="utf-8",
    )
    summary = {"reviewed_rows": len(rows), "exported_examples": len(examples), "skipped": skipped}
    (output_dir / "export_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
