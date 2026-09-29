# MediaTruth — AI Media Forensics Platform

> **Current upgrade status (2026-09-29):** Supabase Free is provisioned; bounded local jobs, offline C2PA inspection, safe exports and locked dependencies are implemented. See [local operations](OPERATIONS.md), [codebase audit](AUDIT_2026-09-29.md) and [INR 0 upgrade plan/task ledger](UPGRADE_PLAN.md). Detection scores are experimental, not validated probabilities. New `/metadata` page exports still images without ordinary metadata; it does not guarantee removal of invisible watermarks or all AI traces. Enterprise release remains blocked by the items in the audit.


> **Detect AI-generated, AI-edited, deepfaked, and traditionally manipulated images and videos using a multi-model forensics pipeline.**

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        MediaTruth Stack                         │
├────────────────────────┬────────────────────────────────────────┤
│  Frontend              │  Backend                               │
│  Next.js 15 + Tailwind │  FastAPI + PyTorch                     │
│  Vercel                │  Docker / Render                       │
├────────────────────────┼────────────────────────────────────────┤
│  Database              │  ML Models                             │
│  Supabase (Postgres)   │  EfficientNet-B5 (deepfake)            │
│                        │  ResNet-50 CNNDetect (GAN)             │
│                        │  ELA + DCT (manipulation)              │
│                        │  EXIF parser (metadata)                │
└────────────────────────┴────────────────────────────────────────┘
```

---

## Project Structure

```
MediaTruth/
├── backend/
│   ├── main.py                          # FastAPI entrypoint
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── .env.example
│   ├── api/
│   │   └── routes/
│   │       ├── image_routes.py          # POST /image/analyze
│   │       ├── video_routes.py          # POST /video/analyze
│   │       ├── scan_routes.py           # GET /scan/history, /scan/{id}
│   │       └── health_routes.py
│   ├── services/
│   │   ├── model_loader.py              # Startup model loading + caching
│   │   ├── image_analyzer.py            # Image pipeline orchestrator
│   │   ├── video_analyzer.py            # Video pipeline orchestrator
│   │   └── supabase_service.py          # DB persistence
│   ├── inference_pipeline/
│   │   ├── deepfake_detector.py         # EfficientNet-B5 deepfake clf
│   │   ├── gan_detector.py              # CNNDetect GAN fingerprint
│   │   ├── manipulation_localizer.py    # ELA + DCT heatmap generation
│   │   ├── metadata_analyzer.py         # EXIF anomaly detection
│   │   └── aggregator.py               # Confidence matrix + verdict
│   ├── utils/
│   │   ├── file_utils.py
│   │   ├── video_utils.py
│   │   ├── auth.py
│   │   └── logger.py
│   ├── models/weights/                  # Downloaded model weights (gitignored)
│   └── tests/                           # Unit tests (pytest)
├── frontend/
│   ├── src/app/
│   │   ├── page.tsx                     # Landing page
│   │   ├── upload/page.tsx              # Upload + analysis progress
│   │   ├── results/[id]/page.tsx        # Full forensics dashboard
│   │   ├── history/page.tsx             # Scan history
│   │   └── auth/page.tsx               # Sign in / Sign up
│   └── src/components/
│       ├── charts/ProbabilityMatrix.tsx
│       ├── charts/HeatmapViewer.tsx
│       ├── ui/DetectorCard.tsx
│       └── layout/Nav.tsx
├── supabase/
│   └── schema.sql                       # Full DB schema with RLS
└── docker-compose.yml
```

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker & Docker Compose (optional)
- Supabase account (free tier works)

---

### 1. Clone & Configure

```bash
git clone https://github.com/AtharvS7/MediaTruth.git
cd MediaTruth
```

**Backend config:**
```bash
cp backend/.env.example backend/.env
# Edit backend/.env with your Supabase credentials
```

**Frontend config:**
```bash
cp frontend/.env.local.example frontend/.env.local
# Edit frontend/.env.local with your API URL and Supabase keys
```

---

### 2. Database Setup

1. Create a Supabase project at [supabase.com](https://supabase.com)
2. Open the SQL editor and run `supabase/schema.sql`
3. Copy your **Project URL** and **service role key** into `backend/.env`
4. Copy your **Project URL** and **anon key** into `frontend/.env.local`

---

### 3. Run with Docker

```bash
docker compose up --build
```

This starts the **FastAPI backend** on `http://localhost:8000`.

Model weights are downloaded on first startup (~1–2 GB, saved to Docker volume).

---

### 4. Run Locally (Development)

**Backend:**
```bash
cd backend
python -m venv .venv && .venv\Scripts\activate   # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
# Open http://localhost:3000
```

---

## API Reference

### `POST /image/analyze`

Upload an image for forensic analysis.

**Request:** `multipart/form-data` with field `file`

**Response:**
```json
{
  "scan_id": "uuid",
  "file_type": "image",
  "ai_generated_probability": 0.22,
  "ai_edited_probability": 0.41,
  "traditional_edit_probability": 0.63,
  "authentic_probability": 0.12,
  "final_verdict": "Traditionally Edited",
  "confidence": 0.63,
  "manipulation_heatmap": "<base64 PNG>",
  "detector_scores": {
    "deepfake_score": 0.15,
    "gan_score": 0.08,
    "manipulation_score": 0.72,
    "metadata_anomaly_score": 0.45
  },
  "metadata_findings": ["✏️ Adobe Photoshop CC 2024 detected"],
  "explanation": "Analysis indicates traditional image editing..."
}
```

### `POST /video/analyze`

Upload a video (max 180s) for forensic analysis. Same response schema plus:
```json
{
  "duration_seconds": 47.3,
  "frames_analyzed": 15,
  "per_frame_results": [...]
}
```

### `GET /scan/history?page=1&page_size=20`

Returns paginated scan history.

### `GET /scan/{scan_id}`

Returns full scan result by ID.

### `GET /health/`

Public health check endpoint.

---

## ML Models

| Detector | Architecture | Purpose | Weight Source |
|---|---|---|---|
| Deepfake | EfficientNet-B5 | Face deepfake detection | timm pretrained + optional fine-tune |
| GAN | ResNet-50 (CNNDetect) | GAN-generated image detection | CNNDetect (Wang et al. 2020) |
| Manipulation | ELA + DCT analysis | Pixel-level edit localization | Algorithmic (no weights needed) |
| Metadata | Rule-based EXIF parser | AI software signature detection | Algorithmic |

### Adding Custom Weights

Place `.pth` files in `backend/models/weights/`:
- `efficientnet_b5_deepfake.pth` — fine-tuned deepfake classifier
- `cnn_detect.pth` — CNNDetect GAN detector weights

The model loader will automatically use them on next startup.

---

## Security

- **Input Validation:** Magic-byte file validation prevents file-type spoofing
- **Rate Limiting:** 5 req/min for image analysis, 3 req/min for video analysis
- **IDOR Protection:** Scan ownership enforcement — users can only access their own scans
- **CORS:** Configurable origin allowlist via `ALLOWED_ORIGINS` env var
- **CSP Headers:** Content Security Policy, X-Frame-Options, and more
- **Container Security:** Non-root user in Docker, no stack trace leakage
- **RLS:** Row Level Security policies on all Supabase tables

---

## Deployment

### Backend — Docker + Render/Railway/Fly.io

```bash
docker build -t mediatruth-backend ./backend
docker push your-registry/mediatruth-backend
```

Set these environment variables in your hosting provider:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `JWT_SECRET` *(reserved — not read by app code; token verification uses Supabase)*
- `ALLOWED_ORIGINS`

### Frontend — Vercel

```bash
cd frontend
npx vercel --prod
```

Set environment variables in Vercel dashboard (see `frontend/.env.local.example`).

---

## Testing

### Backend Unit Tests
```bash
cd backend
python -m pytest tests/ -v
```

Tests cover:
- Aggregator probability fusion and verdict logic
- IDOR ownership access control
- Magic-byte file validation
- Metadata analyzer AI software detection

---

## Performance Notes

- **Model caching:** All models are loaded once at startup and kept in memory
- **Async inference:** `asyncio.gather` runs all detectors concurrently
- **Video batching:** Frames analyzed in batches of 8 to control VRAM usage
- **GPU support:** Automatically uses CUDA if available, falls back to CPU
- **Timeout guards:** All DB operations wrapped in 12-second timeouts

---

## License

MIT — free to use, modify, and deploy commercially.
