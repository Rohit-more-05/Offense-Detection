"""Fine-tune a candidate on reviewed data; never overwrite the deployed model.

First review feedback.jsonl and assign train/validation/test splits by meme
template/source. This command requires all three splits and leaves test unused
until final evaluation. Non-memes belong in a separate input-scope dataset.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def load_manifest(path):
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [r for r in rows if r.get("is_meme") is True and r.get("label") in (0, 1)]
    splits = {name: [] for name in ["train", "validation", "test"]}
    hashes = {}
    from PIL import Image, ImageOps
    for row in rows:
        if row.get("label_source") != "human" or row.get("split") not in splits:
            raise ValueError("Every meme must have a human label and an explicit train/validation/test split")
        image_path = (path.parent / row["image"]).resolve()
        if not image_path.is_relative_to(path.parent.resolve()):
            raise ValueError("Image must be inside the dataset directory")
        with Image.open(image_path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            digest = hashlib.sha256(str(image.size).encode() + image.tobytes()).hexdigest()
        if digest in hashes:
            raise ValueError("Duplicate image in dataset; remove duplicates before splitting/training")
        hashes[digest] = row["split"]
        if not row.get("text", "").strip():
            raise ValueError("Review the missing transcription before training")
        row["image_path"] = str(image_path)
        splits[row["split"]].append(row)
    for name, items in splits.items():
        if {r["label"] for r in items} != {0, 1}:
            raise ValueError(f"{name} must include both classes; collect more reviewed data")
    return splits


def train(manifest, output, epochs):
    from services import model_service
    import numpy as np
    import tensorflow as tf
    if output.resolve() == model_service.MODEL_PATH.resolve() or output.exists():
        raise ValueError("Choose a NEW candidate path; the deployed model is never overwritten")
    splits = load_manifest(manifest)
    tf.keras.utils.set_random_seed(42)
    model = model_service.load_global_model()
    # Keep the saved vocabulary and frozen vision backbone; train the existing
    # trainable layers using a small LR, with early stopping on validation loss.
    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=1e-5),
        loss="binary_crossentropy", metrics=[tf.keras.metrics.BinaryAccuracy(name="accuracy"),
        tf.keras.metrics.AUC(name="auroc"), tf.keras.metrics.Precision(name="precision"), tf.keras.metrics.Recall(name="recall")])
    def dataset(items, training=False):
        def generate():
            for row in items:
                yield {"image": model_service.preprocess_image(row["image_path"]), "text": row["text"]}, np.float32(row["label"])
        ds = tf.data.Dataset.from_generator(generate, output_signature=(
            {"image": tf.TensorSpec((224, 224, 3), tf.float32), "text": tf.TensorSpec((), tf.string)}, tf.TensorSpec((), tf.float32)))
        if training:
            ds = ds.shuffle(len(items), seed=42)
        return ds.batch(8).prefetch(1)
    history = model.fit(dataset(splits["train"], True), validation_data=dataset(splits["validation"]), epochs=epochs,
        callbacks=[tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=3, restore_best_weights=True)])
    metrics = model.evaluate(dataset(splits["test"]), return_dict=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    model.save(output)
    output.with_suffix(".metrics.json").write_text(json.dumps({"test": metrics,
        "split_sizes": {k: len(v) for k, v in splits.items()}, "history": history.history}, indent=2), encoding="utf-8")
    print("Candidate saved. Compare against the baseline on held-out data before deployment.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=15)
    args = parser.parse_args()
    train(args.manifest.resolve(), args.output, args.epochs)
