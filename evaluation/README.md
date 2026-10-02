# Evaluation inputs

Exploratory model comparisons are documented in `ACCURACY_ITERATION.md`; no independent accuracy validation has passed. `backend/evaluation.py` validates the manifest and scores categorical predictions separately from software smoke tests.

Each JSONL manifest row requires `id`, relative `path`, `label`, `source`, `license`, `sha256`, `group_id`, and `split`. Labels: `original`, `ai_generated`, `ai_edited`, `traditional_edit`, `mixed`. Splits: `train`, `validation`, `test`. Keep the original, crops, recompressions, edits and video frames in one group/split. Include generator/tool/version and edit-mask metadata as additional fields where available. Merely writing a license label is not a legal review.

Prediction JSONL rows require `id` and `label`; `inconclusive` is allowed. Every test sample must have exactly one prediction; never omit failures.

Release gates additionally require `independence_verified: true` for every test
sample, assigned only after reviewing parent identity and split provenance.
Unique filenames or hashes alone do not establish independence. Public pilot
data with unverified parents must leave this false or absent.

Run:

```sh
python backend/evaluation.py evaluation/data/manifest.jsonl evaluation/data/predictions.jsonl
```

The report includes per-class precision/recall, confusion, original-image false-positive rate, abstention coverage and Wilson confidence intervals with release gates. Abstentions reduce recall. Calibration, localization quality and unseen-generator evaluation still require additional work. Treat raw detector scores as uncalibrated.

Representative release datasets and commercial model eligibility remain pending.
The new calibration experiment is described in `CALIBRATION_ITERATION.md`; the
95% acceptance target and planning completion estimate are in `PRODUCTION_TARGET.md`.
Use documented primary sources; ordinary internet images are not reliable ground
truth. Local media and generated reports are ignored by Git.
