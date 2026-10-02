# Remaining release targets — 3 October 2026

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

1. **Validated still-image detection:** meet the predeclared >=95% balanced
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

The FSD/Community Forensics combiner is implemented and tested only as a research
candidate. It uses calibration-only fitting and preserves the baseline. Its
development evaluations must be reviewed before any further training decision;
neither repeated tuning on these images nor a small high score qualifies release.
