# Editing evaluation contract and candidate review — 3 October 2026

Implemented: `backend/edit_evaluation.py` evaluates supplied predictions against
paired source/output images, declared edit histories and binary masks. This is
benchmark infrastructure, **not a validated editing detector**. Public verdicts
remain withheld. There are no new model weights, datasets or accuracy results.
The user's revised strictly-above-90% classification target is not established
by these software tests; localization needs its own predeclared acceptance rule.

## Run

From `backend`, using the existing Python environment:

```powershell
../.venv-upgrade/Scripts/python.exe edit_evaluation.py ../evaluation/data/edits/manifest.jsonl ../evaluation/data/edits/predictions.jsonl --threshold 0.5
```

These paths illustrate the required inputs; no such dataset is bundled. Choose
the threshold using calibration data before opening test masks. The CLI never
fits a threshold, flips a map to improve its score, resizes a prediction, or
excludes difficult border pixels. Consequently its numbers are not directly
comparable with benchmarks that use those conventions. Scores are not calibrated
probabilities. Save stdout as the experiment report; input hashes are recorded.

## Dataset format

Use the base manifest fields in `evaluation/README.md`, with labels restricted to
`original`, `ai_edited`, `traditional_edit`, and `mixed`. Each row also requires:

```json
{
  "original": {
    "path": "originals/example.png", "sha256": "<64 lowercase hex characters>",
    "source": "<documented source>", "license": "<documented rights>"
  },
  "mask": {"path": "masks/example.png", "sha256": "<sha256>"},
  "edit_history": [
    {
      "kind": "ai", "tool": "<tool>", "version": "<version>",
      "operation": "<documented operation>",
      "input_sha256": "<original sha256>", "output_sha256": "<output sha256>"
    }
  ]
}
```

All artifact paths are relative to the manifest directory and must stay inside
it. All source/output/mask bytes are hash checked. A grayscale binary mask uses
0 for pristine and 1 or 255 for edited pixels, in the stored output raster's
coordinates (no automatic EXIF rotation). Edited masks must be nonempty; original
masks must be empty. Mask scope is the union of substantive edits. It does not
attribute individual pixels to AI versus conventional editing.

History steps must chain from original hash to final output hash. `ai` and
`traditional` denote substantive edits; `mixed` requires both. `delivery` denotes
documented export/recompression, which does not itself change attribution.
An untouched original has an empty history and the same original/output hash.
Intermediate hashes are lineage assertions, not checked intermediate files.
The same original/intermediate/output content cannot appear under distinct group
IDs; related variants must share a group and split. Donor-image lineage, disguised
near-duplicates, truthful histories, mask quality, rights and independence still
need independent review. Do not infer histories from image differences or metadata.

## Predictions and metrics

Provide exactly one JSONL prediction for each test row:

```json
{"id":"example","label":"inconclusive","score_map":{"path":"maps/example.npy","sha256":"<sha256>"}}
```

Use `score_map: null` for an explicit localization abstention. Attribution may
abstain independently of localization. Maps must be numeric, finite [0,1] NumPy
arrays of exact output dimensions; pickle loading is disabled. Map paths are
relative to the predictions file and hashes are checked.

- Attribution: existing per-class precision/recall, confusion, coverage, and
  false-positive rate on originals. Abstentions reduce recall.
- Localization: per-image IoU and Dice, averaged separately for each edit class.
  An abstention contributes zero for an edited image, not an omitted denominator.
- Originals: separate false-positive pixel area and any-false-positive-image rate
  over available maps, with available counts. Missing maps never receive clean
  credit. Empty original masks are excluded from edit IoU/Dice.
- Per-image results and unique group count support later grouped analysis.
  Related variants are not independent samples, and these averages contain no
  population confidence interval or release gate. `deployment_approved` is false.

## Pretrained candidates: primary-source review

**TruFor:** upstream provides CPU inference (`-g -1`), anomaly maps, a reliability
map and an image score. The official release is a ZIP containing `trufor.pth.tar`,
with an MD5 value documented. No safetensors release is documented there. Its
evaluation uses inversion/border conventions that differ from this contract.
[Official inference instructions](https://github.com/grip-unina/TruFor/blob/main/TruFor_train_test/README.md).

The license restricts usage to informational/nonprofit purposes and disallows
unauthorized industrial/profit-oriented activities. Zero spending does not itself
establish that the intended use qualifies. The checkpoint code calls `torch.load`
without an explicit `weights_only` argument. A future adapter must use a current
PyTorch, explicit restricted loading, pinned source/weight hashes, tensor-key/shape
validation and no unrestricted-pickle fallback. No weight size or local CPU
latency/memory measurement was verified; nothing was downloaded.
[License](https://github.com/grip-unina/TruFor/blob/main/TruFor_train_test/LICENSE.txt),
[loader](https://github.com/grip-unina/TruFor/blob/main/TruFor_train_test/test.py).

**IML-ViT:** repository code carries MIT terms. The README links separate Google
Drive/Baidu pretrained checkpoints, conventionally named `.pth`, and documents an
older CUDA environment. The model defaults to 1024-pixel input and a 12-layer,
768-dimensional transformer. CPU practicality is therefore unmeasured here;
free access to code does not establish a usable zero-cost serving configuration.
The reviewed pages did not separately establish external checkpoint/data rights,
checkpoint sizes, or safetensors availability. No files were downloaded.
[Code license](https://github.com/SunnyHaze/IML-ViT/blob/main/LICENSE),
[checkpoint instructions](https://github.com/SunnyHaze/IML-ViT/blob/main/README.md),
[model definition](https://github.com/SunnyHaze/IML-ViT/blob/main/iml_vit_model.py).

**Next concrete integration option:** a research-only TruFor adapter can export
the upstream anomaly map into this `.npy` prediction contract while leaving
attribution `inconclusive`. It must wait for intended-use rights review, an exact
checkpoint size/integrity check, restricted-load compatibility, and a bounded
single-image CPU trial. IML-ViT is the alternative after external weight rights
and CPU viability are established. Neither localizer alone distinguishes AI,
conventional and mixed editing histories.

Task completion still requires reviewed paired originals/edit histories/masks,
representative independent calibration and locked holdouts, a validated attribution
model or authenticated edit provenance, fixed localization acceptance criteria,
and measured robustness/false alarms. Synthetic unit fixtures validate only this
evaluator's arithmetic and input checks. Do not report their perfect masks as
detection accuracy.
