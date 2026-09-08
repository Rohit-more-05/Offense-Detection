"""
text_inference.py  (api-inference branch)
==========================================
HuggingFace Inference API edition.

ARCHITECTURAL CHANGE vs main branch:
  - REMOVED: PyTorch, transformers, local model weights (~600 MB)
  - ADDED:   Lightweight httpx POST to HuggingFace Inference API (~0 MB)

The same model is used:
  am4nsolanki/autonlp-text-hateful-memes-36789092

But instead of loading 400MB weights into Render's 512MB RAM container,
we simply send a 100-byte JSON payload to HuggingFace's cloud GPU servers
and receive the label + confidence back.

Memory usage on Render: < 100 MB (vs > 600 MB before)
Cold-start time:         < 2 s  (vs > 40 s before)
"""

from __future__ import annotations

import time
from typing import Tuple

import json
import urllib.request
import urllib.error
import socket

# ── Render IPv6 DNS Patch ──────────────────────────────────────────────────────
# Render's free tier occasionally fails to resolve hostnames if the HTTP library
# attempts an IPv6 (AF_INET6) lookup. This forces IPv4 (AF_INET) at the query level.
_original_getaddrinfo = socket.getaddrinfo

def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    # Force the query to ONLY ask for IPv4, preventing the AAAA DNS drop bug on Render
    return _original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

socket.getaddrinfo = _ipv4_getaddrinfo
# ───────────────────────────────────────────────────────────────────────────────

from app.config import get_settings
from app.logger import get_logger

logger = get_logger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
MODEL_ID  = "am4nsolanki/autonlp-text-hateful-memes-36789092"
HF_API_URL = f"https://api-inference.huggingface.co/models/{MODEL_ID}"
LABEL_MAP  = {"LABEL_0": "Safe", "LABEL_1": "Harmful",
              "safe": "Safe", "harmful": "Harmful",
              "Safe": "Safe", "Harmful": "Harmful"}

# Timeout: 30s covers model cold-start wake-up on HF free inference
REQUEST_TIMEOUT = 30.0

logger.info(
    "[text_inference] [TELEMETRY:MODULE_IMPORT] "
    "api-inference edition loaded | model_id=%r | "
    "inference_mode=HUGGINGFACE_API | memory_overhead=ZERO",
    MODEL_ID
)


# ══════════════════════════════════════════════════════════════════════════════
# Public API  (same signature as main branch — router unchanged)
# ══════════════════════════════════════════════════════════════════════════════

def run(text: str) -> Tuple[str, float]:
    """
    Classify a meme caption via the HuggingFace Inference API.

    Parameters
    ----------
    text : str  Caption / OCR text extracted from the meme.

    Returns
    -------
    (label, confidence) : Tuple[str, float]
        label      — "Harmful" | "Safe"
        confidence — softmax probability of the winning class ∈ [0.0, 1.0]

    Raises
    ------
    RuntimeError — on API failure, timeout, or unexpected response format.
    """
    settings = get_settings()
    api_key  = settings.huggingface_api_key

    t_start = time.monotonic()
    logger.info(
        "[text_inference] [TELEMETRY:API_CALL:START] "
        "Sending text to HuggingFace Inference API | "
        "model_id=%r | input_chars=%d | snippet=%r",
        MODEL_ID, len(text), text[:80]
    )

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        logger.debug("[text_inference] [TELEMETRY:API_CALL] Auth header attached.")
    else:
        logger.warning(
            "[text_inference] [TELEMETRY:API_CALL] "
            "No HUGGINGFACE_API_KEY found — sending unauthenticated request. "
            "Rate limits will apply. Set HUGGINGFACE_API_KEY in Render env vars."
        )

    payload = {"inputs": text}

    try:
        req = urllib.request.Request(
            HF_API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
                status_code = response.getcode()
                response_text = response.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            status_code = e.code
            response_text = e.read().decode("utf-8")
            
        elapsed_ms = int((time.monotonic() - t_start) * 1000)
        logger.info(
            "[text_inference] [TELEMETRY:API_CALL:RESPONSE] "
            "HTTP %d | elapsed_ms=%d",
            status_code, elapsed_ms
        )

        # ── Handle model cold-start (HF wakes sleeping models) ────────────────
        if status_code == 503:
            body = json.loads(response_text)
            if "loading" in str(body).lower() or "estimated_time" in body:
                wait_s = body.get("estimated_time", 20)
                logger.warning(
                    "[text_inference] [TELEMETRY:API_CALL] "
                    "Model is cold-starting on HuggingFace servers. "
                    "Estimated wake-up: %ss. Retrying once...", wait_s
                )
                time.sleep(min(wait_s, 25))  # Cap wait at 25s
                
                try:
                    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
                        status_code = response.getcode()
                        response_text = response.read().decode("utf-8")
                except urllib.error.HTTPError as e:
                    status_code = e.code
                    response_text = e.read().decode("utf-8")
                    
                elapsed_ms = int((time.monotonic() - t_start) * 1000)
                logger.info(
                    "[text_inference] [TELEMETRY:API_CALL:RETRY] "
                    "Retry HTTP %d | total_elapsed_ms=%d",
                    status_code, elapsed_ms
                )

        if status_code != 200:
            raise RuntimeError(
                f"HuggingFace API returned HTTP {status_code}: {response_text[:300]}"
            )

        # ── Parse response ────────────────────────────────────────────────────
        result = json.loads(response_text)
        logger.debug("[text_inference] [TELEMETRY:API_CALL] Raw response: %r", result)

        # Flatten one level of nesting if needed
        if isinstance(result, list) and isinstance(result[0], list):
            result = result[0]

        if not isinstance(result, list) or len(result) == 0:
            raise RuntimeError(f"Unexpected API response format: {result}")

        # Pick the highest-score label
        best = max(result, key=lambda x: x.get("score", 0))
        raw_label  = best.get("label", "")
        confidence = round(float(best.get("score", 0.0)), 6)

        label = LABEL_MAP.get(raw_label)
        if label is None:
            # Last-resort mapping: if label contains "1" → Harmful, else Safe
            label = "Harmful" if "1" in raw_label else "Safe"
            logger.warning(
                "[text_inference] [TELEMETRY:API_CALL] "
                "Unknown raw label %r — mapped to %r", raw_label, label
            )

        elapsed_ms = int((time.monotonic() - t_start) * 1000)
        logger.info(
            "[text_inference] [TELEMETRY:API_CALL:COMPLETE] "
            "status=SUCCESS | label=%r | confidence=%.6f | "
            "elapsed_ms=%d | model_id=%r",
            label, confidence, elapsed_ms, MODEL_ID
        )

        return label, confidence

    except (urllib.error.URLError, TimeoutError) as exc:
        elapsed_ms = int((time.monotonic() - t_start) * 1000)
        if isinstance(exc.reason, TimeoutError) or isinstance(exc, TimeoutError):
            logger.error(
                "[text_inference] [TELEMETRY:API_CALL:FAILED] "
                "TIMEOUT after %dms — HuggingFace API did not respond within %ss. "
                "Model may still be cold-starting.",
                elapsed_ms, REQUEST_TIMEOUT
            )
            raise RuntimeError(
                f"HuggingFace Inference API timed out after {REQUEST_TIMEOUT}s. "
                "The model may be cold-starting. Please retry in 30 seconds."
            ) from exc
        else:
            logger.error(
                "[text_inference] [TELEMETRY:API_CALL:FAILED] "
                "Network error after %dms — %s", elapsed_ms, str(exc.reason)
            )
            raise RuntimeError(
                f"Network error contacting HuggingFace API: {exc.reason}"
            ) from exc

    except RuntimeError:
        raise  # Already formatted above

    except Exception as exc:
        elapsed_ms = int((time.monotonic() - t_start) * 1000)
        logger.error(
            "[text_inference] [TELEMETRY:API_CALL:FAILED] "
            "Unexpected error after %dms — %s", elapsed_ms, str(exc), exc_info=True
        )
        raise RuntimeError(f"text_inference API call failed: {exc}") from exc
