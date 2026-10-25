"""Usage: python scripts/export_feedback.py --output ../output/feedback"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.database import SessionLocal
from services.feedback_export import export_feedback

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with SessionLocal() as db:
        summary = export_feedback(db, args.output)
    print(json.dumps(summary, indent=2))
