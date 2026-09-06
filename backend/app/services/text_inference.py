"""
text_inference.py
=================
Real, deterministic text-only hate-speech classifier — LAZY LOAD edition.

CRITICAL ARCHITECTURE CHANGE (v2):
  The model is NO LONGER loaded at module import time.
  It is loaded LAZILY on the first call to run(), using a thread-safe
  double-checked locking pattern.

WHY THIS MATTERS FOR RENDER FREE TIER:
  - Eager loading (old): model loads BEFORE uvicorn binds port 10000
    → Render sees no open port → kills the process → OOM race condition
  - Lazy loading (new): uvicorn binds port immediately → /health responds
    → model loads on FIRST /predict call → Render sees healthy service

Model : am4nsolanki/autonlp-text-hateful-memes-36789092
Type  : BERT-based binary sequence classifier
        label 0 = "Safe"  |  label 1 = "Harmful"

Validation metrics (baseline — not production-grade):
  Accuracy ~76.7%  |  AUC ~78.9%  |  F1 ~65.3%
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Optional, Tuple

import torch
torch.set_num_threads(1)  # CRITICAL: Minimise memory overhead — single thread for CPU inference

from fastapi import HTTPException
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from app.logger import get_logger

# ── Constants ──────────────────────────────────────────────────────────────────
MODEL_ID  = "am4nsolanki/autonlp-text-hateful-memes-36789092"
MAX_LEN   = 128
LABEL_MAP = {0: "Safe", 1: "Harmful"}

logger = get_logger(__name__)

# ── Lazy singleton state ───────────────────────────────────────────────────────
_lock: threading.Lock = threading.Lock()
_tokenizer: Optional[AutoTokenizer] = None
_model: Optional[AutoModelForSequenceClassification] = None
_device: str = "cpu"
_model_loaded: bool = False
_load_failed: bool = False
_load_error: str = ""

# ── Telemetry call counter ─────────────────────────────────────────────────────
_call_counter: int = 0


# ══════════════════════════════════════════════════════════════════════════════
# Private telemetry helpers
# ══════════════════════════════════════════════════════════════════════════════

def _check_cache() -> bool:
    """Return True if HF model weights are already cached locally."""
    cache_root = Path(
        os.environ.get("TRANSFORMERS_CACHE",
                       Path.home() / ".cache" / "huggingface" / "hub")
    )
    slug = MODEL_ID.replace("/", "--")
    return (cache_root / f"models--{slug}").exists()


def _log_inference(
    *,
    call_id: int,
    text: str,
    label: str,
    confidence: float,
    elapsed_ms: int,
    logit_safe: float,
    logit_harmful: float,
    prob_safe: float,
    prob_harmful: float,
) -> None:
    logger.info(
        "[text_inference] [TELEMETRY:INFERENCE] "
        "call_id=%d | label=%r | confidence=%.6f | elapsed_ms=%d | "
        "input_chars=%d | "
        "logit_safe=%.4f | logit_harmful=%.4f | "
        "prob_safe=%.6f | prob_harmful=%.6f | "
        "text_snippet=%r",
        call_id,
        label,
        confidence,
        elapsed_ms,
        len(text),
        logit_safe,
        logit_harmful,
        prob_safe,
        prob_harmful,
        text[:100],
    )


# ══════════════════════════════════════════════════════════════════════════════
# Lazy model loader — thread-safe double-checked locking
# ══════════════════════════════════════════════════════════════════════════════

def _ensure_model_loaded() -> None:
    """
    Load tokenizer + model exactly once, on the first inference call.
    Uses double-checked locking for thread safety without blocking after first load.

    TELEMETRY STAGES:
      [LAZY_LOAD:CHECK]   — called every inference, confirms model state
      [LAZY_LOAD:ACQUIRE] — thread acquiring the lock
      [LAZY_LOAD:CACHE]   — reports cache hit/miss before download
      [LAZY_LOAD:LOADING] — model weights being loaded into RAM
      [LAZY_LOAD:COMPLETE]— load finished, inference can proceed
      [LAZY_LOAD:FAILED]  — load failed, all future calls will fast-fail
    """
    global _tokenizer, _model, _device, _model_loaded, _load_failed, _load_error

    # Fast path — already loaded
    if _model_loaded:
        logger.debug(
            "[text_inference] [TELEMETRY:LAZY_LOAD:CHECK] status=already_loaded | "
            "device=%s | skipping lock acquisition", _device
        )
        return

    # Fast path — previous load attempt failed, do not retry endlessly
    if _load_failed:
        logger.error(
            "[text_inference] [TELEMETRY:LAZY_LOAD:CHECK] status=previously_failed | "
            "error=%r | raising immediately", _load_error
        )
        raise HTTPException(
            status_code=503,
            detail=f"ML model failed to load at startup: {_load_error}. "
                   "Check backend logs for full traceback."
        )

    logger.info(
        "[text_inference] [TELEMETRY:LAZY_LOAD:ACQUIRE] "
        "Acquiring model load lock — thread will block until load completes..."
    )

    with _lock:
        # Second check inside lock (another thread may have loaded while we waited)
        if _model_loaded:
            logger.debug(
                "[text_inference] [TELEMETRY:LAZY_LOAD:ACQUIRE] "
                "Lock acquired but model already loaded by another thread — releasing"
            )
            return

        if _load_failed:
            raise HTTPException(
                status_code=503,
                detail=f"ML model failed to load: {_load_error}"
            )

        # ── Actual model load ──────────────────────────────────────────────
        cache_hit = _check_cache()
        logger.info(
            "[text_inference] [TELEMETRY:LAZY_LOAD:CACHE] "
            "cache_hit=%s | model_id=%r | "
            "%s",
            cache_hit,
            MODEL_ID,
            "Loading from local disk cache — no download required." if cache_hit
            else "CACHE MISS — downloading ~400MB weights from HuggingFace Hub (first run only)..."
        )

        t0 = time.monotonic()
        logger.info(
            "[text_inference] [TELEMETRY:LAZY_LOAD:LOADING] "
            "Starting tokenizer load... model_id=%r", MODEL_ID
        )

        try:
            tokenizer_t0 = time.monotonic()
            _tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
            logger.info(
                "[text_inference] [TELEMETRY:LAZY_LOAD:LOADING] "
                "Tokenizer loaded in %dms", int((time.monotonic() - tokenizer_t0) * 1000)
            )

            model_t0 = time.monotonic()
            logger.info(
                "[text_inference] [TELEMETRY:LAZY_LOAD:LOADING] "
                "Starting model weights load... (this is the heavy ~400MB step)"
            )
            _model = AutoModelForSequenceClassification.from_pretrained(
                MODEL_ID,
                low_cpu_mem_usage=True,   # Load weights shard-by-shard — avoids peak RAM doubling
            )
            logger.info(
                "[text_inference] [TELEMETRY:LAZY_LOAD:LOADING] "
                "Model weights loaded in %dms", int((time.monotonic() - model_t0) * 1000)
            )

            # CRITICAL — disables dropout for deterministic inference
            _model.eval()

            _device = "cuda" if torch.cuda.is_available() else "cpu"
            _model.to(_device)

            elapsed_ms = int((time.monotonic() - t0) * 1000)
            _model_loaded = True

            logger.info(
                "[text_inference] [TELEMETRY:LAZY_LOAD:COMPLETE] "
                "status=SUCCESS | elapsed_ms=%d | device=%s | "
                "model_id=%r | eval_mode=True | deterministic=True | "
                "Model loaded and set to eval mode — deterministic inference enabled",
                elapsed_ms, _device, MODEL_ID
            )

        except Exception as exc:
            _load_failed = True
            _load_error = str(exc)
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            logger.error(
                "[text_inference] [TELEMETRY:LAZY_LOAD:FAILED] "
                "status=FAILED | elapsed_ms=%d | model_id=%r | error=%r",
                elapsed_ms, MODEL_ID, str(exc),
                exc_info=True
            )
            raise HTTPException(
                status_code=503,
                detail=f"ML model failed to load: {exc}"
            ) from exc


# Log that the module was imported (but NOT that the model was loaded)
logger.info(
    "[text_inference] [TELEMETRY:MODULE_IMPORT] "
    "text_inference module imported | model_id=%r | "
    "load_strategy=LAZY (model loads on first /predict call, NOT at import) | "
    "port_binding_safe=True",
    MODEL_ID
)


# ══════════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════════

def run(text: str) -> Tuple[str, float]:
    """
    Classify a meme caption with the BERT hate-speech model.

    Parameters
    ----------
    text : str  Caption / OCR text extracted from the meme.

    Returns
    -------
    (label, confidence) : Tuple[str, float]
        label      — "Harmful" | "Safe"
        confidence — softmax probability of the winning class ∈ [0.0, 1.0]

    Guarantees
    ----------
    - Lazy load: model is guaranteed to be loaded before inference runs.
    - Deterministic: identical input → identical output (eval + no_grad).
    - Same return-type as the retired mock_inference.run() — router unchanged.
    - On failure: logs full traceback and raises HTTPException(500 or 503).
    """
    global _call_counter
    _call_counter += 1
    call_id = _call_counter
    t_start = time.monotonic()

    logger.info(
        "[text_inference] call_id=%d | START | input_chars=%d | snippet=%r",
        call_id, len(text), text[:80],
    )

    # ── Ensure model is loaded (lazy, thread-safe) ─────────────────────────
    logger.debug(
        "[text_inference] call_id=%d | [TELEMETRY:PRE_LOAD_CHECK] "
        "model_loaded=%s | load_failed=%s",
        call_id, _model_loaded, _load_failed
    )
    _ensure_model_loaded()
    logger.debug(
        "[text_inference] call_id=%d | [TELEMETRY:POST_LOAD_CHECK] "
        "model confirmed ready | proceeding to tokenize", call_id
    )

    try:
        # ── 1. Tokenise ────────────────────────────────────────────────────
        t_tok = time.monotonic()
        inputs = _tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            padding=True,
            max_length=MAX_LEN,
        )
        inputs = {k: v.to(_device) for k, v in inputs.items()}
        tok_ms = int((time.monotonic() - t_tok) * 1000)
        logger.debug(
            "[text_inference] call_id=%d | tokenise_ms=%d | token_count=%d",
            call_id, tok_ms, inputs["input_ids"].shape[-1],
        )

        # ── 2. Forward pass ────────────────────────────────────────────────
        t_fwd = time.monotonic()
        with torch.no_grad():
            outputs = _model(**inputs)
        fwd_ms = int((time.monotonic() - t_fwd) * 1000)
        logger.debug(
            "[text_inference] call_id=%d | forward_pass_ms=%d", call_id, fwd_ms
        )

        # ── 3. Softmax → probabilities ─────────────────────────────────────
        logits = outputs.logits
        probs  = torch.softmax(logits, dim=-1).squeeze()

        pred_idx   = int(torch.argmax(probs).item())
        confidence = round(float(probs[pred_idx].item()), 6)
        label      = LABEL_MAP[pred_idx]

        elapsed_ms = int((time.monotonic() - t_start) * 1000)

        # ── 4. Heavy structured telemetry ──────────────────────────────────
        _log_inference(
            call_id=call_id,
            text=text,
            label=label,
            confidence=confidence,
            elapsed_ms=elapsed_ms,
            logit_safe=float(logits[0][0].item()),
            logit_harmful=float(logits[0][1].item()),
            prob_safe=float(probs[0].item()),
            prob_harmful=float(probs[1].item()),
        )

        logger.info(
            "[text_inference] call_id=%d | SUCCESS | label=%r | confidence=%.6f | "
            "total_ms=%d (tok=%d fwd=%d)",
            call_id, label, confidence, elapsed_ms, tok_ms, fwd_ms,
        )

        return label, confidence

    except HTTPException:
        raise
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - t_start) * 1000)
        logger.error(
            "[text_inference] [TELEMETRY:INFERENCE] call_id=%d | FAILED | "
            "elapsed_ms=%d | reason: %s",
            call_id, elapsed_ms, str(exc), exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"text_inference failed: {exc}",
        ) from exc
