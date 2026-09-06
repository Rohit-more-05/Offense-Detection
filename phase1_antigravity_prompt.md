Act as a Lead Full-Stack ML Engineer.

### Context:
We are developing "Multimodal Intelligence System for Harmful Meme Detection" using:
- Frontend: React (Vite + Tailwind CSS + Lucide Icons)
- Backend: Python (FastAPI + Pydantic v2 + Uvicorn)
- Database/Persistence: SQLite (via SQLAlchemy 2.0 ORM) for review queue tracking and prediction logs
- Future stack (NOT this phase): PyTorch, Hugging Face Transformers (CLIP, BLIP-2), EasyOCR, Grad-CAM/attention-rollout explainability

Based on our architectural research and IEEE SRS specifications, we are executing **Phase 1: Full-Stack Foundation & Scaffolding**. In this phase we want a fully functioning, connected frontend and backend working end-to-end with a **mock inference pipeline** (deterministic/randomized fake predictions) before any heavy PyTorch/VLM models are loaded. Every API contract, database schema, and UI state defined here must remain stable when we swap the mock inference function for the real model in Phase 2 — do not design anything that will require breaking changes later.

---

### Objectives for Phase 1:

#### 1. System Architecture & Directory Structure
Provide a clean, production-grade monorepo layout separating `/backend` and `/frontend`, plus root-level config:

```
meme-moderation-system/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI app instance, CORS, static mounts, router includes
│   │   ├── config.py               # Settings via pydantic-settings (env vars, thresholds, paths)
│   │   ├── database.py             # SQLAlchemy engine, session, Base, init_db()
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── prediction.py       # SQLAlchemy ORM model: Prediction table
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── predict.py          # Pydantic request/response schemas for /predict
│   │   │   └── review.py           # Pydantic schemas for review queue + verdict
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── predict.py          # POST /api/v1/predict
│   │   │   └── review.py           # GET /api/v1/review-queue, POST /api/v1/review/{item_id}/verdict
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── mock_inference.py   # Fake model: random confidence + label generator
│   │   │   └── decision_router.py  # Confidence -> AUTO_APPROVE/AUTO_FLAG/HUMAN_REVIEW logic
│   │   └── storage/
│   │       ├── uploads/            # Saved meme images (gitkeep)
│   │       └── heatmaps/           # Stub heatmap images (gitkeep)
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_predict.py
│   │   └── test_review.py
│   ├── requirements.txt
│   ├── .env.example
│   └── meme_moderation.db          # created at runtime, gitignored
├── frontend/
│   ├── src/
│   │   ├── main.jsx
│   │   ├── App.jsx                 # Router setup (Dashboard + Moderator routes)
│   │   ├── index.css               # Tailwind directives
│   │   ├── api/
│   │   │   └── client.js           # Axios/fetch wrapper for backend calls
│   │   ├── components/
│   │   │   ├── UploadZone.jsx
│   │   │   ├── ResultsCard.jsx
│   │   │   ├── ConfidenceMeter.jsx
│   │   │   ├── ModerationBanner.jsx
│   │   │   ├── ExplainabilityPanel.jsx
│   │   │   ├── ReviewQueueTable.jsx
│   │   │   └── Navbar.jsx
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx       # "/" route
│   │   │   └── ModeratorQueue.jsx  # "/moderator" route
│   │   └── utils/
│   │       └── constants.js        # Label colors, status enums
│   ├── public/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   └── .env.example
├── .gitignore
└── README.md
```

#### 2. Backend Implementation (FastAPI + Python)

**Database schema** (`models/prediction.py`): a single `predictions` table with columns: `id` (UUID primary key), `filename` (str), `image_path` (str), `label` (str: "Harmful"/"Safe"), `confidence` (float), `moderation_decision` (str: "AUTO_APPROVE"/"AUTO_FLAG"/"HUMAN_REVIEW"), `heatmap_path` (str, nullable), `execution_time_ms` (int), `created_at` (datetime, default now), `reviewed` (bool, default False), `human_verdict` (str, nullable: "Harmful"/"Non-Harmful"), `reviewer_notes` (str, nullable), `reviewed_at` (datetime, nullable).

**Pydantic schemas** (exact field names, matching SRS):
- `PredictResponse`: `prediction_id: str`, `label: Literal["Harmful", "Safe"]`, `confidence: float` (0.0–1.0), `moderation_decision: Literal["AUTO_APPROVE", "AUTO_FLAG", "HUMAN_REVIEW"]`, `execution_time_ms: int`, `heatmap_url: str | None`.
- `ReviewQueueItem`: `prediction_id`, `filename`, `image_url`, `label`, `confidence`, `created_at`.
- `VerdictRequest`: `human_verdict: Literal["Harmful", "Non-Harmful"]`, `notes: str | None = None`.
- `VerdictResponse`: `prediction_id`, `status: str`, `updated_at: datetime`.

**Endpoints**:
- `POST /api/v1/predict` — Accepts multipart/form-data: `file: UploadFile` (the meme image) and optional `manual_text_override: str | None` (form field). Saves the uploaded file to `storage/uploads/` with a UUID-prefixed filename. Calls `mock_inference.run(image_path, manual_text_override)` which returns a randomized label + confidence (weight the random distribution so ~40% of results land in each auto-decision band and ~20% land in the 0.10–0.90 human-review band, to make the demo realistic). Calls `decision_router.route(confidence)` to get the moderation decision. If decision is `HUMAN_REVIEW`, persist the row to SQLite with `reviewed=False`; otherwise persist it too (for audit logging) but mark `reviewed=True` immediately since no human action is needed. Returns a `heatmap_url` pointing to a static stub image (e.g., `/static/heatmaps/placeholder.png`) regardless of label for now. Response time should be logged and returned as `execution_time_ms`.
- `GET /api/v1/review-queue` — Queries all `predictions` rows where `moderation_decision == "HUMAN_REVIEW"` and `reviewed == False`, ordered by `created_at` ascending. Returns a list of `ReviewQueueItem`.
- `POST /api/v1/review/{item_id}/verdict` — Looks up the prediction by `id`, sets `reviewed=True`, `human_verdict`, `reviewer_notes`, `reviewed_at=now()`. Returns 404 if the ID doesn't exist. Returns `VerdictResponse` on success.

**Decision router logic** (`services/decision_router.py`), exact thresholds from SRS FR6:
```
if confidence < 0.10: return "AUTO_APPROVE"
elif confidence > 0.90: return "AUTO_FLAG"
else: return "HUMAN_REVIEW"
```
Make these two thresholds configurable constants in `config.py` (not magic numbers), since Phase 2+ may need tuning after real model calibration.

**App wiring** (`main.py`): FastAPI app with CORS middleware allowing `http://localhost:5173` (Vite dev server origin), static file mounts for `/static/uploads` and `/static/heatmaps` serving from the `storage/` directory, router includes for `predict` and `review` under prefix `/api/v1`, and a startup event that calls `init_db()` to create tables if they don't exist. Include a root `GET /health` endpoint returning `{"status": "ok"}` for smoke testing.

**requirements.txt**: `fastapi`, `uvicorn[standard]`, `pydantic>=2.0`, `pydantic-settings`, `sqlalchemy>=2.0`, `python-multipart`, `pytest`, `httpx` (for testing).

#### 3. Frontend Implementation (React + Vite + Tailwind CSS)

**Main Dashboard** (`/`, `pages/Dashboard.jsx`):
- `UploadZone.jsx`: drag-and-drop zone (react-dropzone or native HTML5 drag events) accepting `.jpg/.png/.webp`, showing an immediate local image preview via `URL.createObjectURL`. On drop/select, enables a "Run Detection" button.
- On submit, calls `POST /api/v1/predict` via `api/client.js`, shows an animated loading state (skeleton pulse or spinner, minimum 800ms even if the mock responds instantly, so the loading UX feels real) simulating inference.
- `ResultsCard.jsx` displays after response: `label` tag with color coding (green pill = "Safe", red pill = "Harmful"), `ConfidenceMeter.jsx` as a horizontal gauge/progress bar showing exact percentage text, and `ModerationBanner.jsx` — a prominent full-width banner that switches color/icon/text based on `moderation_decision`: green with a checkmark icon for "Auto-Approved", red with an alert icon for "Auto-Flagged", amber/yellow with a clock icon for "Escalated for Human Review".
- `ExplainabilityPanel.jsx`: side-by-side two-column layout — left shows the originally uploaded image, right shows the `heatmap_url` image (the stub placeholder for now) with a caption "Attention Heatmap (Phase 2 preview)".

**Moderator Queue Tab** (`/moderator`, `pages/ModeratorQueue.jsx`):
- `ReviewQueueTable.jsx`: fetches `GET /api/v1/review-queue` on mount (and on a 10-second polling interval or manual refresh button), renders a table/grid with columns: thumbnail, filename, predicted label, confidence %, submitted time.
- Each row has two action buttons: "Mark as Safe" and "Mark as Harmful", each calling `POST /api/v1/review/{item_id}/verdict` with the corresponding `human_verdict`. On success, remove that row from the local table state immediately (optimistic update) and re-fetch to confirm.
- Empty state: friendly message "No items pending review" when the queue is empty.

**Navigation** (`components/Navbar.jsx`): simple top nav with links to "Dashboard" and "Moderator Queue" (React Router `Link`), using Lucide icons (e.g., `LayoutDashboard`, `ShieldAlert`).

**Styling**: Tailwind CSS utility classes throughout, no custom CSS files beyond `index.css`'s Tailwind directives. Use a clean neutral background (slate/gray) with accent colors: green-500 (safe), red-500 (harmful), amber-500 (review pending).

**API client** (`api/client.js`): centralize the base URL (`http://localhost:8000/api/v1`) as an env var (`VITE_API_BASE_URL`), export `predictMeme(formData)`, `getReviewQueue()`, `submitVerdict(itemId, verdict, notes)` functions using `fetch` or `axios`.

#### 4. Setup & Run Instructions

Provide exact, copy-pasteable commands for:
- Backend: create virtualenv, `pip install -r requirements.txt`, run `uvicorn app.main:app --reload --port 8000` from `/backend`.
- Frontend: `npm install`, `npm run dev` from `/frontend` (Vite defaults to port 5173).
- Confirm the SQLite DB file auto-creates on first backend startup (no manual migration step needed in Phase 1).
- A note on verifying the full loop: upload a meme on the dashboard, confirm a mock prediction renders, then manually trigger enough uploads to get at least one `HUMAN_REVIEW` result (since it's randomized), confirm it appears in `/moderator`, and resolve it there.

---

### Explicit Non-Goals for Phase 1 (do not implement yet):
- No real PyTorch/CLIP/BLIP-2/EasyOCR model loading — `mock_inference.py` must be pure Python random logic, zero ML dependencies.
- No Docker, no Postgres, no Redis — SQLite and local dev servers only.
- No auth/user roles — single-user local demo only.
- No real Grad-CAM/attention-rollout heatmap generation — a static placeholder image is sufficient.

Please provide complete, runnable code files for Phase 1 (no omitted placeholders in core logic — the mock inference randomization, decision routing, database persistence, and all UI states listed above must be fully implemented) so our team can execute this immediately and validate the entire request/response/persistence loop before Phase 2 introduces the real ML pipeline.
