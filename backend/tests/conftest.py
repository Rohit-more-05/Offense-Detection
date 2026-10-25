import io
import os
import tempfile
from pathlib import Path

import pytest
from PIL import Image

# All automated tests use an isolated database and mock remote inference. Never
# write test verdicts to the user's Supabase or invoke a paid API at collection.
_temp = tempfile.TemporaryDirectory(prefix="memeguard-tests-")
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(_temp.name) / "tests.db").replace("\\", "/")
os.environ["UPLOAD_DIR"] = str(Path(_temp.name) / "uploads")
os.environ["GEMINI_API_KEY"] = ""
os.environ["CONTEXT_VERIFICATION_ENABLED"] = "true"

from core.database import Base, SessionLocal, engine
from main import app
from fastapi.testclient import TestClient
from services import model_service, ocr_service


@pytest.fixture(autouse=True)
def clean_database():
    ocr_service._provider_cooldowns.clear()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture(scope="session", autouse=True)
def close_test_database():
    yield
    engine.dispose()
    _temp.cleanup()


@pytest.fixture
def client():
    # No startup network/model loads. The dependencies use real SQLite sessions.
    return TestClient(app)


@pytest.fixture
def image_bytes():
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), "white").save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def inference(monkeypatch):
    state = {"probability": 0.6, "assessment": ocr_service.VisionAssessment(
        extracted_text="A fictional meme caption", content_type="meme", text_readable=True,
        verdict="non_harmful", certainty="medium", reason="Benign fictional humor.",
    ), "status": "ok"}
    def ocr(_):
        a = state["assessment"]
        return ocr_service.OCRResult(a.extracted_text if a else "", state["status"], "test-ocr", a)
    monkeypatch.setattr(ocr_service, "analyze_image", ocr)
    monkeypatch.setattr(model_service, "predict", lambda image, text: state["probability"])
    monkeypatch.setattr(model_service, "text_diagnostics", lambda text: {"tokens_used": 5, "unknown_token_fraction": 0, "text_may_be_truncated": False})
    monkeypatch.setattr(model_service, "MODEL_VERSION", "test-model")
    return state


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session
