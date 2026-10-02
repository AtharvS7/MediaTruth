# FSD pilot checkpoint: 91.7%, research only

Completed 2 October 2026 at 21:54 IST. This preserves actual reports, fitted policy,
model identities and hashes; it contains no media or model binaries.

| Evaluation | Correct | Accuracy | AI recall | Real false flags |
|---|---:|---:|---:|---:|
| New holdout, source representation | 44/48 | 91.67% | 21/24 (87.5%) | 1/24 |
| Same holdout, JPEG quality 85 | 44/48 | 91.67% | 21/24 (87.5%) | 1/24 |
| Earlier diagnostic set | 32/35 | 91.43% | 25/26 | 2/9 |

Both the unchanged -2.0 threshold and fitted -1.5486366817143395 threshold produce
the same holdout results. Calibration did **not** demonstrate an improvement.
91.67% versus 91.43% is not a like-for-like comparison: the images differ.
The two holdout variants represent 48 parent images, not 96 independent samples.

Production validation failed: insufficient independent support, inadequate AI
recall and uncertainty bounds, unresolved pretrained-data overlap and licensing
eligibility. The manifest explicitly leaves independence unverified. No app
verdict is enabled by this checkpoint. It is a reproducible research baseline,
not an enterprise deployment or a universal 91.7% accuracy promise.

`SHA256.json` verifies preserved report bytes. Full acquisition and reproduction
details are in `../../CALIBRATION_ITERATION.md` and `../../experiments/README.md`.
The same dataset cannot now be treated as untouched validation for an adaptively
selected replacement. Further candidate comparisons here are diagnostic; a fresh,
locked evaluation set is required for a new accuracy claim.
