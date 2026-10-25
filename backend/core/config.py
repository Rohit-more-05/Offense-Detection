from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8",
        case_sensitive=False, extra="ignore",
    )
    database_url: str
    environment: str = "development"
    log_level: str = "INFO"
    upload_dir: str = "storage/uploads"
    heatmap_dir: str = "storage/heatmaps"
    auto_approve_threshold: float = Field(0.10, ge=0, le=1)
    auto_flag_threshold: float = Field(0.90, ge=0, le=1)
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:5174"]
    max_upload_bytes: int = Field(10 * 1024 * 1024, gt=0)
    max_image_pixels: int = Field(20_000_000, gt=0)
    # The contextual verifier never rewrites the Keras score.
    context_verification_enabled: bool = True
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    gemini_fallback_model: str = "gemini-3.5-flash"
    vision_timeout_seconds: int = Field(35, ge=1, le=120)
    tesseract_cmd: str = ""
    ocr_languages: str = "eng"

    @model_validator(mode="after")
    def validate_thresholds(self):
        if self.auto_approve_threshold >= self.auto_flag_threshold:
            raise ValueError("AUTO_APPROVE_THRESHOLD must be below AUTO_FLAG_THRESHOLD")
        return self

    def storage_path(self, value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else BACKEND_DIR / path


@lru_cache()
def get_settings() -> Settings:
    return Settings()
