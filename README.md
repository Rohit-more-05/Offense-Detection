# MemeGuard

React/Vite frontend, FastAPI backend, Supabase PostgreSQL, and a saved
EfficientNetB0 + bidirectional LSTM harmful-meme baseline.

## Run locally

Use the `api-inference-2` branch. The API uses **8001** to avoid the other local
project on 8000; the frontend uses 5173. `start_project.bat` starts both.

From `backend`:

```powershell
.venv\Scripts\python -m pip install -r requirements.txt
# Configure .env using .env.example, then apply migrations:
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m uvicorn main:app --port 8001
```

From `frontend`:

```powershell
npm install
# Set VITE_API_BASE_URL=http://localhost:8001/api/v1 in .env
npm run dev
```

The health endpoint identifies `service: memeguard`; the UI rejects a healthy
response from a different app. Database schema changes use Alembic, not startup
`create_all`. Supabase transaction pooling uses `prepare_threshold=None`.

## What actually makes a decision

1. Validate the decoded image, size and format. Filenames are metadata only.
2. Local RapidOCR detects and reads text; Tesseract is an installation fallback.
   RapidOCR includes its OCR weights and does not require a cloud key.
3. In the default hybrid mode, the existing Gemini connection checks input type
   and the joint image/text context. This is a separate, external model.
4. Keras receives RGB pixels at 224 x 224 in the 0..255 range and a string. Its
   saved TextVectorization layer supplies the real 9,139-entry vocabulary and
   64-token limit; EfficientNet performs its own rescaling.
5. Preserve the raw Keras harmful-class score. Never present it as confidence in
   a different contextual verdict. Disagreement, unreadable input, unknown scope
   and unavailable verification require human review. Recognized non-memes get
   `Not a meme`, which is not a statement that their content is harmless.
6. Store the result, provenance, OCR text and deduplicated image bytes in Supabase.
   Automatic decisions do not create human-reviewed training labels.

Set `CONTEXT_VERIFICATION_ENABLED=false` to run local OCR + Keras without sending
images to Gemini. This exposes the baseline's limitations; it is not a calibrated
general image safety classifier. In hybrid mode, cloud quota/service failures
produce `Needs review`, with the local output still available for inspection.

Both `/api/v1/predict` and `/api/v1/detect` use the same pipeline. There is no real
attention heatmap yet; the UI no longer shows a placeholder as an explanation.

## Correct predictions and prepare training data

Use the moderator page or the correction buttons below a result. `Mark Safe`,
`Mark Harmful` and `Mark Not a meme` save explicit human verdicts. A failed write
stays visible and is never reported as success. All unreviewed results, including
automatic decisions, can be corrected. The queue displays up to 200 items at once.

The `meme_images` table stores image bytes separately, deduplicated by SHA-256.
This keeps training images available after local upload files are lost. For a
larger public dataset, migrate image payloads to object storage.

```powershell
# Optionally recover legacy uploads still present on this machine:
.venv\Scripts\python scripts/backfill_images.py
.venv\Scripts\python scripts/backfill_images.py --apply

# Export image/text/user-label records:
.venv\Scripts\python scripts/export_feedback.py --output ../output/feedback
```

Export excludes unreviewed predictions and conflicting duplicate labels. Non-memes
have `label: null` and are kept separate from binary meme-classifier training.
Missing images/transcriptions are reported. Review annotations and near-duplicate
templates, then assign `train`, `validation`, `test` in the exported JSONL. Do not
reuse the diagnostic `meme test` folder as a claimed independent final test set
after training on its labels.

```powershell
.venv\Scripts\python scripts/train_feedback.py --manifest ../output/feedback/feedback.jsonl --output ../output/candidate.keras
```

Training refuses unassigned splits, duplicate images, missing classes or overwriting
an existing model. It saves a separate candidate and held-out metrics. Saving a
moderator verdict **does not automatically retrain or improve the deployed model**.

## Verification

```powershell
# In backend: isolated SQLite tests; no live API charges or Supabase writes
.venv\Scripts\python -m pytest -q

# Live labeled-image evaluation (writes uploads to the configured database)
.venv\Scripts\python scripts/evaluate_images.py --images "../meme test" --url http://localhost:8001

# In frontend
npm test
npm run build
npm run lint
```

The evaluator reads `0_` / `1_` and descriptive filenames only to calculate expected
labels, then uploads with anonymous filenames. It reports abstentions separately
from correct classifications. See `docs/inference-diagnosis.md` for the measured
results and remaining model limitations.

Implementation references: [EfficientNet input contract](https://keras.io/api/applications/efficientnet/efficientnet_models/),
[RapidOCR](https://rapidai.github.io/RapidOCRDocs/main/en/install_usage/rapidocr/install/),
[Supabase transaction pooling](https://supabase.com/kb/troubleshooting/disabling-prepared-statements-qL8lEL).
