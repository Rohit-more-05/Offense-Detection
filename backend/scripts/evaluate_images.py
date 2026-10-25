"""Evaluate filename-labeled images through the actual HTTP upload route.

Names are used ONLY to score results. The server receives anonymous filenames.
Run: python scripts/evaluate_images.py --images "../meme test" --url http://localhost:8001
"""
import argparse
import json
import mimetypes
import re
from pathlib import Path

import httpx


def expected_label(name):
    match = re.match(r"^([01])(?:_|\s|-)", name)
    if match:
        return int(match[1])
    lower = name.lower()
    if "is harmful" in lower:
        return 1
    if "is safe" in lower or "is saefe" in lower:
        return 0
    return None


def evaluate(images, url, output):
    rows = []
    with httpx.Client(timeout=150) as client:
        health = client.get(url.rstrip("/") + "/health")
        health.raise_for_status()
        if health.json().get("service") != "memeguard":
            raise RuntimeError("Target URL is not a MemeGuard backend")
        for path in sorted(Path(images).rglob("*")):
            if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
                continue
            expected = expected_label(path.name)
            with path.open("rb") as source:
                response = client.post(url.rstrip("/") + "/api/v1/predict", files={
                    "file": ("evaluation" + path.suffix, source, mimetypes.guess_type(path)[0]),
                })
            row = {"file": str(path.relative_to(images)), "expected": expected, "http_status": response.status_code}
            if response.is_success:
                data = response.json()
                row.update({k: data.get(k) for k in [
                    "prediction_id", "label", "baseline_label", "harmful_probability", "content_type",
                    "decision_source", "ocr_source", "ocr_status", "moderation_decision", "persisted", "reason", "warnings",
                ]})
                prediction = {"Safe": 0, "Harmful": 1}.get(data["label"])
                row["correct_binary_label"] = prediction == expected if prediction is not None and expected is not None else None
            rows.append(row)
            print(json.dumps(row), flush=True)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    classified = [r for r in rows if r.get("correct_binary_label") is not None]
    print(json.dumps({"images": len(rows), "binary_classified": len(classified),
        "binary_correct": sum(r["correct_binary_label"] for r in classified),
        "out_of_scope": sum(r.get("label") == "Not a meme" for r in rows),
        "needs_review": sum(r.get("label") == "Needs review" for r in rows)}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--url", default="http://localhost:8001")
    parser.add_argument("--output", type=Path, default=Path("../output/evaluation/results.json"))
    args = parser.parse_args()
    evaluate(args.images.resolve(), args.url, args.output)
