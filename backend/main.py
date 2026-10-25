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
import logging
import sys # Force reload

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from core.config import get_settings
from core.database import init_db, verify_connection, verify_predictions_table, close_db
from api import predict as predict_router
from api import detect as detect_router
from services.model_service import load_global_model
from api import review as review_router
from api import images as images_router

settings = get_settings()

# ── Dual-Stream Telemetry Logging Configuration ────────────────────────────────
class TelemetryFormatter(logging.Formatter):
    def format(self, record):
        timestamp = self.formatTime(record, self.datefmt)
        return f"[{timestamp}] [{record.levelname}] [{record.name}] -> {record.getMessage()}"

logger = logging.getLogger("app")
logger.setLevel(logging.DEBUG)

if logger.hasHandlers():
    logger.handlers.clear()

# Dual-Stream: stdout + file for DevSecOps traceability
stream_handler = logging.StreamHandler(sys.stdout)
if hasattr(stream_handler.stream, "reconfigure"):
    stream_handler.stream.reconfigure(encoding="utf-8")
stream_handler.setFormatter(TelemetryFormatter(datefmt="%Y-%m-%d %H:%M:%S"))
logger.addHandler(stream_handler)

try:
    file_handler = logging.FileHandler("../deploy.log", mode="a", encoding="utf-8")
    file_handler.setFormatter(TelemetryFormatter(datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(file_handler)
except Exception:
    pass  # deploy.log is optional

logger.info("[main] Telemetry engine initialised — dual-stream (stdout + deploy.log)")


# ── Lifespan ───────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: load model + verify DB. Shutdown: nothing extra needed."""
    logger.info("=" * 60)
    logger.info("[STARTUP] Meme Detection API starting up...")
    logger.info("   Environment : %s", settings.environment)
    logger.info("   Log level   : %s", settings.log_level)

    app.state.database_ready = False
    # 1. Load the Keras baseline model (non-fatal if it fails)
    try:
        load_global_model()
        logger.info("[STARTUP] Keras model loaded OK")
    except Exception as exc:
        logger.warning("[STARTUP] Model load failed (will retry on first request): %s", exc)

    # 2. Verify Supabase connectivity (non-fatal — allow offline testing)
    try:
        verify_connection()
        verify_predictions_table()
        app.state.database_ready = True
        logger.info("[STARTUP] Database connection OK")
    except Exception as exc:
        logger.warning("[STARTUP] Database unavailable (predictions will not be persisted): %s", exc)

    logger.info("[STARTUP] Startup complete — server is ready")
    logger.info("=" * 60)
    yield
    logger.info("[SHUTDOWN] Meme Detection API shutting down...")
    try:
        close_db()
    except Exception:
        pass
    logger.info("=" * 60)


# ── App instance ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Multimodal Meme Detection API",
    description=(
        "Local multimodal baseline with explicit OCR status, optional contextual "
        "verification and human moderation feedback."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ── CORS ───────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global request / response logging middleware ───────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log every incoming request and outgoing response with latency."""
    client_ip = request.client.host if request.client else "unknown"
    logger.info(f"[HTTP Request] -> Incoming {request.method} {request.url.path} from client IP {client_ip}")
    
    t_start = time.monotonic()
    try:
        logger.debug(f"[HTTP Middleware] -> Invoking next handler for {request.url.path}")
        response = await call_next(request)
        latency_ms = int((time.monotonic() - t_start) * 1000)
        
        logger.info(f"[HTTP Response] -> Resolved {request.method} {request.url.path} with status {response.status_code} in {latency_ms}ms")
        return response
    except Exception as exc:
        latency_ms = int((time.monotonic() - t_start) * 1000)
        logger.critical(f"[HTTP Middleware] -> Unhandled exception on {request.method} {request.url.path} after {latency_ms}ms: {exc}")
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
_upload_dir = settings.storage_path(settings.upload_dir)
_heatmap_dir = settings.storage_path(settings.heatmap_dir)
_upload_dir.mkdir(parents=True, exist_ok=True)
_heatmap_dir.mkdir(parents=True, exist_ok=True)

app.mount("/static/uploads", StaticFiles(directory=str(_upload_dir)), name="uploads")
app.mount("/static/heatmaps", StaticFiles(directory=str(_heatmap_dir)), name="heatmaps")


# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(predict_router.router, prefix="/api/v1")
app.include_router(detect_router.router, prefix="/api/v1")
app.include_router(review_router.router, prefix="/api/v1")
app.include_router(images_router.router, prefix="/api/v1")


# ── Health endpoint ────────────────────────────────────────────────────────────
@app.get(
    "/health",
    summary="Health check",
    tags=["System"],
    responses={200: {"description": "API is running"}},
)
def health_check():
    """Smoke-test endpoint — returns OK immediately."""
    import services.model_service as ms
    model_status = "loaded" if ms.MODEL is not None else "pending"
    logger.info(
        "[health_check] status=ok | environment=%s | model_status=%s",
        settings.environment, model_status
    )
    return {
        "service": "memeguard",
        "status": "ok",
        "environment": settings.environment,
        "model_status": model_status,
        "database_ready": getattr(app.state, "database_ready", False),
        "context_verification_enabled": settings.context_verification_enabled,
    }

# ── Dummy Login Endpoint (Telemetry Injection Check) ───────────────────────────
from pydantic import BaseModel

class LoginRequest(BaseModel):
    alive: bool = None

@app.post("/api/v1/users/login", tags=["Users"])
def dummy_login(payload: dict):
    """Evaluates user state and conditionally logs telemetry as per orchestrator requirements."""
    logger.info("Triggered /api/v1/users/login endpoint logic.")
    
    # Track the exact state evaluation of the user's alive status
    if "alive" not in payload:
        logger.warning("User 'alive' status key is MISSING from the payload.")
        return JSONResponse(status_code=400, content={"error": "Missing alive key"})
    
    is_alive = payload.get("alive")
    
    if is_alive is False:
        logger.error("User 'alive' status evaluated to FALSE. Login rejected.")
        return JSONResponse(status_code=403, content={"error": "User is not alive"})
        
    if is_alive is True:
        logger.info("User 'alive' status successfully verified as TRUE. Proceeding with authentication.")
        return {"status": "success", "message": "User authenticated"}
        
    logger.error(f"User 'alive' status provided an invalid state: {is_alive}")
    return JSONResponse(status_code=400, content={"error": "Invalid alive state"})
