import httpx
from app.logger import get_logger

logger = get_logger(__name__)

# Free OCR API (No auth required for 'helloworld' key up to low limits)
# If rate limits become an issue, we can swap the apikey.
OCR_API_URL = "https://api.ocr.space/parse/image"
API_KEY = "helloworld"

def extract_text(image_path: str) -> str:
    """
    Extract text from an image using the free OCR.space Cloud API.
    Gracefully degrades to an empty string on failure.
    """
    try:
        with open(image_path, "rb") as img_file:
            # We use a synchronous httpx client to keep the existing predict.py logic simple,
            # though an async client would be better in a high-throughput environment.
            # We already use httpx for text inference.
            with httpx.Client(timeout=15.0) as client:
                logger.info("[ocr_service] Sending image to Cloud OCR API (ocr.space)...")
                response = client.post(
                    OCR_API_URL,
                    data={"apikey": API_KEY, "language": "eng", "OCREngine": "2"},
                    files={"file": (image_path, img_file, "image/jpeg")}
                )
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("IsErroredOnProcessing"):
                    error_msg = data.get("ErrorMessage", ["Unknown error"])[0]
                    logger.error(f"[ocr_service] Cloud OCR returned error: {error_msg}")
                    return ""
                
                # Parse out the extracted text from the response
                parsed_results = data.get("ParsedResults", [])
                if not parsed_results:
                    logger.warning("[ocr_service] Cloud OCR returned no parsed results.")
                    return ""
                    
                raw_text = parsed_results[0].get("ParsedText", "")
                
                # Clean up output: strip whitespace and remove empty lines
                cleaned_text = " ".join(raw_text.split())
                
                logger.info(f"[ocr_service] Extracted {len(cleaned_text)} characters from image via Cloud OCR")
                return cleaned_text

    except Exception as exc:
        logger.error(f"[ocr_service] Cloud OCR Extraction FAILED — reason: {exc}", exc_info=True)
        # Fail gracefully: return empty string so the visual-only fallback path triggers
        return ""
