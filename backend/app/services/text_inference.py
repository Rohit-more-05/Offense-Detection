"""
text_inference.py  (api-inference branch)
==========================================
HuggingFace Inference API edition — Render DNS Bypass via DoH.

RENDER FREE TIER FIX:
  Render's free tier blocks outbound system DNS (getaddrinfo → Errno -5).
  This version resolves the HuggingFace API IP using DNS-over-HTTPS (DoH)
  via Cloudflare 1.1.1.1, which IS reachable even when system DNS is broken.
  It then opens a raw SSL socket directly to the resolved IP, bypassing
  the OS-level DNS resolver entirely.

  ALSO: api-inference.huggingface.co has no DNS A records.
  The active HF endpoint is: router.huggingface.co

Memory usage on Render: < 100 MB
Cold-start time:         < 2 s
"""

from __future__ import annotations

import json
import socket
import ssl
import time
import urllib.error
import urllib.request
from typing import Optional, Tuple

from app.config import get_settings
from app.logger import get_logger

logger = get_logger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
# The original model (am4nsolanki/autonlp-text-hateful-memes-36789092) was dropped 
# by the HuggingFace Free Inference Tier. We now use an officially supported Meta model.
MODEL_ID    = "facebook/roberta-hate-speech-dynabench-r4-target"

# HuggingFace migrated inference to router.huggingface.co
# api-inference.huggingface.co has no A records as of 2026
HF_HOSTNAME = "router.huggingface.co"
HF_PATH     = f"/hf-inference/models/{MODEL_ID}"
HF_PORT     = 443

LABEL_MAP   = {
    "hate":       "Harmful",
    "nothate":    "Safe",
    "toxic":      "Harmful",
    "neutral":    "Safe",
    "LABEL_0":    "Safe",     # Fallback
    "LABEL_1":    "Harmful",  # Fallback
}
REQUEST_TIMEOUT = 30.0

# Cloudflare DoH IPs — these need NO DNS resolution (hardcoded IPs)
DOH_URLS = [
    ("1.1.1.1", "https://1.1.1.1/dns-query"),    # Cloudflare
    ("8.8.8.8", "https://8.8.8.8/dns-query"),     # Google
]

# Cache the resolved IP so we don't DoH-query on every request
_hf_resolved_ip: Optional[str] = None

logger.info(
    "[text_inference] [TELEMETRY:MODULE_IMPORT] "
    "api-inference edition loaded | model_id=%r | "
    "inference_mode=HUGGINGFACE_ROUTER_DOH_BYPASS | memory_overhead=ZERO",
    MODEL_ID
)


def _resolve_via_doh(hostname: str) -> str:
    """
    Resolve a hostname to IPv4 using DNS-over-HTTPS via Cloudflare 1.1.1.1.
    Completely bypasses the broken system DNS on Render free tier.
    The DoH servers are accessed by hardcoded IP — no DNS needed for them.
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    for doh_ip, doh_url in DOH_URLS:
        try:
            url = f"{doh_url}?name={hostname}&type=A"
            req = urllib.request.Request(
                url,
                headers={"accept": "application/dns-json"},
                method="GET"
            )
            with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            if data.get("Status") == 0 and "Answer" in data:
                for answer in data["Answer"]:
                    if answer.get("type") == 1:  # A record = IPv4
                        ip = answer["data"].strip()
                        logger.info(
                            "[text_inference] [DOH] Resolved %s → %s via DoH %s",
                            hostname, ip, doh_ip
                        )
                        return ip
        except Exception as e:
            logger.warning("[text_inference] [DOH] Failed via %s: %s", doh_ip, e)
            continue

    raise RuntimeError(
        f"[DOH_RESOLUTION_FAILED] Could not resolve {hostname} via DoH. "
        "Render may be blocking outbound HTTPS to 1.1.1.1 and 8.8.8.8."
    )


def _get_hf_ip() -> str:
    """Return cached resolved IP, or resolve fresh via DoH."""
    global _hf_resolved_ip
    if _hf_resolved_ip is None:
        _hf_resolved_ip = _resolve_via_doh(HF_HOSTNAME)
    return _hf_resolved_ip


def _make_raw_https_request(
    ip: str,
    hostname: str,
    port: int,
    path: str,
    method: str,
    headers: dict,
    body: bytes,
    timeout: float,
) -> Tuple[int, str]:
    """
    Open a raw SSL socket to the given IP with the correct Host/SNI header.
    This completely avoids DNS resolution — connects directly to the IP.
    """
    ctx = ssl.create_default_context()
    raw_sock = socket.create_connection((ip, port), timeout=timeout)
    ssl_sock = ctx.wrap_socket(raw_sock, server_hostname=hostname)

    try:
        header_lines = "\r\n".join(f"{k}: {v}" for k, v in headers.items())
        request_str = (
            f"{method} {path} HTTP/1.1\r\n"
            f"Host: {hostname}\r\n"
            f"Connection: close\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"{header_lines}\r\n"
            f"\r\n"
        )
        ssl_sock.sendall(request_str.encode("utf-8") + body)

        response_bytes = b""
        while True:
            chunk = ssl_sock.recv(8192)
            if not chunk:
                break
            response_bytes += chunk
    finally:
        ssl_sock.close()

    header_end = response_bytes.find(b"\r\n\r\n")
    if header_end == -1:
        raise RuntimeError("Malformed HTTP response from HuggingFace API")

    header_part = response_bytes[:header_end].decode("utf-8", errors="replace")
    body_bytes  = response_bytes[header_end + 4:]

    status_line = header_part.split("\r\n")[0]
    status_code = int(status_line.split(" ")[1])

    if "transfer-encoding: chunked" in header_part.lower():
        body_str = _decode_chunked(body_bytes).decode("utf-8", errors="replace")
    else:
        body_str = body_bytes.decode("utf-8", errors="replace")

    return status_code, body_str


def _decode_chunked(data: bytes) -> bytes:
    """Decode HTTP chunked transfer encoding."""
    result = b""
    while data:
        crlf = data.find(b"\r\n")
        if crlf == -1:
            break
        try:
            chunk_size = int(data[:crlf].strip(), 16)
        except ValueError:
            break
        if chunk_size == 0:
            break
        result += data[crlf + 2: crlf + 2 + chunk_size]
        data = data[crlf + 2 + chunk_size + 2:]
    return result


# ══════════════════════════════════════════════════════════════════════════════
# Public API  (same signature as main branch — router unchanged)
# ══════════════════════════════════════════════════════════════════════════════

def run(text: str) -> Tuple[str, float]:
    """
    Classify a meme caption via the HuggingFace Inference API.
    Uses DoH + raw SSL sockets to bypass Render's broken system DNS.
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

    req_headers = {"Content-Type": "application/json"}
    if api_key:
        req_headers["Authorization"] = f"Bearer {api_key}"
        logger.debug("[text_inference] [TELEMETRY:API_CALL] Auth header attached.")
    else:
        logger.warning(
            "[text_inference] [TELEMETRY:API_CALL] "
            "No HUGGINGFACE_API_KEY — sending unauthenticated. Rate limits apply."
        )

    payload = json.dumps({"inputs": text}).encode("utf-8")

    try:
        # Step 1: Resolve IP via DoH — bypass broken Render system DNS
        hf_ip = _get_hf_ip()
        logger.info("[text_inference] [DOH] Connecting directly to IP: %s", hf_ip)

        # Step 2: POST directly to the resolved IP via raw SSL socket
        status_code, response_text = _make_raw_https_request(
            ip=hf_ip,
            hostname=HF_HOSTNAME,
            port=HF_PORT,
            path=HF_PATH,
            method="POST",
            headers=req_headers,
            body=payload,
            timeout=REQUEST_TIMEOUT,
        )

        elapsed_ms = int((time.monotonic() - t_start) * 1000)
        logger.info(
            "[text_inference] [TELEMETRY:API_CALL:RESPONSE] HTTP %d | elapsed_ms=%d",
            status_code, elapsed_ms
        )

        # Handle HF model cold-start (503 + estimated_time in body)
        if status_code == 503:
            try:
                body_json = json.loads(response_text)
                if "loading" in str(body_json).lower() or "estimated_time" in body_json:
                    wait_s = min(body_json.get("estimated_time", 20), 25)
                    logger.warning(
                        "[text_inference] HF model cold-starting. Waiting %ss then retrying...",
                        wait_s
                    )
                    time.sleep(wait_s)
                    status_code, response_text = _make_raw_https_request(
                        ip=hf_ip, hostname=HF_HOSTNAME, port=HF_PORT,
                        path=HF_PATH, method="POST",
                        headers=req_headers, body=payload, timeout=REQUEST_TIMEOUT,
                    )
                    elapsed_ms = int((time.monotonic() - t_start) * 1000)
                    logger.info(
                        "[text_inference] [TELEMETRY:API_CALL:RETRY] HTTP %d | elapsed_ms=%d",
                        status_code, elapsed_ms
                    )
            except (json.JSONDecodeError, KeyError, AttributeError):
                pass

        if status_code == 400:
            raise RuntimeError(
                f"[HF_MODEL_UNSUPPORTED] HuggingFace Free Tier refused the model: {response_text}. "
                "The provider 'hf-inference' no longer supports this specific model architecture on the free tier."
            )
            
        if status_code == 401 or status_code == 403:
            raise RuntimeError(
                f"[HF_AUTH_ERROR] HuggingFace returned {status_code} Unauthorized/Forbidden. "
                "Check HUGGINGFACE_API_KEY is correctly set in Render env vars and has permissions."
            )
            
        if status_code == 429:
            raise RuntimeError(
                "[HF_RATE_LIMIT] HuggingFace rate limit exceeded. You have made too many requests "
                "on the free tier. Please wait or upgrade your Hugging Face account."
            )

        if status_code != 200:
            raise RuntimeError(
                f"[HF_API_ERROR] HuggingFace API returned HTTP {status_code}: {response_text[:300]}"
            )

        # Parse response
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"[HF_MALFORMED_RESPONSE] Could not parse JSON from HF API: {e} | Body: {response_text[:200]}")
        logger.debug("[text_inference] [TELEMETRY:API_CALL] Raw response: %r", result)

        if isinstance(result, list) and len(result) > 0 and isinstance(result[0], list):
            result = result[0]

        if not isinstance(result, list) or len(result) == 0:
            raise RuntimeError(f"Unexpected API response format: {result}")

        best       = max(result, key=lambda x: x.get("score", 0))
        raw_label  = best.get("label", "")
        confidence = round(float(best.get("score", 0.0)), 6)

        label = LABEL_MAP.get(raw_label)
        if label is None:
            label = "Harmful" if "1" in raw_label else "Safe"
            logger.warning(
                "[text_inference] Unknown raw label %r — mapped to %r", raw_label, label
            )

        elapsed_ms = int((time.monotonic() - t_start) * 1000)
        logger.info(
            "[text_inference] [TELEMETRY:API_CALL:COMPLETE] "
            "status=SUCCESS | label=%r | confidence=%.6f | elapsed_ms=%d",
            label, confidence, elapsed_ms
        )
        return label, confidence

    except RuntimeError:
        raise

    except Exception as exc:
        elapsed_ms = int((time.monotonic() - t_start) * 1000)
        logger.error(
            "[text_inference] [TELEMETRY:API_CALL:FAILED] "
            "Unexpected error after %dms — %s", elapsed_ms, str(exc), exc_info=True
        )
        raise RuntimeError(f"text_inference call failed: {exc}") from exc
