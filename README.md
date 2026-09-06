# 🛡️ MemeGuard — Multimodal Harmful Meme Detection System

> **Phase 1 Foundation** 🚀
> A full-stack AI platform designed to detect, flag, and manage harmful or offensive multimodal content (memes) through intelligent routing and human moderation queues.

---

## 🏗️ Architecture & Workflow

```mermaid
graph TD
    %% Define styles
    classDef frontend fill:#38bdf8,stroke:#0284c7,stroke-width:2px,color:#fff;
    classDef backend fill:#10b981,stroke:#059669,stroke-width:2px,color:#fff;
    classDef db fill:#f59e0b,stroke:#d97706,stroke-width:2px,color:#fff;
    classDef review fill:#f43f5e,stroke:#e11d48,stroke-width:2px,color:#fff;

    %% Nodes
    User([User / Moderator])
    UI[Frontend: React + Vite + Tailwind]:::frontend
    API[Backend: FastAPI + Python]:::backend
    ML[Mock Inference Pipeline<br/>(Phase 2: CLIP/BLIP-2)]:::backend
    DB[(Supabase PostgreSQL)]:::db
    Queue[Human Review Queue]:::review

    %% Relationships
    User -- Uploads Meme --> UI
    UI -- POST /api/v1/predict --> API
    API -- Extracted Image/Text --> ML
    ML -- Label + Confidence Score --> API
    API -- Saves Prediction --> DB
    
    API -- Conf < 85% --> Queue
    User -- Reviews Pending Memes --> Queue
    Queue -- Verdict (Block/Allow) --> DB
```

---

## 🌟 Key Features

*   **⚡ High-Performance Backend**: Built with **FastAPI** for asynchronous, high-throughput request handling.
*   **🎨 Dynamic Frontend**: Responsive, animated UI built with **React**, **Vite**, and **Tailwind CSS**.
*   **🗄️ Self-Evolving Schema**: Managed via **Alembic ORM Migrations** directly connected to a **Supabase PostgreSQL** instance.
*   **⚖️ Intelligent Moderation Router**: Configurable confidence thresholds automatically route borderline memes to a dedicated **Human Review Queue**.

---

## 📁 Repository Structure

```text
meme-detection/
├── 📂 backend/          # FastAPI server, ML services, DB migrations
│   ├── 📂 app/          # Application core (routers, schemas, services)
│   ├── 📂 migrations/   # Alembic revision scripts
│   ├── 📄 requirements.txt # Pinned dependencies
│   └── 📄 .env          # Secrets (Not tracked)
├── 📂 frontend/         # React application
│   ├── 📂 src/          # React components, pages, context
│   ├── 📄 package.json  # Node dependencies
│   └── 📄 tailwind.config.js
├── 📄 .gitignore        # Keeps secrets & temporary files out
└── 📄 README.md         # You are here!
```

---

## 🚀 Quick Start Guide

### 1. Database & Backend Setup

```bash
cd backend
# Create a virtual environment
python -m venv .venv
# Activate it
.venv\Scripts\activate      # Windows
source .venv/bin/activate   # Linux/macOS
# Install dependencies
pip install -r requirements.txt
# Run migrations to set up Supabase schema
alembic upgrade head
# Start FastAPI server
uvicorn app.main:app --reload --port 8000
```
*API Docs available at: [http://localhost:8000/docs](http://localhost:8000/docs)*

### 2. Frontend Setup

```bash
cd frontend
# Install dependencies
npm install
# Start dev server
npm run dev
```
*Web App available at: [http://localhost:5173](http://localhost:5173)*

---

## 🛣️ Roadmap

- [x] **Phase 1**: Full-stack setup, DB migrations, Frontend UI, Mock Inference Pipeline, Moderator Queue.
- [ ] **Phase 2**: Integration of **CLIP** and **BLIP-2** for real multimodal text/image analysis.
- [ ] **Phase 3**: Explainable AI (Grad-CAM heatmaps) and EasyOCR text extraction.

---
*Built for safe, scalable, and intelligent content moderation.*
