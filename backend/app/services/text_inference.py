"""
text_inference.py
=================
Real, deterministic text-only hate-speech classifier.

Model : am4nsolanki/autonlp-text-hateful-memes-36789092
Type  : BERT-based binary sequence classifier
        label 0 = "Safe"  |  label 1 = "Harmful"
Source: Trained via AutoNLP on the Facebook Hateful Memes dataset.

Validation metrics (baseline — not production-grade):
  Accuracy ~76.7%  |  AUC ~78.9%  |  F1 ~65.3%
  ⚠ False negatives are expected on subtle/coded hate speech.

Weights download once to ~/.cache/huggingface on first import.
Every subsequent restart reads from local disk — no API token, no billing.

Architecture decision — singleton load
──────────────────────────────────────
Model + tokenizer are loaded ONCE at module import as module-level singletons.
The ~400 MB load happens at startup, not per-request, keeping inference <100 ms on CPU.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Tuple

import torch
torch.set_num_threads(1) # CRITICAL: Reduce memory overhead on CPU for 512MB environments

from fastapi import HTTPException
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from app.logger import get_logger

# ── Constants ──────────────────────────────────────────────────────────────────
MODEL_ID  = "am4nsolanki/autonlp-text-hateful-memes-36789092"
MAX_LEN   = 128      # meme captions are short; 128 tokens is sufficient
LABEL_MAP = {0: "Safe", 1: "Harmful"}

logger = get_logger(__name__)

# ── Telemetry call counter (monotonically increments per inference call) ────────
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


def _log_load_start() -> None:
    if _check_cache():
        logger.info(
            "[text_inference] [TELEMETRY:MODEL_LOAD] status=cache_hit "
            "model_id=%r — loading from local disk, no download required", MODEL_ID
        )
    else:
        logger.warning(
            "[text_inference] [TELEMETRY:MODEL_LOAD] status=cache_miss "
            "model_id=%r — downloading weights (~400 MB, first run only)…", MODEL_ID
        )


def _log_load_done(elapsed_ms: int, device: str) -> None:
    logger.info(
        "[text_inference] [TELEMETRY:MODEL_LOAD] status=complete "
        "elapsed_ms=%d device=%s model_id=%r eval_mode=True deterministic=True",
        elapsed_ms, device, MODEL_ID,
    )


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
    """
    Structured per-call telemetry.
    Key=value pipe-delimited for easy parsing in Grafana Loki / any log shipper.
    """
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
        text[:100],   # truncate for log readability
    )


# ══════════════════════════════════════════════════════════════════════════════
# Singleton model load  — executed ONCE when the module is first imported
# ══════════════════════════════════════════════════════════════════════════════

logger.info(
    "[text_inference] [TELEMETRY:STARTUP] Initialising text inference module | model_id=%r",
    MODEL_ID,
)

_log_load_start()
_t0 = time.monotonic()

try:
    tokenizer: AutoTokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    model: AutoModelForSequenceClassification = (
        AutoModelForSequenceClassification.from_pretrained(MODEL_ID, low_cpu_mem_usage=True)
    )
    # CRITICAL — disables dropout so identical input always returns identical output.
    model.eval()

    _device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(_device)

    _log_load_done(int((time.monotonic() - _t0) * 1000), _device)
    logger.info(
        "[text_inference] Model loaded and set to eval mode — "
        "deterministic inference enabled | device=%s", _device
    )

except Exception as _exc:
    logger.error(
        "[text_inference] [TELEMETRY:MODEL_LOAD] status=FAILED | reason: %s",
        str(_exc), exc_info=True,
    )
    raise RuntimeError(
        f"[text_inference] Cannot load model '{MODEL_ID}': {_exc}"
    ) from _exc


# ══════════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════════

def run(text: str) -> Tuple[str, float]:
    """
    Classify a meme caption with the BERT hate-speech model.

    Parameters
    ----------
    text : str
        Caption / OCR text extracted from the meme.

    Returns
    -------
    (label, confidence) : Tuple[str, float]
        label      — "Harmful" | "Safe"
        confidence — softmax probability of the winning class ∈ [0.0, 1.0]

    Guarantees
    ----------
    - Deterministic: identical input → identical output every time (eval + no_grad).
    - Same return-type signature as the retired mock_inference.run(), so
      predict.py needs zero signature changes.
    - On failure: logs full traceback and raises HTTPException(500).
    """
    global _call_counter
    _call_counter += 1
    call_id = _call_counter
    t_start = time.monotonic()

    logger.info(
        "[text_inference] call_id=%d | START | input_chars=%d | snippet=%r",
        call_id, len(text), text[:80],
    )

    try:
        # ── 1. Tokenise ───────────────────────────────────────────────────────
        t_tok = time.monotonic()
        inputs = tokenizer(
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

        # ── 2. Forward pass ───────────────────────────────────────────────────
        # torch.no_grad() prevents gradient tracking → saves memory, ensures determinism.
        t_fwd = time.monotonic()
        with torch.no_grad():
            outputs = model(**inputs)
        fwd_ms = int((time.monotonic() - t_fwd) * 1000)
        logger.debug(
            "[text_inference] call_id=%d | forward_pass_ms=%d", call_id, fwd_ms
        )

        # ── 3. Softmax → probabilities ────────────────────────────────────────
        logits = outputs.logits          # shape: (1, 2)
        probs  = torch.softmax(logits, dim=-1).squeeze()   # shape: (2,)

        pred_idx   = int(torch.argmax(probs).item())
        confidence = round(float(probs[pred_idx].item()), 6)
        label      = LABEL_MAP[pred_idx]

        elapsed_ms = int((time.monotonic() - t_start) * 1000)

        # ── 4. Heavy structured telemetry ─────────────────────────────────────
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
