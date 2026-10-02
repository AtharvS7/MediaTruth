# Calibration iteration, 2 October 2026

Goal: reduce FSD's real-photo false positives without optimizing the prior 35-image
diagnostic set. Threshold calibration is the first adjustment; neural weights are
not yet being fine-tuned. Weight training needs a larger, suitable training corpus.

The predeclared pilot uses 24 originals and 24 generated images for calibration,
plus 24 originals and 24 generated images for holdout. Selection is a deterministic
shuffle of source offsets, independent of detector scores. Original decoded-pixel
hashes prevent exact cross-partition duplicates. They do not prove independence.

Source: [Tiny-GenImage](https://huggingface.co/datasets/TheKernel01/Tiny-GenImage),
revision `89c4fe9efd0ebc7ce5c7641ef57d578ccd639c69`, CC-BY-NC-SA-4.0 according
to the dataset card. The card describes a derived Kaggle/GenImage subset; underlying
rights and pretrained-model overlap remain unverified. Use is local research only.
Source train rows become calibration (`validation`); source validation rows become
our untouched `test` partition. Viewer image representations are used, not claimed
to be byte-identical to the original archives. Failures and partial downloads are
recorded; the experiment refuses incomplete/unbalanced partitions.

Acquisition completed: 96 images, with 24 per class in each partition. Recorded
manifest hashes, generator counts and acquisition failures are in
`calibration-data-20261002.json`. No cross-partition dHash candidates were found
at Hamming distance <=3; this screening does not verify parent independence.

The first download stopped after repeated HTTP failures. It is preserved as
`evaluation/data/tiny-calibration-20261002`. The second attempt uses bounded retries,
honors Retry-After and paces viewer requests. Both data and raw reports are ignored.

Procedure:

1. Verify all content hashes; score calibration data using the unchanged FSD model.
2. Select the threshold maximizing calibration recall with empirical false-positive
   rate <=1%. Break ties toward fewer false positives and a stricter threshold.
3. Save the policy and source-report digest **before** holdout inference begins.
4. Compare default and frozen thresholds on holdout source bytes and JPEG quality 85.
5. Count failures/abstentions as missed classifications. Report balanced accuracy,
   per-class precision/recall, false positives and intervals against the 95% target.
6. Keep release eligibility false: 24 originals per partition cannot validate a 1%
   false-positive rate, and this pilot cannot establish production accuracy.

Run from the repository root:

```text
python backend/fetch_calibration_pilot.py evaluation/data/tiny-calibration-20261002-v2 --per-class 24 --resume
python backend/run_calibration_experiment.py .tools/fsd-repro .tools/accuracy_sources/fsd_source/weights evaluation/data/tiny-calibration-20261002-v2 evaluation/reports/calibration-20261002 --threads 4
```

Use `--resume` for acquisition only after an initial run has saved both manifests.
The experiment resumes matching inference checkpoints automatically. Its status
is in `evaluation/reports/calibration-20261002/status.json`; per-image checkpoints
are saved beside reports. Keep the PC awake. Restarting the same command resumes
completed samples without changing the model, partition or frozen threshold.

Expected CPU cost is several hours for 144 image evaluations (48 calibration,
48 original holdout, 48 JPEG holdout). Four-thread smoke inference preserved the
two-thread score within 4.1e-11. No paid service or external upload of user media is used.

The local run has started. No calibrated accuracy improvement or production
qualification is claimed until its comparisons are complete and reviewed.
