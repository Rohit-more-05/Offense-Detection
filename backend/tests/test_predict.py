from unittest.mock import patch

import pytest

from models.prediction import Prediction


def upload(client, data, name="untrusted_1_harmful.png", endpoint="predict"):
    return client.post(f"/api/v1/{endpoint}", files={"file": (name, data, "image/png")})


def test_full_upload_stores_text_score_and_provenance(client, image_bytes, inference, db):
    response = upload(client, image_bytes)
    assert response.status_code == 200
    data = response.json()
    assert data["label"] == "Safe"  # Contextual verdict, not the filename.
    assert data["baseline_label"] == "Harmful"
    assert data["harmful_probability"] == 0.6
    assert data["moderation_decision"] == "HUMAN_REVIEW"
    assert data["persisted"] is True
    assert data["heatmap_url"] is None
    row = db.get(Prediction, data["prediction_id"])
    assert row.extracted_text == inference["assessment"].extracted_text
    assert row.reviewed is False and row.human_verdict is None
    assert row.image_sha256 and row.model_version == "test-model"
    assert client.get(data["image_url"]).status_code == 200


@pytest.mark.parametrize("kind", ["document", "screenshot", "photograph"])
def test_non_meme_never_becomes_harmful_or_safe(client, image_bytes, inference, kind):
    inference["assessment"].content_type = kind
    inference["assessment"].verdict = "not_applicable"
    with patch("services.model_service.predict") as predictor:
        data = upload(client, image_bytes).json()
    predictor.assert_not_called()
    assert data["label"] == "Not a meme"
    assert data["harmful_probability"] is None
    assert data["moderation_decision"] == "HUMAN_REVIEW"


@pytest.mark.parametrize("status", ["error", "no_text"])
def test_ocr_failure_or_empty_text_abstains(client, image_bytes, inference, status):
    inference.update(assessment=None, status=status)
    with patch("services.model_service.predict") as predictor:
        data = upload(client, image_bytes).json()
    predictor.assert_not_called()
    assert data["label"] == "Needs review"
    assert data["harmful_probability"] is None


def test_actual_image_bytes_validated(client, inference):
    assert upload(client, b"not an image").status_code == 400


def test_size_limit(client, image_bytes, inference, monkeypatch):
    from core.config import get_settings
    monkeypatch.setattr(get_settings(), "max_upload_bytes", 10)
    assert upload(client, image_bytes).status_code == 413


def test_both_endpoints_use_reviewable_predictions(client, image_bytes, inference):
    data = upload(client, image_bytes, endpoint="detect").json()
    ids = [row["prediction_id"] for row in client.get("/api/v1/review-queue").json()]
    assert data["prediction_id"] in ids


def test_database_failure_is_visible(client, image_bytes, inference):
    with patch("sqlalchemy.orm.Session.commit", side_effect=RuntimeError("offline")):
        data = upload(client, image_bytes).json()
    assert data["persisted"] is False
    assert any("NOT saved" in message for message in data["warnings"])


def test_model_failure_is_review_not_false_classification(client, image_bytes, inference):
    with patch("services.model_service.predict", side_effect=RuntimeError("model missing")):
        data = upload(client, image_bytes).json()
    assert data["label"] == "Needs review" and data["harmful_probability"] is None


def test_health_identifies_this_service(client):
    assert client.get("/health").json()["service"] == "memeguard"
