import os
os.environ["PYTHONUTF8"] = "1"
import re
import string
import logging
import numpy as np
from PIL import Image

logger = logging.getLogger("app")

# Try to import tensorflow/keras
try:
    import tensorflow as tf
    from tensorflow.keras.models import load_model
    from tensorflow.keras.preprocessing.sequence import pad_sequences
    TF_AVAILABLE = True
except ImportError:
    logger.warning("TensorFlow is not installed. Model inference will fail.")
    TF_AVAILABLE = False

# Global model instance
MODEL = None

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "ml_assets", "baseline_best_model.keras")

# Mock vocabulary based on the sample provided.
# In a real scenario, this would be loaded from a vocab.json or embedded in the model.
VOCAB = {'': 0, '[UNK]': 1, 'the': 2, 'you': 3, 'a': 4, 'to': 5, 'i': 6, 'and': 7, 'when': 8, 'is': 9}
VOCAB_SIZE = 9139
MAX_SEQ_LENGTH = 64

def load_global_model():
    """
    Loads the Keras model globally into memory on backend startup
    to prevent cold-start latency.
    """
    global MODEL
    if not TF_AVAILABLE:
        logger.error("Cannot load model without TensorFlow.")
        return

    if MODEL is None:
        try:
            logger.info(f"Loading model from {MODEL_PATH}")
            if os.path.exists(MODEL_PATH):
                import builtins
                _original_open = builtins.open
                def _utf8_open(*args, **kwargs):
                    mode = 'r'
                    if 'mode' in kwargs:
                        mode = kwargs['mode']
                    elif len(args) > 1:
                        mode = args[1]
                        
                    is_binary = isinstance(mode, str) and 'b' in mode
                    
                    if is_binary:
                        kwargs.pop('encoding', None)
                    else:
                        if 'encoding' not in kwargs:
                            kwargs['encoding'] = 'utf-8'
                            
                    return _original_open(*args, **kwargs)
                
                builtins.open = _utf8_open
                try:
                    MODEL = load_model(MODEL_PATH)
                finally:
                    builtins.open = _original_open
                    
                logger.info("Model loaded successfully.")
            else:
                logger.error(f"Model file not found at {MODEL_PATH}")
        except Exception as e:
            logger.error(f"Failed to load model: {e}", exc_info=True)

def preprocess_image(image_path: str) -> np.ndarray:
    """
    Read/decode PNG/JPEG, resize strictly to 224x224, cast to float32,
    standardizing pixel range to [0, 255] with a shape of (224, 224, 3).
    """
    try:
        img = Image.open(image_path).convert('RGB')
        img = img.resize((224, 224))
        # Cast to float32
        img_array = np.array(img, dtype=np.float32)
        # Ensure it's in [0, 255] range. PIL already loads it in [0, 255], so we just return it.
        # If standardizing means something else, like normalization, it didn't specify division by 255.
        return img_array
    except Exception as e:
        logger.error(f"Error preprocessing image: {e}")
        raise

def preprocess_text(text: str) -> np.ndarray:
    """
    Accept string input, convert to lowercase, strip punctuation,
    tokenize using the mapped vocabulary, and pad/truncate to exactly 64 tokens.
    """
    # Lowercase
    text = text.lower()
    # Strip punctuation
    text = text.translate(str.maketrans('', '', string.punctuation))
    
    # Tokenize using the mapped vocabulary
    tokens = []
    for word in text.split():
        if word in VOCAB:
            tokens.append(VOCAB[word])
        else:
            # Simple hash fallback since we don't have the full vocab
            # to map to a valid integer < 9139, ensuring 1 (UNK) is a fallback
            tokens.append(VOCAB['[UNK]'])
    
    # Pad/truncate to exactly 64 tokens
    # pad_sequences expects a list of sequences, so we wrap in a list
    padded = pad_sequences([tokens], maxlen=MAX_SEQ_LENGTH, padding='post', truncating='post')
    return padded[0]

def predict(image_path: str, text: str) -> float:
    """
    Run the multimodal inference model.
    Returns harmful_probability (float range 0.0 to 1.0).
    """
    if MODEL is None:
        logger.warning("[TELEMETRY:MODEL_LOAD] Model was not loaded on startup. Attempting lazy load now...")
        try:
            load_global_model()
        except Exception as lazy_exc:
            logger.error(f"[TELEMETRY:MODEL_LOAD] Exception during lazy load: {str(lazy_exc)}")
        if MODEL is None:
            error_msg = "Model lazy load failed completely. Cannot perform prediction."
            logger.error(f"[TELEMETRY:MODEL_LOAD] {error_msg}")
            raise RuntimeError(error_msg)

    try:
        logger.info("[TELEMETRY:PREDICT] Starting preprocessing for image_path")
        img_tensor = preprocess_image(image_path)
        img_batch = np.expand_dims(img_tensor, axis=0) # shape (1, 224, 224, 3)
        logger.info("[TELEMETRY:PREDICT] Image preprocessing successful.")
        
        text_batch = tf.constant([text], dtype=tf.string) # shape (1,)
        logger.info("[TELEMETRY:PREDICT] Text vectorization preprocessing successful.")
        
        logger.info("[TELEMETRY:PREDICT] Executing Keras model prediction...")
        prediction = MODEL.predict({"image": img_batch, "text": text_batch})
        
        prob = float(prediction[0][0])
        logger.info(f"[TELEMETRY:PREDICT] Inference successful. Raw Probability = {prob}")
        return prob
    except Exception as e:
        logger.error(f"[TELEMETRY:PREDICT] Keras inference failed: {e}", exc_info=True)
        raise RuntimeError(f"Keras inference failed: {e}")
