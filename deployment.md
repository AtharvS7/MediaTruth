# MediaTruth — Complete Free Deployment Guide

> **Goal:** Deploy the entire MediaTruth stack (Frontend + Backend + Database) for **$0/month** using free tiers.

---

## Architecture Overview

```
┌──────────────────────────┐     HTTPS      ┌─────────────────────────────┐
│      Vercel (Free)        │◄──────────────►│   Render.com (Free)          │
│   Next.js Frontend        │                │   FastAPI Backend (Python)   │
│   mediatruth.vercel.app   │                │   mediatruth.onrender.com    │
└──────────────────────────┘                └──────────────┬──────────────┘
                                                            │
                                        ┌───────────────────▼───────────────┐
                                        │         Supabase (Free)            │
                                        │   PostgreSQL + Auth + File Storage │
                                        │   yourproject.supabase.co          │
                                        └────────────────────────────────────┘
```

| Service | Platform | Free Tier Limits | Cost |
|---|---|---|---|
| Frontend (Next.js) | Vercel | 100GB bandwidth/month, unlimited deployments | **$0** |
| Backend (FastAPI) | Render.com | 750 hours/month, 512MB RAM | **$0** |
| Database + Auth | Supabase | 500MB DB, 50k monthly active users | **$0** |
| ML Model Weights | Hugging Face (cached in build) | Free public repos | **$0** |

> ⚠️ **Important Limitations of Free Tiers:**
> - **Render.com Free:** Server spins down after 15 minutes of inactivity. First request after sleep takes 30-60 seconds. Upgrade to $7/month Starter for always-on.
> - **Render.com Free RAM:** 512MB RAM. PyTorch + 2 models ≈ 1.5GB. **The ML models will likely OOM on Render Free.** See workarounds in Step 2.
> - **Supabase Free:** 500MB DB storage. At ~50KB per scan, this supports ~10,000 scans before hitting limits.

---

## Step 0 — Prerequisites

Before deploying, ensure you have:
- [ ] GitHub account (for connecting to Vercel and Render)
- [ ] Supabase account (free at supabase.com)
- [ ] The project pushed to a GitHub repository

### Push to GitHub

```bash
cd d:\MediaTruth

# Initialize git (if not already done)
git init
git add .
git commit -m "Initial commit — MediaTruth v1.0"

# Create a new repo on github.com then:
git remote add origin https://github.com/YOUR_USERNAME/mediatruth.git
git push -u origin main
```

> ⚠️ **CRITICAL before pushing:** Make sure `.env.local` and `backend/.env` are NOT tracked.
> Run: `git status` and verify neither file appears in the list.
> If they do: `git rm --cached frontend/.env.local backend/.env` then commit again.

---

## Step 1 — Set Up Supabase (Database + Auth)

Supabase is already integrated. You just need a production project.

### 1.1 Create a Supabase Project

1. Go to **https://supabase.com** → Sign In → New Project
2. Name: `mediatruth-prod`
3. Region: Choose nearest to your users (e.g., `ap-south-1` for India)
4. Database Password: Generate a strong password and save it
5. Wait 2-3 minutes for project to provision

### 1.2 Get Your API Keys

Go to **Settings → API** in your Supabase project:
- Copy `Project URL` → this is your `SUPABASE_URL`
- Copy `anon public` key → this is your `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- Copy `service_role` key (secret) → this is your `SUPABASE_SERVICE_KEY`

> ⚠️ The `service_role` key has full database access. Never expose it in frontend code.

### 1.3 Create Database Tables

Go to **SQL Editor** in Supabase and run:

```sql
-- Scans table: stores summary of each forensic analysis
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

-- Analysis results: stores full JSON result per scan
CREATE TABLE IF NOT EXISTS analysis_results (
  id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  scan_id  UUID NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
  result_json JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_scans_user_id ON scans(user_id);
CREATE INDEX IF NOT EXISTS idx_scans_created_at ON scans(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_analysis_results_scan_id ON analysis_results(scan_id);

-- Row Level Security
ALTER TABLE scans ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_results ENABLE ROW LEVEL SECURITY;

-- RLS Policies: users can only see their own scans
CREATE POLICY "Users see own scans" ON scans
  FOR SELECT USING (auth.uid() = user_id OR user_id IS NULL);

CREATE POLICY "Users insert own scans" ON scans
  FOR INSERT WITH CHECK (auth.uid() = user_id OR user_id IS NULL);

CREATE POLICY "Users delete own scans" ON scans
  FOR DELETE USING (auth.uid() = user_id);

-- Service role can do anything (backend uses service_role key)
CREATE POLICY "Service role full access scans" ON scans
  FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "Service role full access results" ON analysis_results
  FOR ALL TO service_role USING (true) WITH CHECK (true);
```

### 1.4 Configure Supabase Auth

Go to **Authentication → Settings**:
- Site URL: `https://your-app.vercel.app` (update after deploying frontend)
- Redirect URLs: Add `https://your-app.vercel.app/**`
- Email confirmations: Enable for production (disable for quick testing)

---

## Step 2 — Deploy Backend to Render.com

> ⚠️ **Memory Warning:** The ML models (EfficientNet-B5 + ResNet50) require ~1.5GB RAM. Render Free tier has 512MB. **Option A (workaround):** Run in lightweight mode where models return fallback scores. **Option B (recommended):** Use Render's $7/month Starter plan for always-on + 2GB RAM.

### Option A — Deploy Without Heavy ML (Works on Free Tier)

This deploys the backend with graceful model degradation — metadata analysis and confidence aggregation work, but deepfake/GAN/manipulation scoring returns zero (models unavailable).

### Option B — Deploy on Render Starter ($7/month)

Gives you 2GB RAM, always-on server, and custom domains.

### 2.1 Deploy to Render

1. Go to **https://render.com** → Sign In with GitHub
2. Click **New → Web Service**
3. Connect your GitHub repository
4. Configure:
   - **Name:** `mediatruth-backend`
   - **Root Directory:** `backend`
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Plan:** Free (or Starter for ML)

### 2.2 Set Environment Variables on Render

In your Render service → **Environment** tab, add:

```
ENV=production
SUPABASE_URL=https://YOUR-PROJECT-ID.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key-here
JWT_SECRET=generate-a-strong-random-string-here
ALLOWED_ORIGINS=https://your-app.vercel.app
WORKERS=1
```

> Generate JWT_SECRET: `python -c "import secrets; print(secrets.token_hex(32))"`

### 2.3 Note Your Backend URL

After deployment, note the URL: `https://mediatruth-backend.onrender.com`
(Replace `mediatruth-backend` with your actual service name)

### 2.4 Test Backend Health

```bash
curl https://mediatruth-backend.onrender.com/health/
# Expected: {"status": "ok", "models": {...}}
```

---

## Step 3 — Deploy Frontend to Vercel

### 3.1 Deploy to Vercel

1. Go to **https://vercel.com** → Sign In with GitHub
2. Click **Add New → Project**
3. Import your GitHub repository
4. Configure:
   - **Framework:** Next.js (auto-detected)
   - **Root Directory:** `frontend`
   - **Build Command:** `npm run build` (auto-detected)
   - **Output Directory:** `.next` (auto-detected)

### 3.2 Set Environment Variables on Vercel

In your Vercel project → **Settings → Environment Variables**, add these for **Production, Preview, Development**:

```
NEXT_PUBLIC_SUPABASE_URL        = https://YOUR-PROJECT-ID.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY   = your-anon-key-here
NEXT_PUBLIC_API_URL             = https://mediatruth-backend.onrender.com
```

> ⚠️ Do NOT copy from vercel.json — set these in the dashboard only.

### 3.3 Deploy

Click **Deploy**. Vercel will:
1. Clone your repo
2. Run `npm install` and `npm run build`
3. Deploy to a global CDN

Your frontend will be live at: `https://mediatruth-XXXXX.vercel.app`

### 3.4 Add Custom Domain (Optional, Free)

Vercel → Settings → Domains → Add domain
You can add a free domain from Freenom (.tk, .ml) or use the vercel.app subdomain.

---

## Step 4 — Post-Deployment Configuration

### 4.1 Update Supabase Auth URLs

Go back to Supabase → Authentication → Settings:
- **Site URL:** `https://mediatruth-XXXXX.vercel.app`
- **Redirect URLs:** `https://mediatruth-XXXXX.vercel.app/**`

### 4.2 Update Backend CORS

On Render → Environment:
```
ALLOWED_ORIGINS=https://mediatruth-XXXXX.vercel.app
```
Redeploy the service after updating.

### 4.3 Smoke Test the Full Stack

Visit your Vercel URL and:
- [ ] Landing page loads
- [ ] Sign Up with a new email
- [ ] Check email for verification link
- [ ] Sign In with your credentials
- [ ] Upload a test image (any JPEG)
- [ ] See the analysis result
- [ ] Visit History page — scan appears
- [ ] Click a scan — loads results from API (not sessionStorage)

---

## Step 5 — Keep Render Free Tier Alive (Optional)

Render Free tier sleeps after 15 minutes of inactivity. First request after sleep takes 30-60 seconds (bad UX for users).

**Free solution — use UptimeRobot:**
1. Go to **https://uptimerobot.com** → Free plan
2. Add Monitor → HTTP(S)
3. URL: `https://mediatruth-backend.onrender.com/health/`
4. Interval: Every 5 minutes
5. UptimeRobot pings your backend every 5 minutes, preventing it from sleeping

---

## Environment Variables Reference

### Backend (.env / Render Environment)

| Variable | Required | Description |
|---|---|---|
| `SUPABASE_URL` | ✅ Yes | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | ✅ Yes | Service role key (backend only, never expose) |
| `JWT_SECRET` | ✅ Yes | Secret for JWT signing (generate random) |
| `ALLOWED_ORIGINS` | ✅ Yes | Comma-separated frontend URLs for CORS |
| `ENV` | No | `development` or `production` |
| `PORT` | No | Port number (Render sets this automatically) |
| `WORKERS` | No | Number of uvicorn workers (default: 1) |

### Frontend (.env.local / Vercel Dashboard)

| Variable | Required | Description |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | ✅ Yes | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | ✅ Yes | Supabase anon/public key |
| `NEXT_PUBLIC_API_URL` | ✅ Yes | Backend URL (e.g., https://mediatruth-backend.onrender.com) |

---

## Upgrading From Free to Paid (When Ready)

| Need | Solution | Cost |
|---|---|---|
| Always-on backend + 2GB RAM | Render Starter | $7/month |
| Custom domain | Vercel Pro | $20/month (or free with vercel.app) |
| More DB storage | Supabase Pro | $25/month (8GB storage) |
| GPU for faster ML inference | Render GPU instances | $0.50/hour |

---

## Troubleshooting Common Deployment Issues

### "Network Error" on analysis
- Backend is sleeping (Render free tier cold start) — wait 60 seconds and retry
- `NEXT_PUBLIC_API_URL` not set in Vercel → check Vercel dashboard env vars
- CORS error → check `ALLOWED_ORIGINS` on Render includes your Vercel URL

### "Failed to load results"
- `SUPABASE_URL` or `SUPABASE_SERVICE_KEY` wrong on Render
- Database tables don't exist → re-run the SQL from Step 1.3

### "Supabase environment variables missing"
- `NEXT_PUBLIC_SUPABASE_URL` or `NEXT_PUBLIC_SUPABASE_ANON_KEY` not set in Vercel
- Set them in Vercel Dashboard → Settings → Environment Variables → Redeploy

### Backend crashes on startup
- Out of memory on Render Free (ML models need ~1.5GB) → upgrade to Starter
- Missing env vars → check Render logs

### Models show all-zero scores
- Model weights not found in `models/weights/` — this is expected without fine-tuned weights
- The system runs in graceful degradation mode — metadata analysis still works

---

## Quick Deployment Checklist

```
Pre-Deployment:
  [ ] git rm --cached frontend/.env.local (if committed)
  [ ] Rotate Supabase anon key if it was exposed
  [ ] Push code to GitHub

Supabase:
  [ ] Create production project
  [ ] Run SQL schema (Step 1.3)
  [ ] Copy URL, anon key, service_role key

Render (Backend):
  [ ] Create Web Service from GitHub repo
  [ ] Set Root Directory to backend/
  [ ] Set all 6 environment variables
  [ ] Note the backend URL

Vercel (Frontend):
  [ ] Import GitHub repo
  [ ] Set Root Directory to frontend/
  [ ] Set 3 NEXT_PUBLIC_ environment variables
  [ ] Deploy and note the frontend URL

Post-Deployment:
  [ ] Update Supabase Auth URLs with Vercel URL
  [ ] Update Render ALLOWED_ORIGINS with Vercel URL
  [ ] Smoke test: upload → analyze → results → history
  [ ] (Optional) Set up UptimeRobot to prevent Render sleep
```

---

*MediaTruth Deployment Guide | June 2026*
