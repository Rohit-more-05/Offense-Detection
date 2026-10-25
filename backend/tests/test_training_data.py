import json

import pytest
from PIL import Image

from scripts.train_feedback import load_manifest


def test_training_requires_explicit_holdout_and_human_labels(tmp_path):
    image = tmp_path / "test.png"
    Image.new("RGB", (10, 10), "white").save(image)
    manifest = tmp_path / "data.jsonl"
    manifest.write_text(json.dumps({"image": image.name, "is_meme": True, "label": 0, "label_source": "human", "split": "unassigned", "text": "hello"}), encoding="utf-8")
    with pytest.raises(ValueError, match="explicit"):
        load_manifest(manifest)


def test_training_rejects_leakage_between_splits(tmp_path):
    image = tmp_path / "test.png"
    Image.new("RGB", (10, 10), "white").save(image)
    manifest = tmp_path / "data.jsonl"
    manifest.write_text("\n".join(json.dumps({"image": image.name, "is_meme": True, "label": 0,
        "label_source": "human", "split": split, "text": "hello"}) for split in ["train", "test"]), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate"):
        load_manifest(manifest)
