# Remaining release targets - 3 October 2026

Planning completion remains **approximately 65%**, using the explicit 64/100 rubric
in `evaluation/PRODUCTION_TARGET.md`. Detection accuracy is a different metric.
Finishing research experiments without passing their gates does not justify a
large increase in project completion.

## Current checkpoint

`evaluation/checkpoints/fsd-pilot-20261002` preserves the 91.7% FSD research result.
Both original and JPEG-85 variants scored 44/48. Calibration did not improve the
score. Earlier diagnostics remain 32/35 (91.4%) on different images. These are
not production certification or evidence that every upload is 91.7% reliable.
No public verdict was enabled. Application infrastructure remains implemented.

## Release targets, in priority order

1. **Validated still-image detection:** meet the revised >90% balanced
   accuracy, precision/recall and uncertainty checks; measure failures and
   false-positive rates. The current AI recall is 87.5% on the new holdout.
2. **Fresh representative data and rights:** at least 200 verified independent
   examples per enabled class, separate training/calibration/locked validation,
   unseen generators, original-photo sources and common postprocessing. Review
   source/model licensing and pretrained-data overlap; research permissions are
   not automatic commercial deployment permission.
3. **Editing attribution and localization:** validate AI edits, conventional edits
   and mixed workflows using paired originals, edit histories and masks. A binary
   generation score does not provide these capabilities.
4. **Advanced video detection:** add and validate temporal/face analysis on labeled
   videos. Bounded frame sampling alone is insufficient.
5. **Authentication delivery:** verify actual email confirmation and password
   recovery journeys, beyond password login and redirect/browser checks.
6. **Recovery:** resolve the deferred PostgreSQL connection issue and run a
   backup/restore rehearsal with isolation and recovery verification.
7. **Operations:** trained-model load/performance tests, monitoring/alerts,
   provider-capacity checks and failure/recovery exercises. CI and functional
   tests do not establish an enterprise availability guarantee.
8. **Continuous compute:** retain the user-approved temporary PC worker for now.
   Always-available production processing needs an eligible replacement or an
   explicit operating-hours limitation. This cloud decision remains deferred.

Metadata export removes supported ordinary metadata, not every watermark or
pixel-level AI trace. Provider-specific watermark verification remains dependent
on supported provider capabilities; unavailable checks must remain explicit.

## Next accuracy experiment

The FSD/Community Forensics combiner was implemented, fitted on calibration only
and evaluated. It scored 89.6% on source images and 91.7% on JPEG copies, so it
was rejected for promotion. The next iteration needs broader training/calibration
data covering the observed failures and a fresh locked validation set. Neither
repeated tuning on these images nor a small high score qualifies release.

## Implementation update - 3 October

The user revised acceptance to strictly above 90%. The evaluator now records
that policy explicitly, retains 95% confidence intervals and rejects exactly
90% class recall. Historical checkpoint reports are unchanged. The reassessment
in `evaluation/target-reassessment-20261003.json` retains 44/48 correct, with a
95% Wilson interval of 80.4%-96.7%. All three BigGAN examples were missed. The
native GAN fallback also flagged zero of 24 generated examples and is rejected.
This is a reassessment of existing data, not fresh validation or model training.

Editing now has an offline paired-original/history/mask evaluator with leakage
and integrity checks; it does not supply a validated editing model. Video now
has bounded adjacent-frame optical-flow diagnostics with explicit coverage and
failure reporting; these measurements do not influence public verdicts. See
`evaluation/EDITING_EVALUATION.md` and `evaluation/VIDEO_TEMPORAL_DIAGNOSTICS.md`.

Database-dependent recovery work remains deferred pending a working Session
Pooler `SUPABASE_DB_URL`. No credential changes are included in this update.

Verification for this update: 220 backend tests passed; changed Python files
passed Ruff. These are software checks, not 220 independent detection samples.

Further model work is recorded in `evaluation/MODEL_VALIDATION_PROGRESS.md`:
TruFor CPU integration and a 12-pair localization pilot (insufficient results),
MesoNet CPU/parity verification (independent video data still access restricted),
and a frozen 375-image background evaluation with the missing SD1.4 stratum
explicitly recorded. Latest implementation verification: 241 backend tests and
full backend Ruff passed. These experiments do not close the release gates yet.
