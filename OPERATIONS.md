# Local operations and release gates

This is an experimental media-forensics application. Run on existing hardware with one API process. The Supabase project is on the Free plan; no paid compute, remote inference or automatic deployment is enabled. Full enterprise availability and detector accuracy are not established.

## Start locally

1. Install Python 3.12 and Node 22. Install `uv==0.12.19`, then run `uv sync --project backend --frozen --extra ml` from the repository root. In the current workspace the verified environment is `.venv-upgrade`; use its Python executable for local commands.
2. Set `SUPABASE_SERVICE_KEY` in ignored `backend/.env` to the server secret for project `yiqpqgxlujqcfeagsfff`. The URL and frontend publishable key are already configured locally. Never put the server key in a `NEXT_PUBLIC_` variable.
3. From `backend`, run `../.venv-upgrade/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1` in this workspace. On a fresh installation use `uv run --frozen --extra ml uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1` instead.
4. From `frontend`, run `npm ci` and `npm run dev`. Open `http://localhost:3000`.

Local checkpoint files under `backend/models/weights` are not committed. The existing CNNDetect checkpoint loads and produces scores; its training source/license and generalization still need review. Without trained weights, relevant detectors abstain. Workers disable automatic model downloads and remote inference.

## Authentication setup still required

In [Supabase Auth URL Configuration](https://supabase.com/dashboard/project/yiqpqgxlujqcfeagsfff/auth/url-configuration), set the local Site URL to `http://localhost:3000` and allow exactly:

- `http://localhost:3000/auth/callback`
- `http://localhost:3000/auth/update-password`

Add exact HTTPS counterparts only when a real production hostname exists. Open email links in the browser that requested them because PKCE needs its verifier. Test signup, verification, login, recovery, password update and logout before release. Public access to the Supabase account does not replace the backend secret. Email delivery and provider limits have not been tested.

## Request lifecycle

`POST /jobs` accepts an authenticated image/video upload and returns 202 with an ID. Poll `GET /jobs/{id}` for queued/loading/analyzing/saving/completed/failed/cancelled. `DELETE /jobs/{id}` stops queued/running work; saving cannot be cancelled because the database transaction may already commit. Completed responses include the scan result. Job IDs are owner-scoped. A 404 after restart means check history before resubmitting.

There is one inference slot and space for two waiting jobs. Metadata export shares the slot. Server timeout is 300 seconds for analysis and 60 seconds for export. Queue overload returns 503. Synchronous `/image/analyze` and `/video/analyze` are retired (410); `ENABLE_LEGACY_ANALYSIS=true` is for isolated compatibility tests only and bypasses process isolation.

Inputs are removed after successful, failed or cancelled work. A machine crash can leave files in the operating system's `mediatruth_uploads`/`mediatruth_worker_*` temporary directories. With the server stopped, review and remove only these application-owned temporary files. Do not run cleanup against original-media directories. Pending jobs are not durable; run **one** Uvicorn worker, with no multi-instance deployment.

Stored reports omit heatmaps. The database allows 50 saved reports per owner in a rolling day and a 512KiB report payload. This limits saved reports, not failed-analysis attempts. Request/queue bounds also apply. Monitor database usage; these limits do not guarantee staying within provider capacity indefinitely.

## Database and retention

Applied migrations: initial private schema, atomic reports, restricted profile trigger. Live checks passed for owner isolation, anonymous reads, transactional failure, RPC permissions and same-ID retries. No test accounts or reports were retained. Supabase security advisor returned no findings after remediation of [trigger function access](https://supabase.com/docs/guides/database/database-linter?lint=0028_anon_security_definer_function_executable).

Retention is **manual**, never an unattended deletion. The service-role-only `prune_expired_reports(p_before)` rejects cutoffs newer than 30 days. Back up and review the cutoff before invoking it. Owner account deletion leaves ownerless reports private; a retention decision is needed for these records.

Before schema changes, take a PostgreSQL custom-format backup with `pg_dump` using the provider's database connection details and a local password file or environment variable. Keep backups encrypted and outside Git. The application server key is not a PostgreSQL password. Back up Auth separately as needed; public-table backups alone do not restore user identity.

Rehearse restore into an empty local PostgreSQL/Supabase environment, never the live project: apply schema, restore data, compare counts and repeat two-owner/anonymous isolation and RPC rollback checks. Auth-linked IDs must match. No backup/restore rehearsal has been performed yet because database connection credentials are unavailable.

## Verification and limits

Run backend tests with `python -m pytest tests -q`, then `ruff check .` and `pip-audit`. Frontend checks: `npx tsc --noEmit --incremental false`, `npm run build`, `npm audit`. CI uses locked dependencies and blocks lint/security failures. The test client emits one upstream httpx deprecation warning.

Observed locally: backend tests, actual worker inference, subprocess timeout/cancellation, metadata export, frontend production build and type checking pass. Both dependency audits found no known vulnerabilities. Docker build, browser E2E, live email auth and server-key-backed API flow remain unverified.

C2PA inspection uses [the official SDK's offline configuration](https://github.com/contentauth/c2pa-python/blob/main/docs/context-settings.md). Trust is evaluated against SDK anchors with no live revocation lookup. Signed provenance is not proof that the depicted scene is truthful. Absence of credentials is not proof of authenticity. Export removes ordinary metadata; it does not guarantee removal of invisible watermarks, pixel-level AI signals or external copies.

The four legacy score fields remain uncalibrated heuristics. Do not use them as authentication, legal evidence, fraud decisions or proof of a particular editing tool. The remaining scientific gates are representative licensed data, generator/original-level splits, independent metrics, calibration, mixed edits and real video temporal/localization evaluation.
