"""
services/ocr_service.py
========================
DUAL-STRATEGY OCR ENGINE
  Strategy 1: Local Tesseract via pytesseract (primary)
  Strategy 2: Gemini Vision API via google.genai (fallback)

The extracted text is printed directly to the live terminal with full telemetry.
"""

import os
import logging
import traceback
from pathlib import Path

# Load .env so GEMINI_API_KEY is available even without shell export
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=False)
except ImportError:
    pass  # python-dotenv not installed; rely on shell env

logger = logging.getLogger("app")

# ─── Strategy flags ───────────────────────────────────────────────────────────
_TESSERACT_AVAILABLE = False
_GEMINI_AVAILABLE = False
_genai_client = None

# ── Check Tesseract ────────────────────────────────────────────────────────────
try:
    import pytesseract
    from PIL import Image as _PILImage
    pytesseract.get_tesseract_version()
    _TESSERACT_AVAILABLE = True
    print("[OCR ENGINE] ✓ Tesseract detected — primary OCR strategy ACTIVE", flush=True)
    logger.info("[OCR ENGINE] Tesseract detected and available.")
except Exception as _tess_err:
    print(f"[OCR ENGINE] ✗ Tesseract NOT available: {_tess_err}", flush=True)
    print("[OCR ENGINE]   → Will use Gemini Vision API as fallback.", flush=True)
    logger.warning(f"[OCR ENGINE] Tesseract unavailable: {_tess_err}")

# ── Check Gemini ───────────────────────────────────────────────────────────────
try:
    from google import genai as _genai_module
    from google.genai import types as _genai_types
    _GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    if _GEMINI_API_KEY:
        _genai_client = _genai_module.Client(api_key=_GEMINI_API_KEY)
        _GEMINI_AVAILABLE = True
        print("[OCR ENGINE] ✓ Gemini Vision API (google.genai) configured — fallback ACTIVE", flush=True)
        logger.info("[OCR ENGINE] Gemini Vision API available as OCR fallback.")
    else:
        print("[OCR ENGINE] ✗ GEMINI_API_KEY not set in environment!", flush=True)
        logger.warning("[OCR ENGINE] GEMINI_API_KEY missing — Gemini fallback disabled.")
except Exception as _gem_import_err:
    print(f"[OCR ENGINE] ✗ google-genai not available: {_gem_import_err}", flush=True)
    logger.warning(f"[OCR ENGINE] google-genai import failed: {_gem_import_err}")


def _extract_via_tesseract(image_path: str) -> str:
    """Strategy 1 — Local Tesseract OCR."""
    print(f"\n[OCR:TESSERACT] ─────────────────────────────────────────────", flush=True)
    print(f"[OCR:TESSERACT] → Running local Tesseract on: {Path(image_path).name}", flush=True)
    logger.info(f"[OCR:TESSERACT] Attempting Tesseract OCR on {image_path}")

    from PIL import Image
    img = Image.open(image_path).convert("RGB")
    raw_text = pytesseract.image_to_string(img)
    cleaned = " ".join(raw_text.split())

    print(f"[OCR:TESSERACT] → Extracted {len(cleaned)} characters.", flush=True)
    print(f"[OCR:TESSERACT] → Text: \"{cleaned[:200]}\"", flush=True)
    print(f"[OCR:TESSERACT] ─────────────────────────────────────────────\n", flush=True)
    logger.info(f"[OCR:TESSERACT] Extracted {len(cleaned)} chars: '{cleaned[:100]}'")
    return cleaned


def _extract_via_gemini(image_path: str) -> str:
    """Strategy 2 — Gemini Vision API using google.genai SDK."""
    print(f"\n[OCR:GEMINI] ────────────────────────────────────────────────", flush=True)
    print(f"[OCR:GEMINI] → Fallback triggered. Sending to Gemini Vision API...", flush=True)
    print(f"[OCR:GEMINI] → File: {Path(image_path).name}", flush=True)
    logger.info(f"[OCR:GEMINI] Sending {image_path} to Gemini Vision for OCR.")

    try:
        import PIL.Image
        from google.genai import types

        img = PIL.Image.open(image_path).convert("RGB")

        # Convert PIL image to bytes for upload
        import io
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        image_bytes = buf.getvalue()

        prompt = (
            "You are an OCR engine. Extract ALL visible text from this meme image exactly as it appears. "
            "If there is no text, respond with exactly: NO_TEXT_FOUND. "
            "Do not describe the image. Only output the raw extracted text."
        )

        response = _genai_client.models.generate_content(
            model="gemini-3.8-flash",
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                prompt,
            ],
        )

        extracted = response.text.strip() if response.text else ""
        if extracted.upper() == "NO_TEXT_FOUND" or not extracted:
            extracted = ""

        cleaned = " ".join(extracted.split())

        print(f"[OCR:GEMINI] → SUCCESS. {len(cleaned)} characters extracted.", flush=True)
        print(f"[OCR:GEMINI] → Text: \"{cleaned[:200]}\"", flush=True)
        print(f"[OCR:GEMINI] ────────────────────────────────────────────────\n", flush=True)
        logger.info(f"[OCR:GEMINI] Extracted {len(cleaned)} chars: '{cleaned[:100]}'")
        return cleaned

    except Exception as gemini_exc:
        tb = traceback.format_exc()
        print(f"[OCR:GEMINI] ✗ GEMINI EXTRACTION FAILED!", flush=True)
        print(f"[OCR:GEMINI]   Error: {gemini_exc}", flush=True)
        logger.error(f"[OCR:GEMINI] Gemini Vision extraction failed: {gemini_exc}\n{tb}")
        return ""


def extract_text(image_path: str) -> str:
    """
    DUAL-STRATEGY OCR ENTRY POINT.
    1. Tesseract (primary)
    2. Gemini Vision API (fallback if Tesseract fails or returns empty)

    Terminal prints the exact extracted text before returning.
    """
    print(f"\n{'='*62}", flush=True)
    print(f"[OCR ENGINE] Dual-strategy extraction: {Path(image_path).name}", flush=True)
    print(f"[OCR ENGINE] Tesseract={_TESSERACT_AVAILABLE} | Gemini={_GEMINI_AVAILABLE}", flush=True)
    logger.info(f"[OCR ENGINE] Starting extraction for {image_path} | tesseract={_TESSERACT_AVAILABLE} | gemini={_GEMINI_AVAILABLE}")

    extracted_text = ""
    ocr_source = "NONE"

    # Strategy 1
    if _TESSERACT_AVAILABLE:
        try:
            extracted_text = _extract_via_tesseract(image_path)
            if extracted_text.strip():
                ocr_source = "TESSERACT"
            else:
                print(f"[OCR ENGINE] Tesseract returned empty → activating Gemini fallback.", flush=True)
                logger.warning("[OCR ENGINE] Tesseract returned empty. Falling back to Gemini.")
        except Exception as tess_exc:
            print(f"[OCR ENGINE] ✗ Tesseract error: {tess_exc} → activating Gemini fallback.", flush=True)
            logger.error(f"[OCR ENGINE] Tesseract failed: {tess_exc}")
            extracted_text = ""

    # Strategy 2
    if not extracted_text.strip() and _GEMINI_AVAILABLE:
        extracted_text = _extract_via_gemini(image_path)
        if extracted_text.strip():
            ocr_source = "GEMINI_VISION"

    # Final summary
    print(f"\n[OCR ENGINE] ══ FINAL RESULT ══════════════════════════════", flush=True)
    print(f"[OCR ENGINE]   Source : {ocr_source}", flush=True)
    print(f"[OCR ENGINE]   Length : {len(extracted_text)} chars", flush=True)
    print(f"[OCR ENGINE]   Text   : \"{extracted_text[:300] if extracted_text else '[NO TEXT FOUND — visual-only mode]'}\"", flush=True)
    print(f"{'='*62}\n", flush=True)

    logger.info(
        f"[OCR ENGINE] COMPLETE — source={ocr_source} | length={len(extracted_text)} | "
        f"preview='{extracted_text[:80]}'"
    )
    return extracted_text
