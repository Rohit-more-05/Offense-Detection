"""
main.py
=======
FastAPI application entry point.

Responsibilities:
  - CORS middleware
  - Global HTTP request/response logging middleware
  - Global exception handler (surfaces errors in Swagger response body)
  - Static file mounts for uploads and heatmaps
  - Router includes under /api/v1
  - Startup lifespan: verify Supabase + create tables
"""

from __future__ import annotations

import time
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import init_db, verify_connection, verify_predictions_table
from app.logger import get_logger
from app.routers import predict as predict_router
from app.routers import review as review_router

logger = get_logger(__name__)
settings = get_settings()


# ── Lifespan ───────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: verify DB + create tables. Shutdown: nothing extra needed."""
    logger.info("=" * 60)
    logger.info("🚀 Meme Detection API starting up …")
    logger.info("   Environment : %s", settings.environment)
    logger.info("   Log level   : %s", settings.log_level)

    # 1. Verify Supabase connectivity
    verify_connection()

    # 2. Create tables if missing (fallback; prefer `alembic upgrade head`)
    init_db()

    # 3. Confirm predictions table exists
    verify_predictions_table()

    logger.info("✅ Startup complete — all checks passed")
    logger.info("=" * 60)
    yield
    logger.info("🛑 Meme Detection API shutting down …")


# ── App instance ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Multimodal Meme Detection API",
    description=(
        "Phase 1 — mock inference pipeline for the Harmful Meme Detection system. "
        "All API contracts are stable for Phase 2 real-model swap."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ── CORS ───────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global request / response logging middleware ───────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log every incoming request and outgoing response with latency."""
    client_ip = request.client.host if request.client else "unknown"
    logger.info(
        "[HTTP] ▶  %s %s | client=%s",
        request.method,
        request.url.path,
        client_ip,
    )
    t_start = time.monotonic()
    try:
        response = await call_next(request)
        latency_ms = int((time.monotonic() - t_start) * 1000)
        logger.info(
            "[HTTP] ◀  %s %s | status=%d | latency=%dms",
            request.method,
            request.url.path,
            response.status_code,
            latency_ms,
        )
        return response
    except Exception as exc:
        latency_ms = int((time.monotonic() - t_start) * 1000)
        logger.error(
            "[HTTP] ✗  %s %s | UNHANDLED EXCEPTION after %dms — %s",
            request.method,
            request.url.path,
            latency_ms,
            str(exc),
            exc_info=True,
        )
        raise


# ── Global exception handler ───────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all handler: logs full traceback and returns structured JSON
    so errors surface in Swagger UI response body, not just the terminal.
    """
    tb = traceback.format_exc()
    logger.error(
        "[global_exception_handler] Unhandled exception on %s %s\n%s",
        request.method,
        request.url.path,
        tb,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": str(exc),
            "type": type(exc).__name__,
            "path": str(request.url.path),
            "detail": "An unexpected error occurred. Check backend logs for full traceback.",
        },
    )


# ── Static files ───────────────────────────────────────────────────────────────
_upload_dir = Path(settings.upload_dir)
_heatmap_dir = Path(settings.heatmap_dir)
_upload_dir.mkdir(parents=True, exist_ok=True)
_heatmap_dir.mkdir(parents=True, exist_ok=True)

app.mount("/static/uploads", StaticFiles(directory=str(_upload_dir)), name="uploads")
app.mount("/static/heatmaps", StaticFiles(directory=str(_heatmap_dir)), name="heatmaps")


# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(predict_router.router, prefix="/api/v1")
app.include_router(review_router.router, prefix="/api/v1")


# ── Health endpoint ────────────────────────────────────────────────────────────
@app.get(
    "/health",
    summary="Health check",
    tags=["System"],
    responses={200: {"description": "API is running"}},
)
def health_check():
    """Smoke-test endpoint — returns OK if the server is reachable."""
    logger.debug("[health_check] ping")
    return {"status": "ok", "environment": settings.environment}
