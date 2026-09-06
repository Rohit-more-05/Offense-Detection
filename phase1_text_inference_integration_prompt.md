# Phase 1 Addendum — Replace Mock Inference with Real Text-Only Model

## Objective

Replace the random-output `mock_inference.py` with a real, pretrained, text-only hateful-content classifier so the `/predict` route returns genuine, deterministic confidence scores instead of random numbers. This stays scoped to **Phase 1** — image pixels are NOT analyzed yet, only OCR-extracted or manually-provided text. No API keys, no external billing — the model runs 100% locally after a one-time automatic download.

## Model to Use

- Hugging Face model ID: `am4nsolanki/autonlp-text-hateful-memes-36789092`
- Type: BERT-based binary sequence classifier (label 0 = not-hateful, label 1 = hateful), trained via AutoNLP on the Facebook Hateful Memes text data.
- Reported validation metrics: ~76.7% accuracy, ~78.9% AUC, ~65.3% F1. Note in code comments that this is a lightweight baseline, not production-grade — false negatives are expected on subtle/coded hate speech.
- No API token required. `transformers.AutoModelForSequenceClassification.from_pretrained(...)` downloads and caches the weights locally on first run (cached under `~/.cache/huggingface`, reused on every subsequent app start — zero cost, zero external calls after that).

## Implementation Steps

1. Add to `backend/requirements.txt` if not already pinned: `transformers==4.44.2`, `torch==2.4.1` (or latest compatible pinned versions already in use).

2. Create `backend/app/services/text_inference.py`:
   - At module load time (not per-request), load the tokenizer and model once into module-level singletons:
     ```python
     from transformers import AutoTokenizer, AutoModelForSequenceClassification
     import torch

     MODEL_ID = "am4nsolanki/autonlp-text-hateful-memes-36789092"
     tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
     model = AutoModelForSequenceClassification.from_pretrained(MODEL_ID)
     model.eval()  # CRITICAL: disables dropout so identical input always returns identical output
     ```
   - Log at startup: `"[text_inference] Model loaded and set to eval mode — deterministic inference enabled"`.
   - Write a `run(text: str) -> tuple[str, float]` function that:
     - Logs the input text (truncated for readability) on entry.
     - Tokenizes with truncation/padding (`max_length=128` is enough for meme captions).
     - Runs inference inside `with torch.no_grad():` (mandatory — prevents gradient tracking and unnecessary memory use).
     - Applies `torch.softmax` on the output logits to get a proper 0–1 confidence.
     - Maps label index 1 → `"Harmful"`, label index 0 → `"Safe"`, returns `(label, confidence)` in the exact same tuple shape `mock_inference.run()` used, so the router's calling code does not need to change signature.
     - Logs the final label + confidence before returning.
     - Wrap in try/except; on failure, log full traceback and raise `HTTPException(status_code=500, detail="text_inference failed: <reason>")`.

3. In `backend/app/routers/predict.py`:
   - Change the import from `from app.services import decision_router, mock_inference` to `from app.services import decision_router, text_inference`.
   - Change the call from `mock_inference.run(image_path_str, manual_text_override)` to `text_inference.run(extracted_or_manual_text)`.
   - If OCR extraction (EasyOCR) is not yet wired in, use `manual_text_override` as the required text input for now, and log a clear warning: `"[predict] No OCR yet — using manual_text_override as input text"`. Do not silently fall back to empty string.
   - Keep `decision_router.py` thresholds (10%/90%) unchanged — they already expect a confidence float, no changes needed there.

4. Add a determinism regression test in `backend/tests/test_predict.py`:
   - Call `text_inference.run("some sample harmful text")` 10 times in a loop.
   - Assert all 10 confidence values are identical (or within 1e-6 floating point tolerance).
   - This test proves the same-image/same-text-different-confidence bug is fixed, and should be run before closing this task.

5. Update logs so the terminal clearly shows on first startup:
   - `"[text_inference] Downloading model weights (first run only)..."` if cache miss, or `"[text_inference] Loaded from local cache"` if already cached.
   - This confirms to the user that no repeated network/API calls happen on every request.

## Acceptance Criteria

- Submitting the same text twice returns the exact same label and confidence both times.
- No Hugging Face API token or billing is involved — `requirements.txt` only needs `transformers` + `torch`, nothing else.
- `mock_inference.py` can be deleted or left unused, but do not leave it wired into any active route.
- Swagger UI (`/docs`) `/predict` endpoint still returns the same response schema as before — only the values are now real and stable.
