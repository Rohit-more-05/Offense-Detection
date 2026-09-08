from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables / .env file.
    All thresholds are configurable so Phase 2 can tune them without code changes.
    """

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str  # Supabase Transaction Pooler connection string

    # ── Environment ───────────────────────────────────────────────────────────
    environment: str = "development"
    log_level: str = "DEBUG"

    # ── Storage paths (relative to backend/) ──────────────────────────────────
    upload_dir: str = "app/storage/uploads"
    heatmap_dir: str = "app/storage/heatmaps"

    # ── Decision thresholds (SRS FR6) ─────────────────────────────────────────
    auto_approve_threshold: float = 0.10
    auto_flag_threshold: float = 0.90

    # ── CORS ──────────────────────────────────────────────────────────────────
    cors_origins: List[str] = ["http://localhost:5173"]


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton — call this everywhere instead of constructing Settings()."""
    return Settings()
