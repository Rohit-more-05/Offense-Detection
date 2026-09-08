import pytesseract
from PIL import Image

from app.logger import get_logger

logger = get_logger(__name__)

# Validate Tesseract installation at startup
try:
    version = pytesseract.get_tesseract_version()
    logger.info(f"[ocr_service] Tesseract version: {version}")
except Exception as exc:
    logger.critical(
        f"[ocr_service] FATAL: Tesseract OCR binary is missing or not installed properly: {exc}\n"
        "Please ensure 'tesseract-ocr' is installed on the system (e.g. via apt-get)."
    )
    raise RuntimeError("Tesseract OCR missing") from exc

def extract_text(image_path: str) -> str:
    """
    Extract text from an image using Tesseract OCR.
    Gracefully degrades to an empty string on failure.
    """
    try:
        with Image.open(image_path) as img:
            # Convert to RGB to ensure compatibility
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            raw_text = pytesseract.image_to_string(img)
            
            # Clean up output: strip whitespace and remove empty lines
            cleaned_text = " ".join(raw_text.split())
            
            logger.info(f"[ocr_service] Extracted {len(cleaned_text)} characters from image")
            return cleaned_text

    except Exception as exc:
        logger.error(f"[ocr_service] OCR Extraction FAILED — reason: {exc}", exc_info=True)
        # Fail gracefully: return empty string so the visual-only fallback path triggers
        return ""
