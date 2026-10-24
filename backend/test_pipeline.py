"""
test_pipeline.py
================
Automated test harness targeting ONLY the restricted meme set in:
  d:/meme detection/meme input

Feeds each meme through the live backend API and prints full telemetry.
"""

import requests
import os
import glob
import sys
import json

API_URL = "http://localhost:8000/api/v1/predict"
MEME_DIR = r"d:\meme detection\meme input"
ALLOWED_EXT = ("*.jpeg", "*.jpg", "*.png", "*.webp")


def run_test_harness():
    print("\n" + "=" * 62)
    print("[TEST HARNESS] MemeGuard Restricted Corpus Validation")
    print(f"[TEST HARNESS] Target directory: {MEME_DIR}")
    print("=" * 62)

    memes = []
    for pattern in ALLOWED_EXT:
        memes.extend(glob.glob(os.path.join(MEME_DIR, pattern)))

    if not memes:
        print(f"[TEST HARNESS] ✗ No memes found in {MEME_DIR}! Aborting.")
        return

    print(f"[TEST HARNESS] Found {len(memes)} memes to test.\n")

    results = []
    success_count = 0

    for idx, meme in enumerate(memes, 1):
        fname = os.path.basename(meme)
        print(f"[TEST HARNESS] [{idx}/{len(memes)}] Injecting: {fname}")
        print(f"[TEST HARNESS]   File size: {os.path.getsize(meme)} bytes")

        try:
            content_type = "image/jpeg" if fname.lower().endswith((".jpg", ".jpeg")) else "image/png"
            with open(meme, "rb") as f:
                response = requests.post(
                    API_URL,
                    files={"file": (fname, f, content_type)},
                    timeout=60,
                )

            if response.status_code == 200:
                payload = response.json()
                success_count += 1
                results.append({"file": fname, "status": "SUCCESS", "payload": payload})
                print(f"[TEST HARNESS]   ✓ SUCCESS")
                print(f"[TEST HARNESS]   Label       : {payload.get('label', 'N/A')}")
                print(f"[TEST HARNESS]   Confidence  : {payload.get('confidence', 0) * 100:.2f}%")
                print(f"[TEST HARNESS]   Decision    : {payload.get('moderation_decision', 'N/A')}")
                print(f"[TEST HARNESS]   Time        : {payload.get('execution_time_ms', 'N/A')}ms")
            else:
                results.append({"file": fname, "status": "FAIL", "code": response.status_code, "body": response.text})
                print(f"[TEST HARNESS]   ✗ FAILED — HTTP {response.status_code}")
                try:
                    err = response.json()
                    print(f"[TEST HARNESS]   Error detail: {err.get('error_message', response.text)}")
                except Exception:
                    print(f"[TEST HARNESS]   Raw response: {response.text[:200]}")

        except requests.exceptions.ConnectionError:
            print(f"[TEST HARNESS]   ✗ CONNECTION ERROR — is the backend running on port 8000?")
            results.append({"file": fname, "status": "CONNECTION_ERROR"})
        except Exception as e:
            print(f"[TEST HARNESS]   ✗ EXCEPTION: {e}")
            results.append({"file": fname, "status": "EXCEPTION", "error": str(e)})

        print()

    # Final summary
    print("=" * 62)
    print(f"[TEST HARNESS] ══ FINAL SUMMARY ══")
    print(f"[TEST HARNESS]   Total Tested  : {len(memes)}")
    print(f"[TEST HARNESS]   ✓ Succeeded   : {success_count}")
    print(f"[TEST HARNESS]   ✗ Failed      : {len(memes) - success_count}")
    print("=" * 62)

    for r in results:
        status_icon = "✓" if r["status"] == "SUCCESS" else "✗"
        label = r.get("payload", {}).get("label", r.get("status", "N/A")) if r["status"] == "SUCCESS" else r["status"]
        conf = f"{r.get('payload', {}).get('confidence', 0) * 100:.1f}%" if r["status"] == "SUCCESS" else "—"
        print(f"  {status_icon}  {r['file']:<25} → {label:<10} {conf}")

    print("=" * 62 + "\n")


if __name__ == "__main__":
    run_test_harness()
