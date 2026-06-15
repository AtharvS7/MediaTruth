# MediaTruth — Complete Deployment Guide

> **Last Updated:** June 2026 | **Status:** Production Ready | **Cost:** $0/month

---

## Architecture

```
┌──────────────────────────┐     HTTPS      ┌─────────────────────────────┐
│      Vercel (Free)        │◄──────────────►│   Render.com (Free)          │
│   Next.js Frontend        │                │   FastAPI Backend             │
│   mediatruth.vercel.app   │                │   ~120MB RAM (models via API) │
└──────────────────────────┘                └──────────────┬──────────────┘
                                                            │ HF Inference API
                                            ┌───────────────▼───────────────┐
                                            │    HuggingFace.co (Free)       │
                                            │    dima806 ViT (deepfake)      │
                                            │    umm-maybe (GAN/AI detect)   │
                                            └────────────────────────────────┘
                                                            │
                                            ┌───────────────▼───────────────┐
                                            │         Supabase (Free)        │
                                            │   PostgreSQL + Auth + Storage  │
                                            └────────────────────────────────┘
```

| Service | Platform | Free Tier | Cost |
|---|---|---|---|
| Frontend (Next.js) | Vercel | 100GB bandwidth/month | **$0** |
| Backend (FastAPI) | Render.com | 750 hours/month, 512MB RAM | **$0** |
| ML Inference | HuggingFace API | ~30,000 requests/month | **$0** |
| Database + Auth | Supabase | 500MB DB, 50k users | **$0** |
| **Total** | — | — | **$0/month** |

---

## How ML Models Work at $0

Instead of loading PyTorch models on the server (which would need 1.5GB RAM and crash Render Free), the backend calls **HuggingFace's free Inference API**:

```
Backend (120MB RAM) ──POST image bytes──► HuggingFace servers
                    ◄──JSON scores──────── (runs the model for free)
```

- **Deepfake:** `dima806/deepfake_vs_real_image_detection` (ViT-base, ~99.27% accuracy)
- **GAN/AI:** `umm-maybe/AI-image-detector` (AI-generated image detection)
- **ELA + DCT + Metadata:** Runs locally, no model needed
- Enabled by env var `USE_HF_API=true` (already set in `render.yaml`)

---

## Prerequisites

Before starting, you need:
- [ ] GitHub account (to connect to Vercel and Render)
- [ ] Supabase account (free at supabase.com)
- [ ] HuggingFace account (free at huggingface.co)
- [ ] Code already pushed to GitHub: `AtharvS7/MediaTruth`

---

## Step 0 — Get a Free HuggingFace Token

This is needed for ML inference on Render. Without it, models still work but may have slower cold-starts.

1. Go to **https://huggingface.co** → Sign up (free, no credit card)
2. Go to **Settings → Access Tokens → New token**
3. Name: `mediatruth-render`, Role: `read`
4. Copy the token (starts with `hf_`) — save it for Step 2

---

## Step 1 — Set Up Supabase (Database + Auth)

### 1.1 Create a Supabase Project

1. Go to **https://supabase.com** → Sign In → New Project
2. Name: `mediatruth-prod`
3. Region: Choose nearest (e.g., `ap-south-1` for India)
4. Database Password: Generate a strong password and save it
5. Wait 2-3 minutes for project to provision

### 1.2 Get Your API Keys

Go to **Settings → API** in your Supabase project:
- `Project URL` → `SUPABASE_URL`
- `anon public` key → `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `service_role` key (secret) → `SUPABASE_SERVICE_KEY`

> ⚠️ The `service_role` key has full DB access. Never expose it in frontend code.

### 1.3 Create Database Tables

Go to **SQL Editor** in Supabase and run:

```sql
-- Scans table
CREATE TABLE IF NOT EXISTS scans (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  file_type       TEXT NOT NULL CHECK (file_type IN ('image', 'video')),
  filename        TEXT,
  verdict         TEXT,
  ai_generated_probability    FLOAT,
  ai_edited_probability       FLOAT,
  traditional_edit_probability FLOAT,
  authentic_probability        FLOAT,
  confidence      FLOAT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Analysis results (full JSON)
CREATE TABLE IF NOT EXISTS analysis_results (
  id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  scan_id  UUID NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
  result_json JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_scans_user_id ON scans(user_id);
CREATE INDEX IF NOT EXISTS idx_scans_created_at ON scans(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_analysis_results_scan_id ON analysis_results(scan_id);

-- Row Level Security
ALTER TABLE scans ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_results ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "Users see own scans" ON scans
  FOR SELECT USING (auth.uid() = user_id OR user_id IS NULL);
CREATE POLICY "Users insert own scans" ON scans
  FOR INSERT WITH CHECK (auth.uid() = user_id OR user_id IS NULL);
CREATE POLICY "Users delete own scans" ON scans
  FOR DELETE USING (auth.uid() = user_id);
CREATE POLICY "Service role full access scans" ON scans
  FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access results" ON analysis_results
  FOR ALL TO service_role USING (true) WITH CHECK (true);
```

### 1.4 Configure Supabase Auth

Go to **Authentication → Settings**:
- **Site URL:** `https://your-app.vercel.app` (update after frontend deploys)
- **Redirect URLs:** Add `https://your-app.vercel.app/**`

---

## Step 2 — Deploy Backend to Render.com

> ✅ The `render.yaml` blueprint in the repo auto-configures everything.

### 2.1 Deploy via Blueprint

1. Go to **https://render.com** → Sign In with GitHub
2. Click **New → Blueprint**
3. Connect repository `AtharvS7/MediaTruth`
4. Render auto-detects `render.yaml` and shows the service config

### 2.2 Set Secret Environment Variables

In your Render service → **Environment** tab, set these manually (they are marked `sync: false` for security):

| Variable | Value | Where to get it |
|---|---|---|
| `HF_TOKEN` | `hf_xxxxxxxxxxxxxx` | HuggingFace Settings → Tokens (Step 0) |
| `SUPABASE_URL` | `https://xxx.supabase.co` | Supabase Settings → API |
| `SUPABASE_SERVICE_KEY` | `eyJhbGci...` | Supabase Settings → API (service_role key) |
| `ALLOWED_ORIGINS` | `https://your-app.vercel.app` | Set after Vercel deploy in Step 3 |

> `JWT_SECRET` is auto-generated by Render (already in render.yaml).
> `USE_HF_API=true` is already set in render.yaml — do NOT change it.

### 2.3 Deploy

Click **Deploy**. Build takes ~3-5 minutes (pip install).

### 2.4 Note Your Backend URL

After deployment: `https://mediatruth-backend.onrender.com`
(Your actual URL will vary — check Render dashboard)

### 2.5 Test Backend Health

```bash
curl https://mediatruth-backend.onrender.com/health/
# Expected: {"status": "ok", ...}
```

---

## Step 3 — Deploy Frontend to Vercel

### 3.1 Deploy to Vercel

1. Go to **https://vercel.com** → Sign In with GitHub
2. Click **Add New → Project**
3. Import `AtharvS7/MediaTruth`
4. Configure:
   - **Root Directory:** `frontend`
   - **Framework:** Next.js (auto-detected)

### 3.2 Set Environment Variables on Vercel

In Vercel project → **Settings → Environment Variables**:

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | `https://xxx.supabase.co` |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | `eyJhbGci...` (anon key) |
| `NEXT_PUBLIC_API_URL` | `https://mediatruth-backend.onrender.com` |

### 3.3 Deploy

Click **Deploy**. Your frontend will be live at: `https://mediatruth-XXXXX.vercel.app`

---

## Step 4 — Post-Deployment Configuration

### 4.1 Update Supabase Auth URLs

Supabase → Authentication → Settings:
- **Site URL:** `https://mediatruth-XXXXX.vercel.app`
- **Redirect URLs:** `https://mediatruth-XXXXX.vercel.app/**`

### 4.2 Update Render CORS

Render → Environment → update `ALLOWED_ORIGINS`:
```
ALLOWED_ORIGINS=https://mediatruth-XXXXX.vercel.app
```
Click **Save Changes** — Render auto-redeploys.

### 4.3 Smoke Test Checklist

- [ ] Frontend loads at Vercel URL
- [ ] Sign Up with email → receive verification
- [ ] Sign In → redirected to upload page
- [ ] Upload a JPEG photo → analysis completes (may take 20-30s on cold start)
- [ ] Results page shows: verdict, confidence %, all 4 probability bars
- [ ] Manipulation heatmap renders
- [ ] Scan appears in History page
- [ ] Click history entry → full results load

---

## Step 5 — Keep Render Free Tier Alive (Recommended)

Render Free spins down after 15 minutes of inactivity. First request after sleep takes 30-60s.

**Fix — UptimeRobot (free):**
1. Go to **https://uptimerobot.com** → Free plan → Add Monitor
2. Type: HTTP(S), URL: `https://mediatruth-backend.onrender.com/health/`
3. Interval: Every 5 minutes
4. This prevents Render from sleeping → fast response for users

---

## Environment Variables Reference

### Backend (Render Dashboard)

| Variable | Required | Description |
|---|---|---|
| `USE_HF_API` | ✅ | `true` — enables HuggingFace Inference API mode |
| `HF_TOKEN` | ✅ | Free HuggingFace token for stable rate limits |
| `SUPABASE_URL` | ✅ | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | ✅ | Service role key (backend only) |
| `JWT_SECRET` | ✅ | Auto-generated by Render |
| `ALLOWED_ORIGINS` | ✅ | Your Vercel frontend URL |
| `ENV` | No | `production` (set by render.yaml) |
| `WORKERS` | No | `1` (set by render.yaml) |

### Frontend (Vercel Dashboard)

| Variable | Required | Description |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | ✅ | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | ✅ | Supabase anon/public key |
| `NEXT_PUBLIC_API_URL` | ✅ | Backend URL on Render |

---

## Troubleshooting

### "Analysis takes 30-60 seconds on first request"
Normal. Two cold-starts happening simultaneously:
1. Render service waking up (15s)
2. HuggingFace model loading (15-20s)

After first request, subsequent ones take 2-5 seconds.
Fix: Set up UptimeRobot (Step 5) to prevent Render sleep.

### "Network Error" on analysis
- Backend sleeping → wait 60s and retry
- `NEXT_PUBLIC_API_URL` missing/wrong in Vercel → check dashboard
- CORS error → `ALLOWED_ORIGINS` on Render doesn't include your Vercel URL

### "Failed to load results"
- Wrong `SUPABASE_URL` or `SUPABASE_SERVICE_KEY` on Render
- Database tables don't exist → re-run SQL from Step 1.3

### "Supabase environment variables missing"
- Set `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` in Vercel
- Redeploy after setting them

### Models return 0.0 scores / "Limited Mode" banner
- `USE_HF_API` not set to `true` on Render
- `HF_TOKEN` missing → API may rate-limit (but should still work)
- HuggingFace Inference API temporary outage → try again in a few minutes

### "413 Request Entity Too Large"
- Image/video file too large for the plan
- Resize image to under 10MB before uploading

---

## Quick Deployment Checklist

```
Pre-Deployment:
  [ ] Push code to GitHub (AtharvS7/MediaTruth)
  [ ] Get HuggingFace token (huggingface.co/settings/tokens)
  [ ] Have Supabase URL, anon key, service_role key ready

Supabase:
  [ ] Create production project
  [ ] Run SQL schema (Step 1.3)
  [ ] Copy 3 API keys

Render (Backend):
  [ ] New Blueprint → connect AtharvS7/MediaTruth
  [ ] Set: HF_TOKEN, SUPABASE_URL, SUPABASE_SERVICE_KEY, ALLOWED_ORIGINS
  [ ] Deploy and note the backend URL

Vercel (Frontend):
  [ ] New Project → import AtharvS7/MediaTruth
  [ ] Root Directory: frontend
  [ ] Set: NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY, NEXT_PUBLIC_API_URL
  [ ] Deploy and note the frontend URL

Post-Deployment:
  [ ] Update Supabase Auth URLs with Vercel URL
  [ ] Update Render ALLOWED_ORIGINS with Vercel URL
  [ ] Set up UptimeRobot (https://uptimerobot.com, free)
  [ ] Run smoke test checklist (Step 4.3)
```

---

*MediaTruth Deployment Guide — June 2026 | Zero-cost production deployment*
