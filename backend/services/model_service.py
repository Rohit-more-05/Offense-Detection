"""Inference for the saved EfficientNetB0 + BiLSTM model.

The archive owns its vocabulary, text standardization and image rescaling.
Never substitute a guessed vocabulary or normalize images a second time.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)
MODEL_PATH = Path(__file__).resolve().parent.parent / "ml_assets/baseline_best_model.keras"
MODEL = None
MODEL_VERSION = None
_load_lock = threading.Lock()
_predict_lock = threading.Lock()


def load_global_model():
    global MODEL, MODEL_VERSION
    if MODEL is not None:
        return MODEL
    with _load_lock:
        if MODEL is not None:
            return MODEL
        import tensorflow as tf
        # Supply UTF-8 vocabulary through the public layer config, avoiding a
        # process-wide builtins.open monkey patch on Windows.
        with zipfile.ZipFile(MODEL_PATH) as archive:
            config = json.loads(archive.read("config.json"))
            for layer in config["config"]["layers"]:
                if layer["class_name"] == "TextVectorization":
                    name = layer["config"]["name"]
                    vocabulary = archive.read(f"assets/layers/{name}/vocabulary.txt").decode("utf-8").splitlines()
                    layer["config"]["vocabulary"] = vocabulary
            config["compile_config"] = None
        model = tf.keras.models.model_from_json(json.dumps(config))
        model.load_weights(MODEL_PATH)
        inputs = {tensor.name.split(":")[0]: tensor for tensor in model.inputs}
        if set(inputs) != {"image", "text"} or tuple(inputs["image"].shape[1:]) != (224, 224, 3):
            raise RuntimeError("Unsupported model input contract")
        MODEL_VERSION = "baseline-" + hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()[:12]
        MODEL = model
        logger.info("Loaded %s with its saved vocabulary", MODEL_VERSION)
    return MODEL


def preprocess_image(image_path: str) -> np.ndarray:
    with Image.open(image_path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        # EfficientNet already includes Rescaling(1/255). Keep 0..255 inputs.
        image = image.resize((224, 224), Image.Resampling.BICUBIC)
        return np.asarray(image, dtype=np.float32)


def preprocess_text(text: str) -> np.ndarray:
    import tensorflow as tf
    model = load_global_model()
    return model.get_layer("text_vectorization")(tf.constant([text])).numpy()[0]


def text_diagnostics(text: str) -> dict:
    tokens = preprocess_text(text)
    non_padding = tokens[tokens != 0]
    return {
        "tokens_used": int(len(non_padding)),
        "unknown_token_fraction": float(np.mean(non_padding == 1)) if len(non_padding) else 0.0,
        "sequence_limit": int(len(tokens)),
        "text_may_be_truncated": len(text.split()) > len(tokens),
    }


def predict(image_path: str, text: str) -> float:
    import tensorflow as tf
    model = load_global_model()
    inputs = {
        "image": tf.convert_to_tensor(preprocess_image(image_path)[None, ...]),
        "text": tf.constant([text], dtype=tf.string),
    }
    with _predict_lock:
        output = np.asarray(model(inputs, training=False))
    if output.shape != (1, 1):
        raise RuntimeError("Unexpected model output shape")
    probability = float(output[0, 0])
    if not np.isfinite(probability) or not 0 <= probability <= 1:
        raise RuntimeError("Invalid model probability")
    return probability
