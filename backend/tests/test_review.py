"""
test_review.py
==============
Tests for GET /api/v1/review-queue and POST /api/v1/review/{item_id}/verdict.
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _upload_and_get_human_review_id() -> str | None:
    """
    Upload images until we get a HUMAN_REVIEW decision.
    Returns the prediction_id or None after 50 attempts.
    """
    for _ in range(50):
        files = {"file": ("meme.jpg", io.BytesIO(b"\xff\xd8\xff"), "image/jpeg")}
        resp = client.post("/api/v1/predict", files=files)
        body = resp.json()
        if body.get("moderation_decision") == "HUMAN_REVIEW":
            return body["prediction_id"]
    return None


class TestReviewQueue:
    def test_review_queue_returns_list(self):
        resp = client.get("/api/v1/review-queue")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_review_queue_items_have_required_fields(self):
        # First ensure there's at least one HUMAN_REVIEW item
        _upload_and_get_human_review_id()
        resp = client.get("/api/v1/review-queue")
        assert resp.status_code == 200
        items = resp.json()
        if items:
            item = items[0]
            assert "prediction_id" in item
            assert "filename" in item
            assert "image_url" in item
            assert "label" in item
            assert "confidence" in item
            assert "created_at" in item


class TestVerdict:
    def test_verdict_404_for_unknown_id(self):
        resp = client.post(
            "/api/v1/review/nonexistent-uuid/verdict",
            json={"human_verdict": "Harmful"},
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_verdict_success(self):
        prediction_id = _upload_and_get_human_review_id()
        if prediction_id is None:
            pytest.skip("Could not generate a HUMAN_REVIEW item in 50 attempts")

        resp = client.post(
            f"/api/v1/review/{prediction_id}/verdict",
            json={"human_verdict": "Non-Harmful", "notes": "Sarcastic meme, not actual hate."},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["prediction_id"] == prediction_id
        assert body["status"] == "reviewed"
        assert "updated_at" in body

    def test_verdict_removes_item_from_queue(self):
        prediction_id = _upload_and_get_human_review_id()
        if prediction_id is None:
            pytest.skip("Could not generate a HUMAN_REVIEW item in 50 attempts")

        # Submit verdict
        client.post(
            f"/api/v1/review/{prediction_id}/verdict",
            json={"human_verdict": "Harmful"},
        )

        # Item should no longer appear in queue
        resp = client.get("/api/v1/review-queue")
        ids_in_queue = [item["prediction_id"] for item in resp.json()]
        assert prediction_id not in ids_in_queue

    def test_verdict_rejects_invalid_verdict(self):
        resp = client.post(
            "/api/v1/review/some-id/verdict",
            json={"human_verdict": "INVALID"},
        )
        assert resp.status_code == 422  # Pydantic validation error
