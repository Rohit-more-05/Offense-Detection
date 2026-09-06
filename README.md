<div align="center">
  <img src="https://raw.githubusercontent.com/tandpfun/skill-icons/main/icons/React-Dark.svg" width="40" height="40" />
  <img src="https://raw.githubusercontent.com/tandpfun/skill-icons/main/icons/FastAPI.svg" width="40" height="40" />
  <img src="https://raw.githubusercontent.com/tandpfun/skill-icons/main/icons/PyTorch-Dark.svg" width="40" height="40" />
  <img src="https://raw.githubusercontent.com/tandpfun/skill-icons/main/icons/PostgreSQL-Dark.svg" width="40" height="40" />
  <img src="https://raw.githubusercontent.com/tandpfun/skill-icons/main/icons/TailwindCSS-Dark.svg" width="40" height="40" />

  <h1>🛡️ MemeGuard — Harmful Meme Detection System</h1>
  <p><i>A full-stack, AI-powered platform designed to detect, flag, and manage harmful or offensive multimodal content using state-of-the-art NLP models.</i></p>

  <p>
    <a href="https://memeguard-frontend.onrender.com/"><img src="https://img.shields.io/badge/Live_Frontend-Render-46E3B7?style=for-the-badge&logo=render&logoColor=white" alt="Frontend Status"></a>
    <a href="https://memeguard-backend.onrender.com/docs"><img src="https://img.shields.io/badge/Live_API_Docs-Swagger-85EA2D?style=for-the-badge&logo=swagger&logoColor=black" alt="API Status"></a>
  </p>
</div>

---

## 🏗️ Architecture & Workflow

The system is built on a modern **React/Vite** frontend and a **FastAPI** Python backend, backed by **Supabase PostgreSQL**. The core engine features a real-time NLP classification pipeline powered by a fine-tuned **BERT** model.

```mermaid
graph TD
    %% Define styles
    classDef frontend fill:#3b82f6,stroke:#1d4ed8,stroke-width:2px,color:#fff,rx:8px,ry:8px;
    classDef backend fill:#10b981,stroke:#047857,stroke-width:2px,color:#fff,rx:8px,ry:8px;
    classDef ml fill:#8b5cf6,stroke:#5b21b6,stroke-width:2px,color:#fff,rx:8px,ry:8px;
    classDef db fill:#f59e0b,stroke:#b45309,stroke-width:2px,color:#fff,rx:8px,ry:8px;
    classDef queue fill:#ef4444,stroke:#b91c1c,stroke-width:2px,color:#fff,rx:8px,ry:8px;
    classDef render fill:#000000,stroke:#46E3B7,stroke-width:2px,color:#fff;

    %% Nodes
    User([👤 User / Moderator])
    
    subgraph Render Cloud Deployment
        UI[⚛️ Frontend<br/>React + Vite + Tailwind]:::frontend
        API[🚀 Backend API<br/>FastAPI Server]:::backend
        ML["🧠 NLP Inference Engine<br/>HuggingFace BERT<br/>(Lazy-Loaded PyTorch)"]:::ml
    end

    DB[(🗄️ Supabase<br/>PostgreSQL)]:::db
    Queue[⚠️ Human Review Queue<br/>Moderation Dashboard]:::queue

    %% Relationships
    User -- "Uploads Meme" --> UI
    UI -- "POST /api/v1/predict" --> API
    API -- "Text Extraction" --> ML
    ML -- "Label + Confidence %" --> API
    API -- "Persists Log" --> DB
    
    API -- "Confidence < 85%" --> Queue
    API -- "Confidence >= 85%" --> User
    
    User -- "Reviews Pending Cases" --> Queue
    Queue -- "Final Verdict (Block/Allow)" --> DB
```

---

## 🌟 Key Features

- **⚡ High-Performance Backend**: Built with **FastAPI** for asynchronous, high-throughput request handling. Includes dual-stream deployment telemetry.
- **🧠 Real-Time NLP Inference**: Integrated with a fine-tuned HuggingFace BERT model (`autonlp-text-hateful-memes`). Designed with a **Lazy-Load Singleton** architecture to safely run PyTorch ML models within strict 512MB RAM cloud constraints.
- **🎨 Dynamic Frontend**: Responsive, glassmorphism-inspired animated UI built with **React**, **Vite**, and **Tailwind CSS**.
- **🗄️ Self-Evolving Schema**: Managed via **Alembic ORM Migrations** directly connected to a **Supabase PostgreSQL** cloud instance.
- **⚖️ Intelligent Moderation Router**: Configurable confidence thresholds automatically route borderline or ambiguous memes to a dedicated **Human Review Queue**.

---

## 📁 Repository Structure

```text
meme-detection/
├── 📂 backend/               # FastAPI server, PyTorch Inference, DB migrations
│   ├── 📂 app/               # Application core (routers, schemas, services)
│   ├── 📂 migrations/        # Alembic revision scripts
│   ├── 📄 requirements.txt   # CPU-optimized pinned dependencies
│   └── 📄 .env               # Secrets (Not tracked)
├── 📂 frontend/              # React application
│   ├── 📂 src/               # React components, pages, context
│   ├── 📄 package.json       # Node dependencies
│   └── 📄 tailwind.config.js # Theming and Design Tokens
├── 📄 deploy.sh              # Production-grade CI/CD pre-deployment orchestrator
└── 📄 README.md              # You are here!
```

---

## 🚀 Quick Start Guide

### 1. Database & Backend Setup

```bash
cd backend
# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows

# Install CPU-optimized dependencies
pip install -r requirements.txt

# Run migrations to set up Supabase schema
alembic upgrade head

# Start FastAPI server
uvicorn app.main:app --reload --port 8000
```
> **Tip:** API Docs available at `http://localhost:8000/docs`

### 2. Frontend Setup

```bash
cd frontend
# Install dependencies
npm install

# Start development server
npm run dev
```
> **Tip:** Web App available at `http://localhost:5173`

---

## 🛣️ Project Roadmap

- [x] **Phase 1**: Full-stack setup, Supabase migrations, React UI, and Human Moderator Queue.
- [x] **Phase 1.5**: **BERT NLP Integration**. Replaced mock inference with real PyTorch classification, including Render free-tier deployment optimizations (lazy-loading, CPU wheels, CVE patches).
- [ ] **Phase 2**: Integration of **CLIP** and **BLIP-2** for multi-modal vision-language analysis (understanding the image *context* alongside text).
- [ ] **Phase 3**: Explainable AI (**Grad-CAM heatmaps**) and EasyOCR text extraction.

---
<div align="center">
  <i>Built for safe, scalable, and intelligent content moderation.</i>
</div>
