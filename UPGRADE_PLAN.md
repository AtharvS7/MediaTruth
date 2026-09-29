# MediaTruth upgrade plan and task ledger

Updated 29 September 2026. Goal: assess AI generation, AI-assisted edits and conventional edits of photos/videos, with evidence and explicit uncertainty; provide a separate metadata-removal export. Budget: **INR 0**. This plan supersedes the completion claims in earlier planning documents for the new scope.

## Product contract

- Report origin, modification evidence and verified provenance separately. Mixed workflows can include both AI and conventional editing; do not force all cases into mutually exclusive classes.
- “No evidence found” is not proof of authenticity. Missing EXIF and smooth colors are not proof of AI generation. Unsupported or unavailable detectors must abstain.
- Metadata export produces a new copy with ordinary metadata removed. Do not promise removal of invisible watermarks, pixel artifacts, external records or every AI trace.
- Keep model name, revision, input transform, label mapping, score type, status, processing version and coverage with results. An uncalibrated score must not be sold as a probability.

## Architecture and INR 0 operating model

Keep Next.js, FastAPI, and Supabase Auth/PostgreSQL; avoid a paid queue or a second database provider. Run inference on an existing local machine initially, with one bounded worker and an eventual PostgreSQL job table. Local electricity/internet/hardware are assumed already available; no new service spend is authorized. Do not expose a development server directly as an enterprise service.

Supabase must be provisioned in a **Free organization with available free project capacity**, preferably the nearest available India region. Do not create it in a paid organization, upgrade hardware, add payment details or enable paid backups. Store report summaries, not large inline heatmaps or original media. Use quotas and retention to stay within free capacity; stop accepting work at limits.

[Supabase documents a 500MB free database allowance](https://supabase.com/docs/guides/platform/billing-on-supabase) and [possible inactivity pauses](https://supabase.com/docs/guides/platform/free-project-pausing). [Render free services sleep after inactivity](https://render.com/docs/free). Consequently INR 0 cannot promise an enterprise SLA or continuously available high-throughput video analysis. Existing `render.yaml` claims of free unlimited HF inference are unverified and must not guide capacity planning. No paid resource has been created in this milestone.

## Ordered tasks and acceptance criteria

| ID | Priority / status | Work | Acceptance / dependency |
|---|---|---|---|
| A1 | P0 Done | Audit code, training and deployment paths | Findings and evidence in `AUDIT_2026-09-29.md`; earlier work preserved. |
| A2 | P0 Done | Fix registry access, two-logit inference, malformed output and unsafe checkpoint loading | Regression tests; no silent random-head or unknown-label real verdict. |
| A3 | P0 Done | Neutral missing metadata, no-model abstention, video uncertainty and readiness fix | All-inconclusive video stays inconclusive; ordinary stripped photos are not flagged from absence alone. |
| A4 | P0 Done locally | Private ownerless scans/profile RLS and backend-only inserts | Schema/migration prepared; cloud policy tests still required. |
| F1 | P1 Done locally | Authenticated still-image metadata removal + UI/download | Chunk-level removal tests, alpha/orientation checks, size/animation/corruption rejection and cleanup. |
| C1 | P0 Done | Create fresh free Supabase project | Created free Mumbai project `yiqpqgxlujqcfeagsfff`; initial schema, atomic reports and trigger restrictions applied. Live owner/anonymous/transaction checks passed; security advisor clean. |
| C2 | P0 Waiting for server key | Configure real environment and auth | Backend URL + secret/service key, frontend URL + public/anon key; never expose backend key. Set callback URLs; test signup/login/reset/logout. Provider must issue credentials; random local strings are not valid cloud keys. |
| D1 | P0 Implemented; hosted CI/container build pending | Resolve and lock dependencies; enforce CI checks; container hardening | Fresh Python/Node installs pass; updated advisory review; no ignored lint/secrets failures; non-root containers and `.dockerignore`. |
| D2 | P0 Done; client resubmission deduplication pending | Atomic writes, result constraints and idempotency | One transaction stores summary and details; retries return existing scan; faults leave no partial records. Add unique scan result, score-range constraints and owner indexes. |
| D3 | P0 Local implementation done | Job/resource control | Bound pixel counts/frame dimensions/request intake/concurrency; validated decode; real progress; cancellation terminates work; rejected jobs clean temp files. Test overload and timeout races. |
| M1 | P0 Next | Versioned model registry and evidence schema | Same model IDs/transforms/labels across execution modes; pinned revisions and license review; typed evidence/status and score semantics. Keep third-party upload disabled by default. |
| M2 | P0 Harness done; representative data pending | Evaluation harness and ground truth manifest | Sources/licenses/hashes/labels/edit masks/parent group IDs recorded. Split by generator, original and video; prevent duplicates and train-test leakage. |
| M3 | P1 Pending M2 | Benchmark and choose models | Per-category precision/recall, false-positive rate on originals, abstention coverage, ROC/PR where applicable, calibration error and intervals; compare postprocessing robustness and unseen generators. No invented acceptance accuracy. |
| M4 | P1 Pending M2/M3 | Separate AI generation, local AI edits and conventional edits | Labeled paired originals/edits and masks; genuine localization model; mixed editing support. Replace unsupported ELA/DCT probability claims. |
| P1 | P1 Partial | Provenance inspection | Parse EXIF/XMP/IPTC and verify C2PA via supported SDK: signature, binding, trust and actions. Present present/valid/untrusted/invalid/absent distinctly; no substring-as-verification. |
| P2 | P2 Pending provider capability | Watermark inspection | Provider-specific supported verification only; “not checked” when unavailable; never imply absence from no detection. |
| V1 | P1 Pending model/evaluation baseline | Real video forensics | Adaptive bounded sampling, face tracks, temporal consistency, scene changes, original-container provenance and sampled-coverage reporting. Audio analysis is separately scoped. |
| U1 | P1 Implemented; browser E2E pending | Frontend truthfulness and accessibility | Per-detector unavailable states, inconclusive scores shown as unavailable, verified provenance panel, real job progress, unified upload limits, keyboard/mobile tests. |
| O1 | P1 Partial | Free-tier operations | Owner quotas, retention, redacted structured logs, error counters, schema backup/restore rehearsal, documented redeploy and rollback. No paid dependency or availability promise. |
| R1 | P0 Done | Verify and push first milestone | 113 backend tests passed; 53 focused tests passed after final cleanup; TypeScript and production build passed; diff/staged secret-pattern checks passed. Pushed `upgrade/forensics-audit-metadata-export` to the requested GitHub repository. Database/live accuracy not included in “verified”. |

## Data acquisition plan

Use sources with documented generation/edit labels; random web images are not reliable ground truth. Start with a small, licensed, balanced evaluation subset and increase only within local storage/compute limits.

- AI generation: [official GenImage benchmark](https://github.com/GenImage-Dataset/GenImage), with generator holdouts and later current-generator samples.
- Conventional edits/localization: [NIST OpenMFC](https://www.nist.gov/itl/iad/mltg/open-media-forensics-challenge), plus controlled transformations of originals with documented rights and masks.
- Face/video manipulations: [FaceForensics++](https://github.com/ondyari/FaceForensics); access requires an application and acceptance of its terms. Do not bypass access restrictions or assume research data is commercially licensed.
- AI edits: paired originals, inpainting/outpainting/generative-fill results, masks, tool/version and parameters. These are required in addition to fully synthetic images.
- Robustness: resizing, JPEG recompression, metadata removal, screen captures, crops, color changes and mixed workflows. Split related variants together. Generated demonstration images are smoke tests, not a representative accuracy benchmark.

No external dataset or model was downloaded for accuracy evaluation yet; no accuracy measurement is claimed. Current synthetic fixture images test software behavior only.

## Supabase provisioning runbook

1. Expose the Supabase MCP tools in a fresh/reconnected session, then list organizations/projects and confirm the selected organization is Free with spare capacity. No provider switch is required.
2. Create `mediatruth` in an available nearby region at no charge. Use provider-issued credentials. New project starts empty; do not delete or migrate the old project implicitly.
3. Run `supabase/schema.sql` once on a new database, followed by `20260930_atomic_reports.sql` and `20260930_restrict_profile_trigger.sql`. Existing installations instead use `supabase/migrations/20260929_private_records.sql`; it restricts access without deleting records.
4. Write keys directly to gitignored `backend/.env` and `frontend/.env.local` or hosting secrets, without printing them or committing them. See [Supabase API key documentation](https://supabase.com/docs/guides/getting-started/api-keys). Match SDK compatibility before switching to newer key formats.
5. Set `USE_HF_API=false` for local inference; configure exact local and deployed auth redirect URLs and CORS origins. `JWT_SECRET` is unused by this app and does not replace Supabase credentials.
6. Test two owners, anonymous reads/writes, signup profile trigger, account deletion privacy, insert failure and retry. Keep service credentials server-only. Record the new project ID and migration version, never secret values.

## Release and rollback

Publish the first milestone on a review branch because `render.yaml` auto-deploys main and the fresh database is not configured. Merge only after the environment/schema and dependency gates are resolved. Revert application changes by commit; do **not** restore public ownerless-read or unrestricted-insert policies. Back up schema and data before future destructive changes. Existing records remain private after this migration and require explicit ownership/recovery handling.

## Verification record

- Initial existing environment: tests could not collect because `slowapi` was missing. Installed the declared slowapi version and pytest-asyncio into the existing virtual environment.
- TypeScript `tsc --noEmit --incremental false`: passed.
- Expanded backend suite: **113 passed**, Python 3.12.2, existing local environment. Relevant tests rerun after final aggregation cleanup.
- Frontend `npm run build`: **passed**, including `/metadata`; used non-secret placeholder service settings for build validation. This is not a live login check. Only outdated Browserslist data warnings were emitted.
- Not executed: live Supabase migration/RLS checks, hosted inference, browser E2E, fresh dependency install, dataset accuracy or load benchmark.

First implementation commit: `8d491e0`. Branch: [upgrade/forensics-audit-metadata-export](https://github.com/AtharvS7/MediaTruth/tree/upgrade/forensics-audit-metadata-export). Main was not changed. Existing unrelated audit documents and generated TypeScript build information were preserved locally without adding them to this release.


## Second implementation milestone (29 September 2026)

- Supabase is connected and provisioned at **0/month**, in the user-selected Free organization. Project: `yiqpqgxlujqcfeagsfff`, Mumbai. Public configuration is written to local ignored environment files. Backend server key is pending from the user; the MCP only exposes publishable keys.
- Atomic RPC persists report and summary, validates digest/scores, limits report size, serializes owner quota checks and handles retries of the same scan ID. Live rollback, idempotency, cross-owner and anonymous denial checks passed inside a rolled-back fixture transaction. Trigger RPC access revoked following the security advisor; final advisor has no findings. This does not deduplicate two separate client submissions, each of which gets a new ID.
- Python 3.12 dependency graph resolves in a fresh environment, with `uv.lock` and hashed pip exports. Next upgraded to 15.5.26. npm and pip-audit reported no known vulnerabilities. CI now enforces lint, audits and secret checks. Docker files use non-root users and exclude secrets; actual Docker build remains untested.
- Added `/jobs`: one active inference process, two queued jobs, one unfinished job per owner; authenticated status and cancel. Workers have no inherited Supabase credentials and disable external inference/downloads. Timeout/cancel kills and reaps native work before source cleanup. Export shares the worker slot. Old synchronous analysis endpoints return 410 by default. **Single API process only; pending jobs are memory-only and lost on restart.** Saved reports persist. This is not a durable enterprise queue or an SLA.
- Upload intake limits actual streamed bytes and concurrent requests; images require matching format, valid headers, one frame and <=16MP. Video analysis caps at 20 resized frames with serial per-frame processing. Native decoders remain an attack surface; no claim of full OS sandboxing or complete video coverage.
- Auth uses PKCE code exchange and a new password-update page. Model downloads are opt-in. The existing CNNDetect wrapper checkpoint now loads safely; real worker smoke inference passed. Scores remain experimental and the smoke fixture is not an accuracy benchmark.
- Offline C2PA SDK checks produce distinct status and action evidence, with remote manifests/OCSP fetching disabled. Missing credentials and unchecked invisible watermarks are explicit. EXIF/PNG/XMP software claims remain unverified. Signed/tampered/trust-chain fixtures and complete IPTC support are still needed before claiming full provenance validation coverage.
- Evaluation manifest validator rejects duplicate content, hash mismatch, path escapes and related-image split leakage. Metrics include abstention coverage, per-class precision/recall, confusion and original-image false positives. Representative licensed test media, masks, generator holdouts, calibrated thresholds and model/license review remain pending.
- See `OPERATIONS.md` for startup, auth redirects, backup/restore and remaining release gates. No production merge or paid deployment was performed.

Second milestone verification: **122 backend tests passed**, Ruff passed, npm audit reported zero vulnerabilities, and pip-audit reported no known vulnerabilities in the fresh Python environment. Next.js production build and TypeScript checks passed. Six job tests include real process timeout/cancellation and an upload-to-persistence integration check. Browser tooling reported no available browser, so dashboard redirect configuration and browser E2E were not performed.
