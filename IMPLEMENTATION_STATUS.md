# Approved completion plan: implementation record

Updated 1 October 2026. Budget INR 0; non-commercial research release.

## Current work after PC-worker decision

- User chose to retain the temporary PC worker; cloud replacement is deferred.
  CLOUD_OPTIONS.md records additional candidates and their unresolved constraints.
- Added failure-case tests for tampered/oversized/malformed worker inputs, export
  cancellation, storage credential separation, offline admission, cleanup failure,
  and export retention. Fixed download expiry to reject new links after 24 hours
  even when cleanup has not run. Previously issued URLs can remain valid for their
  remaining lifetime (at most two minutes).
- Cloud processing readiness now checks worker availability through the database
  and returns 503 on failure, with a bounded wait. Liveness stays independent.
- Backend suite: 145 tests passed; Ruff passed.
- Commit `adba43e` passed all GitHub CI jobs and was deployed to Render. Hosted
  capabilities and readiness confirmed the restarted PC worker online.
- Both Linux container images built successfully. Non-root backend execution,
  ML imports, credential-file exclusion, HTTP serving, PNG pixel preservation,
  isolated image analysis with networking disabled, and three frontend auth
  browser checks passed. The Linux analysis fixture used no bundled model weights;
  validated trained-model deployment remains a separate gate. Temporary test
  containers were stopped and removed; the authorized PC worker remains running.
- Added bounded, licensed SafeIMG pilot acquisition and actual isolated-pipeline
  evaluation commands. This is not representative accuracy validation; see
  evaluation/PILOT.md for scope and missing data classes.

## Implemented and verified

- Supabase server key and Hugging Face token authenticated successfully. Misplaced HF token moved to HF_TOKEN; USE_HF_API=false. Startup validates boolean settings without echoing secrets.
- Private Supabase job bucket (50,000,000 bytes/object) and service-only media_jobs table. Atomic reservation, idempotency conflict checks, capacity limits, owner isolation, expiring worker leases and one retry after worker loss.
- Direct private upload/finalization, owner-scoped progress/cancellation, separate worker authentication, signed input/output URLs, transactional report completion, retryable cleanup.
- Live smoke test passed using temporary confirmed users: password login, signed upload, duplicate reservation, isolation, real isolated PNG cleaning and report saving. All temporary accounts and files removed. This does not test confirmation/recovery email delivery.
- SQL transaction tests passed for lease fencing, concurrent claims, duplicate completion, access denial and single report creation. Fixture transaction rolled back.
- Report schema v2 withholds all unvalidated verdicts. Provenance stays separate; legacy numeric fields are zero placeholders, not probabilities. No category is independently validated yet.
- Evaluation CLI now reports Wilson confidence intervals and the approved support/precision/recall/false-positive gates. Repeated parent groups cannot pass independence checks. Metrics do not approve model licenses or enable deployment automatically.
- Bounded video sampling combines uniform timestamps and scene histogram changes. This is not a temporal manipulation detector or face tracker.
- Frontend uses capabilities-driven limits and cloud signed uploads. Cloud maximum is 50 MB for both images and videos. Metadata export uses the durable worker in cloud mode.

## Hosting constraint discovered during implementation

The HF account AtharvS7 has no Pro subscription or existing Spaces. Docker/CPU Space creation requires a paid account under current terms. The user selected checking free ZeroGPU; the API rejected Gradio ZeroGPU creation with HTTP 402 (account not eligible). No Space or paid resource was created. Sources:

- https://huggingface.co/docs/hub/spaces-overview
- https://huggingface.co/docs/hub/spaces-zerogpu

Render workspace confirmed: My Workspace. Vercel team discovered: Atharv Sawane's projects. Hosting deployment is separate from functional inference availability. Do not silently replace the blocked worker with paid infrastructure.

The user approved a temporary PC worker after the ZeroGPU rejection, while continuing research into free cloud alternatives. The PC worker polls actual queued work every 60 seconds and needs no inbound network port. Start it explicitly with `python -m services.remote_worker` from backend; stop with Ctrl+C. Its separate `worker.env.local` holds only the backend URL and worker secret. Polling consumes the shared Render free instance allowance while running.

Current checks: **145 backend tests passed**, signed-URL live smoke passed, Ruff passed, TypeScript passed; production frontend build passed. Added admission limits: 100 jobs globally/day, estimated 2 GB transfer reservations/month, 400 MB database stop threshold. Provider usage must still be monitored because repeated signed downloads are not fully controlled by these reservations.

## Remaining acceptance gates

1. Replace the working, user-approved temporary PC worker with eligible free cloud compute. Vercel/Render deployment and hosted upload-to-report/export journeys passed.
2. Real email confirmation/recovery. The user corrected deployed auth redirects; mobile keyboard password login, export download and saved-history browser journeys passed.
3. Licensed representative datasets and actual benchmark runs; calibrated model selection and license review. No measured accuracy is claimed.
4. Validated AI-edit/conventional-edit/mixed classification, actual localization models and temporal/face video models. These capabilities remain withheld.
5. Backup/restore rehearsal, operational metrics and provider capacity monitoring. Basic container runtime checks passed; trained-model container performance/load tests remain. Pending jobs survive process restarts; recovery still needs an available worker and a real request to wake it.
6. Further queue tests for quota exhaustion, cancellation races, malformed stored media and storage cleanup failures.

## Reproducible checks

From backend, use the workspace's ../.venv-upgrade/Scripts/python.exe:

- `-m pytest tests -q` (live smoke is not auto-collected).
- `-m ruff check .`
- `tests/live_durable_smoke.py` (explicit cloud fixture mutation and cleanup, no email).
- `evaluation.py manifest.jsonl predictions.jsonl`

SQL fixture: run supabase/tests/durable_jobs.sql inside BEGIN/ROLLBACK against an isolated empty queue. Do not run it against active user jobs: claim operations intentionally act on the queue.

## Operation and rollback

JOB_BACKEND defaults to local for compatibility. Set it to supabase only with the applied migrations, private bucket and WORKER_SECRET. A worker URL is optional for the polling PC worker. WORKER_SECRET is a new random secret stored in ignored backend/.env, distinct from all provider keys. Worker needs only MEDIATRUTH_API_URL and WORKER_SECRET; never supply a Supabase service key.

`uvicorn services.remote_worker:app --host 127.0.0.1 --port 7860` runs the worker endpoint on a suitable host. For a PC without inbound routing, use `python -m services.remote_worker` from backend. No automatic startup or background scheduling is installed. See OPERATIONS.md for deployed URLs, worker lifecycle and verified versus pending checks.

Terminal inputs are deleted on the next cleanup pass. Export downloads expire after 24 hours; signed upload URL lifetime requires a second sweep for late abandoned uploads. Cleanup retries on actual job traffic; no always-on scheduler or keep-alive pings are used. Original media can remain past 24 hours while all services are asleep; the next pass removes it.

Rollback application commits, retaining additive private tables and existing reports. Disable new cloud submissions before rolling back. Never re-enable public database policies or discard pending uploads silently.
