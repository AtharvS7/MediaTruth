# Evaluation inputs

No accuracy benchmark has been claimed or completed. `backend/evaluation.py` validates the manifest and scores categorical predictions separately from software smoke tests.

Each JSONL manifest row requires `id`, relative `path`, `label`, `source`, `license`, `sha256`, `group_id`, and `split`. Labels: `original`, `ai_generated`, `ai_edited`, `traditional_edit`, `mixed`. Splits: `train`, `validation`, `test`. Keep the original, crops, recompressions, edits and video frames in one group/split. Include generator/tool/version and edit-mask metadata as additional fields where available. Merely writing a license label is not a legal review.

Prediction JSONL rows require `id` and `label`; `inconclusive` is allowed. Every test sample must have exactly one prediction; never omit failures. Run:

```sh
python backend/evaluation.py evaluation/data/manifest.jsonl evaluation/data/predictions.jsonl
```

The report includes per-class precision/recall, confusion, original-image false-positive rate, abstention coverage and Wilson confidence intervals with release gates. Abstentions reduce recall. Calibration, localization quality and unseen-generator evaluation still require additional work. Treat raw detector scores as uncalibrated.

Dataset acquisition and model license review remain pending. Use the primary dataset sources listed in `UPGRADE_PLAN.md`; ordinary internet images without documented provenance are not ground truth. Download only subsets with suitable terms. Data and generated reports are ignored by Git.
