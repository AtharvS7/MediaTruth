# Local operations and release gates

This is an experimental media-forensics application, updated 30 September 2026. The public frontend runs on Vercel, the API on Render Free, and private jobs/reports on Supabase Free. Inference runs on the user's temporarily approved PC worker. No paid compute was purchased. Full enterprise availability and detector accuracy are not established.

## Hosted service and PC worker

- Frontend: https://mediatruth-atharv-sawanes-projects.vercel.app
- API: https://mediatruth-api.onrender.com
- Supabase project: `yiqpqgxlujqcfeagsfff`
- Source branch: `upgrade/forensics-audit-metadata-export`

From `D:\MediaTruth\backend`, start `../.venv-upgrade/Scripts/python.exe -u -m services.remote_worker`. Stop a foreground worker with Ctrl+C. `worker.env.local` must contain only `MEDIATRUTH_API_URL` and the shared `WORKER_SECRET`; keep it outside Git. Do not give the worker a Supabase service key. Do not start a second operator process if one already runs. The current hidden session records its PID in `.tools/worker.local.json` and logs in `.tools/worker.out.log` and `.tools/worker.err.log`; verify its process command before stopping that PID, which may be reused after a restart. No automatic startup task is installed.

The PC needs to remain on and connected for processing. It polls every 60 seconds; new jobs can wait up to a polling interval plus cold start. `/capabilities` reports worker availability, and new cloud reservations are rejected when the worker is offline. Polling uses the workspace's shared Render free hours. Admission limits reduce resource use but do not guarantee zero overage or uninterrupted service; monitor provider dashboards and keep paid upgrades disabled.

## Start locally

1. Install Python 3.12 and Node 22. Install `uv==0.12.19`, then run `uv sync --project backend --frozen --extra ml` from the repository root. In the current workspace the verified environment is `.venv-upgrade`; use its Python executable for local commands.
2. Set `SUPABASE_SERVICE_KEY` in ignored `backend/.env` to the server secret for project `yiqpqgxlujqcfeagsfff`. The URL and frontend publishable key are already configured locally. Never put the server key in a `NEXT_PUBLIC_` variable.
3. From `backend`, run `../.venv-upgrade/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1` in this workspace. On a fresh installation use `uv run --frozen --extra ml uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1` instead.
4. From `frontend`, run `npm ci` and `npm run dev`. Open `http://localhost:3000`.

Local checkpoint files under `backend/models/weights` are not committed. The existing CNNDetect checkpoint loads and produces scores; its training source/license and generalization still need review. Without trained weights, relevant detectors abstain. Workers disable automatic model downloads and remote inference.

## Authentication configuration

The user configured [Supabase Auth URL Configuration](https://supabase.com/dashboard/project/yiqpqgxlujqcfeagsfff/auth/url-configuration). Site URL should be `https://mediatruth-atharv-sawanes-projects.vercel.app`, with these exact redirects:

- `http://localhost:3000/auth/callback`
- `http://localhost:3000/auth/update-password`
- `https://mediatruth-atharv-sawanes-projects.vercel.app/auth/callback`
- `https://mediatruth-atharv-sawanes-projects.vercel.app/auth/update-password`

Open email links in the browser that requested them because PKCE needs its verifier. Password sign-in passed hosted browser tests using a temporary confirmed account. Actual confirmation/recovery email delivery and password replacement through an emailed PKCE link remain unverified.

## Request lifecycle

Cloud mode uses `POST /uploads` to reserve an owner-scoped job, upload to a private signed URL, then finalize it. Poll `GET /jobs/{id}`; use `DELETE /jobs/{id}` to request cancellation. A running cancellation remains pending until acknowledged by the worker. The Supabase queue survives API/worker restarts; expired leases permit one retry. Completion saves reports atomically. Local mode retains multipart `POST /jobs` and its in-memory queue.

There is one inference slot and space for two waiting jobs. Metadata export shares the slot. Server timeout is 300 seconds for analysis and 60 seconds for export. Queue overload returns 503. Synchronous `/image/analyze` and `/video/analyze` are retired (410); `ENABLE_LEGACY_ANALYSIS=true` is for isolated compatibility tests only and bypasses process isolation.

Cloud terminal inputs are deleted on cleanup passes and exports expire after 24 hours. Cleanup retries on real job traffic; while services sleep, objects can remain longer. A second sweep handles late uploads through still-valid signed URLs. A machine crash can leave application temporary files; review only `mediatruth_uploads`/`mediatruth_worker_*` directories with the worker stopped. Local-mode pending jobs are not durable. Run one API process under this deployment configuration.

Stored reports omit heatmaps. The database allows 50 saved reports per owner in a rolling day and a 512KiB report payload. This limits saved reports, not failed-analysis attempts. Request/queue bounds also apply. Monitor database usage; these limits do not guarantee staying within provider capacity indefinitely.

## Database and retention

Applied migrations include the initial private schema, atomic reports, restricted profile trigger, durable jobs, job budget, and worker health. Live checks passed for owner isolation, anonymous denial, transactional failure, RPC permissions, lease fencing and same-ID retries. The private queue intentionally has no client read/write policy; access is server-only. Temporary fixture users, jobs and reports are removed after checks. Add forward migrations for further changes; do not edit applied migrations.

Retention is **manual**, never an unattended deletion. The service-role-only `prune_expired_reports(p_before)` rejects cutoffs newer than 30 days. Back up and review the cutoff before invoking it. Owner account deletion leaves ownerless reports private; a retention decision is needed for these records.

Before schema changes, take a PostgreSQL custom-format backup with `pg_dump` using the provider's database connection details and a local password file or environment variable. Keep backups encrypted and outside Git. The application server key is not a PostgreSQL password. Back up Auth separately as needed; public-table backups alone do not restore user identity.

Rehearse restore into an empty local PostgreSQL/Supabase environment, never the live project: apply schema, restore data, compare counts and repeat two-owner/anonymous isolation and RPC rollback checks. Auth-linked IDs must match. No backup/restore rehearsal has been performed yet because database connection credentials are unavailable.

## Verification and limits

Run backend tests with `python -m pytest tests -q`, then `ruff check .` and `pip-audit`. Frontend checks: `npx tsc --noEmit --incremental false`, `npm run build`, `npm audit`. CI uses locked dependencies and blocks lint/security failures. The test client emits one upstream httpx deprecation warning.

Observed: 145 backend tests passed, real isolated worker inference and metadata export passed, and the frontend builds and type-checks. Hosted Chromium tests passed mobile keyboard sign-in, private upload/export download, image-job completion with an Inconclusive result, and saved history. Live Supabase integration passed. On 1 October both Docker images built and served HTTP successfully; backend non-root execution, ML imports, secret-file exclusion, PNG pixel preservation and isolated analysis without networking passed. Three auth browser checks passed against the containerized frontend. The container analysis used no bundled model weights. Trained-model container load testing, email delivery and backup/restore remain unverified.

Use `/health/` for API liveness. `/health/ready` checks cloud worker availability
through the database and returns 503 when processing is unavailable; this must not
be used to restart an otherwise healthy API repeatedly while the PC is off.

Browser checks: install Chromium with `npx playwright install chromium` in frontend, run the app, then run `npx playwright test auth.spec.ts`. Set `E2E_BASE_URL` to test a deployed frontend. The separate hosted fixture suite requires explicit `E2E_LIVE=1`, backend server credentials locally, and an online PC worker; it creates and removes an isolated confirmed test user without sending email. Browser traces/screenshots are disabled to avoid saving credentials.

C2PA inspection uses [the official SDK's offline configuration](https://github.com/contentauth/c2pa-python/blob/main/docs/context-settings.md). Trust is evaluated against SDK anchors with no live revocation lookup. Signed provenance is not proof that the depicted scene is truthful. Absence of credentials is not proof of authenticity. Export removes ordinary metadata; it does not guarantee removal of invisible watermarks, pixel-level AI signals or external copies.

Public schema-v2 verdicts are withheld as Inconclusive until validation passes. Legacy score fields are zero placeholders, not probabilities. The remaining scientific gates are representative licensed data, generator/original-level splits, independent metrics, calibration, mixed edits and real video temporal/localization evaluation.
