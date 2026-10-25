from unittest.mock import patch
from uuid import uuid4

from models.prediction import Prediction
from services.feedback_export import export_feedback
from tests.test_predict import upload


def test_feedback_round_trip_and_image_url(client, image_bytes, inference, db, tmp_path):
    result = upload(client, image_bytes, name="original name.png").json()
    queue = client.get("/api/v1/review-queue").json()
    assert queue[0]["image_url"] == result["image_url"]
    assert "original name" not in queue[0]["image_url"]
    response = client.post(f"/api/v1/review/{result['prediction_id']}/verdict", json={"human_verdict": "Non-Harmful", "notes": "Reviewed image and text."})
    assert response.status_code == 200
    assert client.get("/api/v1/review-queue").json() == []
    row = db.get(Prediction, result["prediction_id"])
    assert row.human_verdict == "Non-Harmful" and row.reviewed_at
    assert row.confidence == 0.6  # Preserve the wrong raw model prediction.
    summary = export_feedback(db, tmp_path)
    assert summary["exported_examples"] == 1
    import json
    exported = json.loads((tmp_path / "feedback.jsonl").read_text())
    assert exported["label"] == 0 and exported["label_source"] == "human"
    assert (tmp_path / exported["image"]).is_file()


def test_auto_decisions_remain_correctable_and_not_training_labels(client, image_bytes, inference, db, tmp_path):
    inference["probability"] = 0.02
    inference["assessment"].certainty = "high"
    result = upload(client, image_bytes).json()
    assert result["moderation_decision"] == "AUTO_APPROVE"
    assert len(client.get("/api/v1/review-queue").json()) == 1
    assert export_feedback(db, tmp_path)["exported_examples"] == 0


def test_database_error_is_not_empty_queue(client):
    with patch("sqlalchemy.orm.Session.execute", side_effect=RuntimeError("offline")):
        assert client.get("/api/v1/review-queue").status_code == 503


def test_failed_verdict_is_not_success(client, image_bytes, inference):
    result = upload(client, image_bytes).json()
    with patch("sqlalchemy.orm.Session.commit", side_effect=RuntimeError("offline")):
        response = client.post(f"/api/v1/review/{result['prediction_id']}/verdict", json={"human_verdict": "Harmful"})
    assert response.status_code == 503
    assert len(client.get("/api/v1/review-queue").json()) == 1


def test_invalid_and_unknown_ids(client):
    assert client.post("/api/v1/review/invalid/verdict", json={"human_verdict": "Harmful"}).status_code == 422
    assert client.post(f"/api/v1/review/{uuid4()}/verdict", json={"human_verdict": "Harmful"}).status_code == 404


def test_conflicting_duplicate_labels_excluded_from_training(client, image_bytes, inference, db, tmp_path):
    for verdict in ["Harmful", "Non-Harmful"]:
        result = upload(client, image_bytes).json()
        client.post(f"/api/v1/review/{result['prediction_id']}/verdict", json={"human_verdict": verdict})
    summary = export_feedback(db, tmp_path)
    assert summary["exported_examples"] == 0
    assert all(row["reason"] == "conflicting_human_labels" for row in summary["skipped"])


def test_images_survive_loss_of_local_upload_directory(client, image_bytes, inference, db, tmp_path):
    from pathlib import Path
    result = upload(client, image_bytes).json()
    row = db.get(Prediction, result["prediction_id"])
    Path(row.image_path).unlink()  # Only this fixture's generated temporary file.
    assert client.get(result["image_url"]).content == image_bytes
    response = client.post(f"/api/v1/review/{row.id}/verdict", json={"human_verdict": "Non-Harmful"})
    assert response.status_code == 200
    db.expire_all()
    assert export_feedback(db, tmp_path)["exported_examples"] == 1


def test_repeated_uploads_share_durable_image_bytes(client, image_bytes, inference, db):
    from sqlalchemy import select, func
    from models.meme_image import MemeImage
    upload(client, image_bytes)
    upload(client, image_bytes)
    assert db.scalar(select(func.count()).select_from(MemeImage)) == 1
