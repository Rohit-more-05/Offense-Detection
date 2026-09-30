"""
text_inference.py (baseline-model branch)
=========================================
Local inference using baseline Keras model.
"""

import time
import numpy as np
from typing import Tuple
from core.logger import get_logger

logger = get_logger(__name__)

# Global model cache
_model = None

def _get_model():
    global _model
    if _model is None:
        logger.info("[text_inference] Loading local Keras baseline model...")
        try:
            import os
            # Set TF_CPP_MIN_LOG_LEVEL to avoid TF warnings if needed
            os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
            import keras
            
            model_path = os.path.join(os.path.dirname(__file__), "..", "ml_assets", "baseline_best_model.keras")
            _model = keras.models.load_model(model_path)
            logger.info("[text_inference] Baseline model loaded successfully.")
        except Exception as e:
            logger.error("[text_inference] Error loading Keras model: %s", e)
            raise RuntimeError(f"Failed to load baseline Keras model: {e}")
    return _model

def run(text: str) -> Tuple[str, float]:
    """
    Classify a meme caption via the local Keras baseline model.
    Returns (label, confidence)
    """
    t_start = time.monotonic()
    logger.info(
        "[text_inference] [TELEMETRY:API_CALL:START] "
        "Sending text to local Keras model | "
        "input_chars=%d | snippet=%r",
        len(text), text[:80]
    )

    try:
        model = _get_model()
        
        # We assume the model accepts an array of strings if it has a TextVectorization layer,
        # or it handles preprocessing internally.
        # Ensure we pass it as a batch of 1
        predictions = model.predict([text], verbose=0)
        
        # Typically binary classification outputs shape (1, 1) with sigmoid activation
        # or (1, 2) with softmax. We handle both:
        preds_flat = predictions.flatten()
        
        if len(preds_flat) == 1:
            # Sigmoid output
            confidence = float(preds_flat[0])
            label = "Harmful" if confidence > 0.5 else "Safe"
            if label == "Safe":
                confidence = 1.0 - confidence # Make confidence > 0.5 for the winning class
        else:
            # Softmax output
            # Assuming index 0 = Safe, index 1 = Harmful (common convention)
            pred_class = int(np.argmax(preds_flat))
            confidence = float(preds_flat[pred_class])
            label = "Harmful" if pred_class == 1 else "Safe"

        elapsed_ms = int((time.monotonic() - t_start) * 1000)
        logger.info(
            "[text_inference] [TELEMETRY:API_CALL:COMPLETE] "
            "status=SUCCESS | label=%r | confidence=%.6f | elapsed_ms=%d",
            label, confidence, elapsed_ms
        )
        return label, confidence

    except Exception as exc:
        elapsed_ms = int((time.monotonic() - t_start) * 1000)
        logger.error(
            "[text_inference] [TELEMETRY:API_CALL:FAILED] "
            "Unexpected error after %dms — %s", elapsed_ms, str(exc), exc_info=True
        )
        raise RuntimeError(f"text_inference call failed: {exc}") from exc
