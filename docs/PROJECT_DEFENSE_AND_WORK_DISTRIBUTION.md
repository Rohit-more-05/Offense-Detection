# 🛡️ Multimodal Harmful Meme Detection System
## 🎓 Final Project Defense & Comprehensive Work Distribution Document
**Institution:** Department of Computer Engineering, M. H. Saboo Siddik College of Engineering, University of Mumbai  
**Academic Year:** 2026–2027  
**Project Guide / Mentor:** Prof. Er. Anand M. Bali  
**Head of Department:** Dr. Ashfaq Shaikh | **Principal:** Dr. Mohammed Shafi Pathan  
**Active Working Branch:** `api-inference-2`  

---

## 📋 Executive Overview & System Architecture

MemeGuard is an end-to-end, multimodal deep learning and automated content moderation system built to detect and flag offensive, harmful, and misogynistic memes. Because memes derive their meaning from the **interplay between visual and textual semantics** (where text alone or image alone may seem completely harmless), standard unimodal text or computer vision classifiers fail. 

Our system solves this using an **EfficientNetB0 (Visual) + BiLSTM (Textual) Fusion Architecture**, a **Dual-Strategy OCR & Scope Extraction Engine**, an **Asynchronous FastAPI Decision Core with Telemetry**, and a **Supabase PostgreSQL & React/Vite Human-in-the-Loop Review Dashboard**.

```
[ User Upload (Meme) ]
         │
         ├───► [ Pillar 2: OCR & Scope Engine (RapidOCR / Tesseract) ] ──► Extracted Text & Scope
         │                                                                       │
         ▼                                                                       ▼
[ Pillar 1: Multimodal Fusion Engine (EfficientNetB0 + BiLSTM) ] ◄───────────────┘
         │
         ▼ (Harmful Probability Score: 0.00 – 1.00)
[ Pillar 3: FastAPI Moderation Router & Telemetry Engine ]
         │
         ├── Score < 0.10  ──► AUTO_APPROVE (Safe)
         ├── 0.10 - 0.90   ──► HUMAN_REVIEW  (Queued for Moderator)
         └── Score >= 0.90 ──► AUTO_FLAG    (Harmful / Blocked)
         │
         ▼
[ Pillar 4: Supabase PostgreSQL Persistence & React/Vite Human Review Feedback ]
```

---

## 👥 Comprehensive Work Distribution (Team of 4)

---

### 👤 Member 1: Rohit Madhukar More (Roll No: 231239)
**Domain / Lead Role:** Full-Stack Architecture, Database Persistence & Human-in-the-Loop Feedback System

#### 1. Core Responsibilities & Modules Authored
* **Supabase Cloud PostgreSQL Architecture & ORM Design**: Designed and integrated the cloud database schema using SQLAlchemy 2.0 with connection pooling (`pool_pre_ping=True`, `pool_recycle=1800`, `max_overflow=0`) to prevent connection dropouts on pooled PostgreSQL instances.
* **Database Migration Pipeline (Alembic)**: Authored and executed progressive migrations:
  * `001_initial_schema.py`: Baseline predictions table structure.
  * `002_add_scan_history.py`: Dedicated table for audit logs and historical scans.
  * `003_inference_feedback.py`: Added inference provenance columns (`extracted_text`, `image_sha256`, `model_version`, `ocr_source`, `decision_source`, `analysis_metadata`).
  * `004_durable_storage.py`: Content-addressed durable storage (`meme_images`) deduplicated via SHA-256 hashes.
* **Frontend Application & Moderator Review Interface**:
  * Developed the React 19 + Vite dashboard featuring dynamic drag-and-drop meme upload, latency tracking, and confidence meters.
  * Built the **Human Review Queue** (`ReviewQueueTable.jsx`) enabling human moderators to inspect flagged/uncertain memes, view full extractions, and record ground-truth verdicts (`Mark Safe`, `Mark Harmful`, `Mark Not a Meme`) for continuous retraining.
* **Project Tooling & Runners**: Engineered [`start_project.bat`](file:///D:/meme%20detection/start_project.bat) with cross-platform UTF-8 encoding flags (`PYTHONUTF8=1`) to eliminate Windows console character-map crashes.

#### 2. Key Codebase Files Authored
* [`backend/core/database.py`](file:///D:/meme%20detection/backend/core/database.py) — SQLAlchemy session management, connection verification (`verify_connection`), and schema validation (`verify_predictions_table`).
* [`backend/models/prediction.py`](file:///D:/meme%20detection/backend/models/prediction.py) & [`backend/models/scan_history.py`](file:///D:/meme%20detection/backend/models/scan_history.py) — PostgreSQL ORM entities.
* [`backend/migrations/versions/`](file:///D:/meme%20detection/backend/migrations/versions/) — Alembic revision scripts 001–004.
* [`frontend/src/pages/Dashboard.jsx`](file:///D:/meme%20detection/frontend/src/pages/Dashboard.jsx) & [`frontend/src/components/ReviewQueueTable.jsx`](file:///D:/meme%20detection/frontend/src/components/ReviewQueueTable.jsx) — User interface and Moderator Queue.
* [`frontend/src/components/ResultsCard.jsx`](file:///D:/meme%20detection/frontend/src/components/ResultsCard.jsx) — Dynamic result visualization and human verdict feedback trigger.

#### 3. Defense / Viva Questions Rohit Can Answer
* **Q: Why use a human-in-the-loop review queue instead of 100% automated blocking?**
  * *Answer:* Memes contain complex cultural nuances, irony, and satire. For borderline confidence cases (e.g., probability between 0.10 and 0.90), automated blocking causes unacceptable false-positive rates on innocent memes. Routing uncertain scans to human moderators ensures safety while collecting high-value annotated feedback for retraining.
* **Q: How does the system handle database connection drops in production?**
  * *Answer:* In `core/database.py`, we implemented SQLAlchemy's `pool_pre_ping=True` which tests connections with a lightweight `SELECT 1` ping before handing them to requests, and `pool_recycle=1800` to refresh connections before cloud firewalls drop idle sockets.

---

### 👤 Member 2: Moinuddin Zaid Dhorajiwala (Roll No: 231238)
**Domain / Lead Role:** Multimodal Deep Learning & Keras Inference Engine Lead

#### 1. Core Responsibilities & Modules Authored
* **Multimodal Neural Network Architecture**: Researched and integrated the deep learning model combining a Convolutional Neural Network (CNN) and a Recurrent Neural Network (RNN):
  * **Visual Branch**: **EfficientNetB0** pretrained on ImageNet, extracting high-level spatial visual representations from `224×224×3` RGB images.
  * **Textual Branch**: **Bidirectional LSTM (BiLSTM)** processing contextual sequence representations from the extracted meme text up to a 64-token sequence limit.
  * **Fusion Layer**: Dense concatenation and classification head producing a calibrated sigmoid probability output $[0.0, 1.0]$.
* **Model Serialization & Saved Vocabulary Architecture**:
  * Implemented safe loading of `baseline_best_model.keras` without requiring untrusted pickle deserialization.
  * Authored the ZIP-archive vocabulary extractor in `model_service.py` to extract embedded tokens directly from `assets/layers/text_vectorization/vocabulary.txt` in UTF-8.
* **Thread-Safe Model Inference**:
  * Wrapped the forward pass in thread locks (`_predict_lock`) to guarantee thread safety during concurrent FastAPI async request processing.
  * Built diagnostic utilities (`text_diagnostics`) to detect token truncation and out-of-vocabulary (OOV) token ratios.

#### 2. Key Codebase Files Authored
* [`backend/services/model_service.py`](file:///D:/meme%20detection/backend/services/model_service.py) — `load_global_model()`, `preprocess_image()`, `preprocess_text()`, `text_diagnostics()`, and `predict()`.
* [`backend/ml_assets/baseline_best_model.keras`](file:///D:/meme%20detection/backend/ml_assets/baseline_best_model.keras) — Compiled model weights and vectorizer assets.
* [`backend/test_pipeline.py`](file:///D:/meme%20detection/backend/test_pipeline.py) & [`backend/test_single.py`](file:///D:/meme%20detection/backend/test_single.py) — Standalone pipeline testing and mathematical output validation.

#### 3. Defense / Viva Questions Moinuddin Can Answer
* **Q: Why choose EfficientNetB0 + BiLSTM over unimodal BERT or ResNet alone?**
  * *Answer:* Memes are intrinsically multimodal. An image of a benign animal paired with derogatory text is harmful, whereas the image alone is innocent. EfficientNetB0 offers state-of-the-art compound scaling for feature extraction with low parameter count (~5.3M), while BiLSTM captures bidirectional text dependencies without the severe RAM and latency overhead of heavy transformer models in production.
* **Q: How are images preprocessed before feeding into the neural network?**
  * *Answer:* Images are opened via PIL, EXIF orientation is normalized (`ImageOps.exif_transpose`), converted to 3-channel RGB, and resized to `224×224` using Bicubic resampling. Because EfficientNet incorporates an internal `Rescaling(1/255)` layer, raw pixel floats $[0, 255]$ are preserved to prevent double normalization.

---

### 👤 Member 3: Mohammed Aadil Kumshi (Roll No: 231232)
**Domain / Lead Role:** Vision-Language OCR Pipeline, Input Scope Analysis & Text Extraction

#### 1. Core Responsibilities & Modules Authored
* **Dual-Strategy OCR Engine**:
  * Designed and built the text extraction subsystem in `backend/services/ocr_service.py` with multi-tier fault tolerance.
  * **Primary Engine (`RapidOCR`)**: Integrated local OpenCV/ONNX-based text detection and recognition operating directly on BGR ndarrays, supporting angled and rotated text overlays.
  * **Secondary Fallback (`Tesseract OCR`)**: Configured path-independent local Tesseract integration with automatic binary discovery under `Program Files`.
* **Input Scope & Non-Meme Filtering**:
  * Identified the critical limitation where standard classifiers force a harmful/safe prediction on non-meme images (such as university ID cards, code screenshots, or official certificates).
  * Designed the **Scope Classifier** logic that validates whether an uploaded image conforms to a meme layout (caption + background) before classification, preventing embarrassing false alarms.
* **Text Normalization & Diagnostic Telemetry**:
  * Sanitized extracted text against null bytes, control characters, and Unicode encoding anomalies.
  * Added visual-only flag detection (`is_visual_only = True` when text length < 5 characters) to inform the downstream fusion network when text signals are absent.

#### 2. Key Codebase Files Authored
* [`backend/services/ocr_service.py`](file:///D:/meme%20detection/backend/services/ocr_service.py) — `analyze_image()`, `_rapid_ocr()`, `_local_ocr()`, and `VisionAssessment` data structures.
* [`backend/tests/test_text_inference.py`](file:///D:/meme%20detection/backend/tests/test_text_inference.py) — Unit test suite for OCR extraction reliability and edge-case handling.
* [`backend/docs/inference-diagnosis.md`](file:///D:/meme%20detection/docs/inference-diagnosis.md) — Detailed benchmark analysis comparing OCR engines and document scope detection across test datasets.

#### 3. Defense / Viva Questions Aadil Can Answer
* **Q: Why does OCR quality make or break a multimodal meme detection system?**
  * *Answer:* The BiLSTM branch relies completely on the transcribed tokens. If an OCR engine fails to detect text or returns garbled characters due to stylized meme fonts or noisy backgrounds, the textual branch receives zero or out-of-vocabulary tokens, forcing the model to guess purely on visual features. RapidOCR dramatically improved diagnostic accuracy over standard Tesseract (10/12 vs 7/12 correct classifications).
* **Q: How does the system handle images with zero text?**
  * *Answer:* When extracted text length is below 5 characters, the OCR service tags the input with `ocr_status: "no_text"`, flags the request as visual-only mode, and safely passes an empty string token representation to the model without crashing the pipeline.

---

### 👤 Member 4: Faisal Alvi (Roll No: 231202)
**Domain / Lead Role:** Backend Infrastructure, High-Throughput API Gateway & Moderation Router

#### 1. Core Responsibilities & Modules Authored
* **FastAPI Backend Core & Lifespan Architecture**:
  * Structured the modular backend into distinct `api/`, `core/`, `models/`, `schemas/`, and `services/` layers.
  * Implemented the asynchronous lifespan management protocol in `backend/main.py` that pre-loads model weights into RAM and verifies database connectivity on server boot.
* **Intelligent Moderation Decision Router**:
  * Authored [`backend/services/decision_router.py`](file:///D:/meme%20detection/backend/services/decision_router.py) implementing three-tier confidence routing:
    * **`AUTO_APPROVE`**: Confidence < 0.10 (High certainty of safe content).
    * **`HUMAN_REVIEW`**: 0.10 ≤ Confidence < 0.90 (Ambiguous content queued for human review).
    * **`AUTO_FLAG`**: Confidence ≥ 0.90 (High certainty of harmful content).
* **Dual-Stream Telemetry & DevSecOps Logging**:
  * Engineered a custom `TelemetryFormatter` providing simultaneous output to standard out (stdout) and persistent logs (`deploy.log`) with microsecond timestamping and client IP tracking.
  * Solved Windows CP1252 terminal crashes by reconfiguring the stdout stream handler to enforce standard UTF-8 encoding.
* **REST API Contracts & Review Endpoints**:
  * Developed endpoints in [`backend/api/predict.py`](file:///D:/meme%20detection/backend/api/predict.py) (file ingestion and classification), [`backend/api/detect.py`](file:///D:/meme%20detection/backend/api/detect.py), and [`backend/api/review.py`](file:///D:/meme%20detection/backend/api/review.py) (queue retrieval and moderator verdict submissions).

#### 2. Key Codebase Files Authored
* [`backend/main.py`](file:///D:/meme%20detection/backend/main.py) — FastAPI application instance, CORS configuration, static mounts, and lifespan handlers.
* [`backend/services/decision_router.py`](file:///D:/meme%20detection/backend/services/decision_router.py) — Decision routing logic and configurable threshold governance.
* [`backend/api/predict.py`](file:///D:/meme%20detection/backend/api/predict.py) & [`backend/api/review.py`](file:///D:/meme%20detection/backend/api/review.py) — Core HTTP endpoints.
* [`backend/core/config.py`](file:///D:/meme%20detection/backend/core/config.py) & [`backend/core/logger.py`](file:///D:/meme%20detection/backend/core/logger.py) — Pydantic settings management and telemetry logger.

#### 3. Defense / Viva Questions Faisal Can Answer
* **Q: Why use FastAPI over traditional Flask or Django?**
  * *Answer:* FastAPI is built on ASGI (`Starlette` and `uvicorn`), allowing fully asynchronous I/O. Since meme detection involves file uploads, disk writes, image preprocessing, and external database writes, async endpoints prevent server worker threads from blocking, enabling high-throughput request handling. Additionally, FastAPI provides automatic Pydantic data validation and auto-generated Swagger documentation at `/docs`.
* **Q: How does the decision router prevent model bias from causing harm?**
  * *Answer:* Standard binary models force an automated 50% split, which is dangerous for harmful content. Our decision router in `services/decision_router.py` enforces a wide human review band (0.10 to 0.90). Only memes with extreme confidence (≥90%) are blocked automatically, minimizing false bans while ensuring harmful memes never bypass scrutiny.

---

## 📊 Summary Work Distribution Matrix

| Team Member | Engineering Pillar | Primary Modules | Primary Technologies |
| :--- | :--- | :--- | :--- |
| **Rohit More** (231239) | Full-Stack, Database & Human Feedback UI | `core/database.py`, `models/`, Alembic migrations 001–004, `Dashboard.jsx`, `ReviewQueueTable.jsx` | React 19, Vite, Tailwind CSS, Supabase PostgreSQL, SQLAlchemy ORM |
| **Moinuddin Dhorajiwala** (231238) | Multimodal AI Model & Inference Engine | `services/model_service.py`, `ml_assets/baseline_best_model.keras`, `test_pipeline.py` | TensorFlow, Keras, EfficientNetB0, BiLSTM, NumPy, PIL |
| **Mohammed Aadil Kumshi** (231232) | Vision-Language OCR & Scope Classifier | `services/ocr_service.py`, `tests/test_text_inference.py`, `inference-diagnosis.md` | RapidOCR, Tesseract, OpenCV, ImageOps, Scope Heuristics |
| **Faisal Alvi** (231202) | API Gateway, Decision Router & Telemetry | `main.py`, `services/decision_router.py`, `api/predict.py`, `api/review.py`, `core/logger.py` | FastAPI, Uvicorn, Pydantic, Python Logging, CORS Middleware |

---

## 💡 Top 5 Defense Questions Invigilators Will Ask & How to Answer

### 1. "How do you prove that your model is actually multimodal and not just reading the text?"
> **Defense Answer:**  
> Our neural network explicitly defines two distinct input tensors in `services/model_service.py`: `inputs = {"image": shape(224, 224, 3), "text": string}`. If you supply an image without text, the visual branch (EfficientNetB0) extracts spatial and semantic features from the picture. If you supply identical text with a different image, the output probability shifts because the fusion layer combines both feature vectors before the final sigmoid activation.

### 2. "What happens if someone uploads a regular document or an ID card instead of a meme?"
> **Defense Answer:**  
> In initial testing (documented in `docs/inference-diagnosis.md`), unimodal baselines misclassified an ordinary ID card as harmful (0.92 score) because they lack scope boundaries. We introduced input scope classification in `ocr_service.py` that verifies the structural layout (image-caption composition) so non-meme documents and screenshots are separated from meme classifications.

### 3. "Why use Supabase instead of local SQLite?"
> **Defense Answer:**  
> SQLite locks on concurrent writes and cannot scale across distributed cloud deployments. Supabase provides managed PostgreSQL with ACID compliance, connection pooling, and remote persistence. Using Alembic ORM migrations, our schema evolves cleanly from baseline predictions to human moderator feedback logs without data loss.

### 4. "How does the Human Moderator Queue help improve the system over time?"
> **Defense Answer:**  
> When moderators submit verdicts on queued memes (`/api/v1/review/{id}/verdict`), the true label is saved alongside the model's original prediction. This dataset is exported to retrain the neural network on false positives and false negatives (like sarcasm and regional satire), forming an active learning feedback loop.

### 5. "What are the limitations of your current baseline and your future roadmap?"
> **Defense Answer:**  
> Current limitations include OCR sensitivity to extreme calligraphy, reliance on English/Hinglish vocabulary, and a 64-token text sequence limit in BiLSTM. Our Phase 2 roadmap integrates **CLIP** and **BLIP-2** for zero-shot vision-language alignment and Grad-CAM visual heatmaps for explainable AI.
