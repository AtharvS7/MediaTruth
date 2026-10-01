# SafeIMG pipeline pilot

Source: [SafeIMG by Yi-Zhi Wang and colleagues](https://huggingface.co/datasets/Snowstorm1492/SafeIMG).
License: [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/).
Use is limited to non-commercial research. All samples are synthetic images;
they must not be presented as real events or records.

The downloader takes 12 evenly spaced rows by default, capped at 48, with an
8 MB maximum per image. It records hashes, source revision, row IDs and the
dataset card. It uses the dataset viewer's encoded representation; byte identity
with original source image files is not claimed. Media and reports stay in ignored
local directories, not Git. The source annotation `image_level_judgment` is not
used as a real-versus-AI label: the authors describe the entire set as synthetic.

From backend:

```text
python fetch_evaluation_pilot.py ../evaluation/data/safeimg-pilot --count 12
python run_evaluation_pilot.py ../evaluation/data/safeimg-pilot/manifest.jsonl ../evaluation/reports/safeimg-pilot
```

Use new destination directories for each run. The runner invokes the actual
isolated image pipeline serially, with remote inference and model downloads
disabled, and records reports plus abstention metrics. It makes no database writes.

This only tests the public pipeline on a small set from one generator. Public
verdicts are currently withheld, so abstention is expected. It is not a benchmark
of raw detector discrimination. There are no original photographs, AI edits,
conventional edits, mixed workflows or videos in this pilot. Parent independence
is unverified. It cannot pass the release gates or establish detection accuracy.

Completed 1 October 2026: all 12 samples processed successfully through the actual
isolated pipeline. All 12 abstained, coverage was 0%, and no category passed its
release gate. Source revision: `389a7c555191c9e946727a470500fcd9b045381c`.
Aggregate results are in `safeimg-pilot-metrics.json`; raw reports and media remain
local. This result verifies current withholding behavior, not a useful detector.

The next evaluation dataset must include licensed original-media controls and all
target classes, verified parent groups, calibration and independent held-out
splits, several generator families, and compression/re-encoding variants.
