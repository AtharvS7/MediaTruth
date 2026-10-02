# FSD plus Community Forensics experiment, 3 October 2026

Hypothesis: FSD residual statistics and Community Forensics' learned visual
features make different errors; a small regularized combiner may improve the
tradeoff between real-photo false flags and missed generated images.

Predeclared configuration: two features (-FSD z score clipped to [-50,50] and clipped Community
Forensics log odds), standardized using calibration only; logistic regression,
L2 penalty 0.1, 2,000 full-batch gradient steps, learning rate 0.05, zero initial
weights. Fit on the existing 48 calibration images only. Decision threshold is
0.5, fixed before scoring. No hyperparameter search on holdout results.

Compare with the preserved FSD baseline on source and JPEG-85 representations,
and the prior modern-generator diagnostics. These are now development comparisons,
not fresh independent validation. Store coefficients, scaler, model identities,
calibration hashes and every failure. If either feature is unavailable, abstain.

No production activation. A successful development result would require a new
locked, representative validation set, reviewed parent/training overlap, supported
license, robustness checks and operational validation under PRODUCTION_TARGET.md.

## Completed result

The frozen combiner scored **43/48 (89.6%)** on source representations and
**44/48 (91.7%)** after JPEG-85 recompression. Source-image false flags fell from
one to zero, but AI misses rose from three to five. It therefore did not improve
the target tradeoff overall and is rejected for promotion. FSD remains the
research baseline. Coefficients, report hashes, metrics and per-image predictions
are preserved in `fusion-results-20261003.json`.

The next model-training iteration needs broader, reviewed training/calibration
data covering these failure types and a fresh locked validation set. Do not
keep altering this combiner until the already-inspected development set reaches 95%.
