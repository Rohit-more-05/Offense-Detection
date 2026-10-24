import requests, os, sys

meme = r"d:\meme detection\meme input\long day.jpeg"
fname = os.path.basename(meme)
print(f"[TEST] Sending: {fname} ({os.path.getsize(meme)} bytes)")

try:
    with open(meme, "rb") as f:
        r = requests.post(
            "http://localhost:8000/api/v1/predict",
            files={"file": (fname, f, "image/jpeg")},
            timeout=90,
        )
    print(f"[TEST] HTTP Status: {r.status_code}")
    if r.status_code == 200:
        p = r.json()
        label = p["label"]
        conf = p["confidence"] * 100
        decision = p["moderation_decision"]
        ms = p["execution_time_ms"]
        print(f"[TEST] Label: {label} | Confidence: {conf:.1f}% | Decision: {decision} | Time: {ms}ms")
    else:
        print(f"[TEST] ERROR: {r.json()}")
except Exception as e:
    print(f"[TEST] EXCEPTION: {e}")
