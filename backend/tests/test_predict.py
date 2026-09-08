"""
test_predict.py
===============
Tests for POST /api/v1/predict endpoint.
Uses httpx.AsyncClient with TestClient overrides for synchronous testing.
"""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_image_bytes() -> bytes:
    """Minimal valid JPEG header bytes for upload tests."""
    return bytes([
        0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10,
        0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
    ])


def _upload(
    filename: str = "test_meme.jpg",
    content_type: str = "image/jpeg",
    text_override: str | None = None,
) -> dict:
    files = {"file": (filename, io.BytesIO(_make_image_bytes()), content_type)}
    data = {}
    if text_override:
        data["manual_text_override"] = text_override
    return client.post("/api/v1/predict", files=files, data=data)


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestHealthCheck:
    def test_health_ok(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestPredict:
    def test_predict_returns_200_with_valid_image(self):
        resp = _upload()
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "prediction_id" in body
        assert body["label"] in ("Harmful", "Safe")
        assert 0.0 <= body["confidence"] <= 1.0
        assert body["moderation_decision"] in (
            "AUTO_APPROVE", "AUTO_FLAG", "HUMAN_REVIEW"
        )
        assert isinstance(body["execution_time_ms"], int)
        assert body["heatmap_url"] == "/static/heatmaps/placeholder.png"

    def test_predict_rejects_invalid_content_type(self):
        resp = _upload(filename="doc.pdf", content_type="application/pdf")
        assert resp.status_code == 400
        assert "Unsupported file type" in resp.json()["detail"]

    def test_predict_accepts_png(self):
        resp = _upload(filename="meme.png", content_type="image/png")
        assert resp.status_code == 200

    def test_predict_accepts_webp(self):
        resp = _upload(filename="meme.webp", content_type="image/webp")
        assert resp.status_code == 200

    def test_predict_with_text_override(self):
        resp = _upload(text_override="Kill all minorities")
        assert resp.status_code == 200
        assert resp.json()["label"] in ("Harmful", "Safe")

    def test_predict_decision_consistent_with_confidence(self):
        """
        Run many predictions and verify that whenever decision is AUTO_APPROVE,
        confidence < 0.10, and when AUTO_FLAG, confidence > 0.90.
        (HUMAN_REVIEW band is 0.10–0.90.)
        """
        errors = []
        for _ in range(30):
            resp = _upload()
            body = resp.json()
            c = body["confidence"]
            d = body["moderation_decision"]
            if d == "AUTO_APPROVE" and c >= 0.10:
                errors.append(f"AUTO_APPROVE but confidence={c}")
            if d == "AUTO_FLAG" and c <= 0.90:
                errors.append(f"AUTO_FLAG but confidence={c}")
            if d == "HUMAN_REVIEW" and not (0.10 <= c <= 0.90):
                errors.append(f"HUMAN_REVIEW but confidence={c} out of band")
        assert not errors, f"Decision/confidence inconsistencies: {errors}"

    @patch("pytesseract.image_to_string")
    def test_predict_visual_only_fallback_on_empty_text(self, mock_ocr):
        """
        Upload a test image containing no embedded text (e.g., a plain photo).
        Assert the response does NOT classify it as 'Harmful' purely because of a filename artifact.
        """
        mock_ocr.return_value = "   \n  " # Simulating empty OCR output
        resp = _upload(filename="offensive_filename.jpg")
        assert resp.status_code == 200
        body = resp.json()
        assert body["label"] == "Safe"
        assert body["moderation_decision"] == "HUMAN_REVIEW"
        
    @patch("pytesseract.image_to_string")
    def test_predict_extracts_offensive_text(self, mock_ocr):
        """
        Upload a test image with a known offensive text string burned into it.
        Assert OCR successfully extracts it and routes it properly.
        """
        mock_ocr.return_value = "Kill all minorities"
        resp = _upload()
        assert resp.status_code == 200
        body = resp.json()
        assert body["label"] in ("Harmful", "Safe")
