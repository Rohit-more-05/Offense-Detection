"""Regression tests for decision policy; the shipped model is multimodal."""
import pytest

from services import decision_router, analysis_service, ocr_service


@pytest.mark.parametrize("score,expected", [(0, "AUTO_APPROVE"), (0.1, "HUMAN_REVIEW"), (0.5, "HUMAN_REVIEW"), (0.9, "HUMAN_REVIEW"), (1, "AUTO_FLAG")])
def test_threshold_boundaries(score, expected):
    assert decision_router.route(score) == expected


@pytest.mark.parametrize("score", [-1, 1.1, float("nan")])
def test_invalid_scores_rejected(score):
    with pytest.raises(ValueError):
        decision_router.route(score)


def test_manual_transcription_never_auto_approved(inference):
    inference["probability"] = 0.01
    inference["assessment"].certainty = "high"
    result = analysis_service.analyze("unused.png", "This is manually provided text")
    assert result.moderation_decision == "HUMAN_REVIEW"
    assert result.ocr_source == "manual_override"


def test_vision_failure_falls_back_to_real_local_ocr(monkeypatch):
    from core.config import get_settings
    monkeypatch.setattr(get_settings(), "gemini_api_key", "test-only")
    monkeypatch.setattr(ocr_service, "_rapid_ocr", lambda _: (_ for _ in ()).throw(RuntimeError("missing")))
    monkeypatch.setattr(ocr_service, "_gemini_assessment", lambda *_: (_ for _ in ()).throw(RuntimeError("503")))
    monkeypatch.setattr(ocr_service, "_local_ocr", lambda _: "Some locally read text")
    result = ocr_service.analyze_image("unused.png")
    assert result.status == "ok" and result.source == "tesseract"
    assert result.assessment is None
    assert len(result.warnings) == 2


def test_all_ocr_failures_are_errors(monkeypatch):
    monkeypatch.setattr(ocr_service, "_rapid_ocr", lambda _: (_ for _ in ()).throw(RuntimeError("missing")))
    monkeypatch.setattr(ocr_service, "_local_ocr", lambda _: (_ for _ in ()).throw(RuntimeError("missing")))
    result = ocr_service.analyze_image("unused.png")
    assert result.status == "error"
    with pytest.raises(RuntimeError, match="OCR unavailable"):
        ocr_service.extract_text("unused.png")
