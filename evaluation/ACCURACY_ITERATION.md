# Accuracy iteration: 2026-10-02

Goal: improve AI-generated image sensitivity without falsely accusing real-photo
authors. User-approved scope is accuracy; cloud replacement and backup work are deferred.

Baseline: CNNDetect flags 0/12 SafeIMG pilot samples at its unchanged 0.5 threshold.
This pilot has no real controls and is not a release test.

Candidates selected before looking at their pilot scores:

- OwensLab/commfor-model-224: compact 21.7M-parameter Community Forensics ViT.
- wkaandemir/ai-image-detector: CLIP ViT-B/16 with merged adaptation, trained on
  newer generators. Its sigmoid represents real images, requiring explicit inversion.

Download pinned weights; verify SHA-256; use safetensors or tensor-only
`torch.load(weights_only=True)`, strict state loading and reviewed local inference
code. No unreviewed remote Python execution or paid inference.
Keep each candidate's own preprocessing. Record CPU time and model identity.

First experiment: fixed upstream decision rules on the existing SafeIMG error
slice and a bounded Community Forensics evaluation subset containing real controls
and multiple generators. Do not fit thresholds to these evaluation results.
Label source, source revision, sample bytes and parent grouping must be recorded.
The public benchmark may have influenced the authors' model selection; it is not
a fresh independent release holdout. Use research-only datasets locally and publish
aggregate scores and source attribution, not image bytes.

Promotion still requires the existing release gates (at least 200 independent
test examples per enabled class and 200 originals, precision >= 0.90, precision
lower 95% bound >= 0.85, original false-positive upper bound <= 0.05, recall >= 0.50),
plus verified licensing, independent calibration/holdout provenance and robustness.
Never equate a binary AI-generation detector with validated editing attribution,
video detection or proof that an image is authentic. Fallback stays inconclusive.

## Exploratory findings

Per-image scores, source hashes, recomputed release gates and parity evidence are
preserved in [accuracy-results-20261002.json](accuracy-results-20261002.json).
No candidate passes. All intervals are descriptive because parent independence
has not been verified.

After the initial two candidates failed the modern-generator pilot or real-photo
controls, follow-up experiments added Community Forensics 384, B-Free and FSD.
This is adaptive model selection on a diagnostic set, not independent validation.
All thresholds stayed at their respective published rules.

| Model | GPT Image 2 detected / 12 | Other generated detected / 14 | Real falsely flagged / 9 |
|---|---:|---:|---:|
| CNNDetect baseline | 0 | 0 | 0 |
| Community Forensics 224 | 2 | 11 | 0 |
| Community Forensics 384 | 1 | 11 | 0 |
| Modern CLIP candidate | 8 | 11 | 8 |
| B-Free | 1 | Not tested | Not tested |
| FSD (streaming CPU research) | 12 | 13 | 2 |

Modern CLIP is rejected for its real-photo false positives. Community Forensics
improves on the legacy baseline on this small multi-generator slice, but still
misses most GPT Image 2 examples. None is approved for production verdicts.
Zero false positives among nine originals is insufficient evidence of a low
population false-positive rate.

B-Free's memory-bounded adapter matches four official reference fixture logits
within 0.000028; implementation parity does not imply detection accuracy.

### Dataset limitations

- SafeIMG: 12 GPT Image 2 images, dataset revision
  `389a7c555191c9e946727a470500fcd9b045381c`; dataset-viewer representations;
  no original-photo controls; parent independence unverified.
- CommunityForensics-Eval: revision `7d4a74a88d2cac93b513c0853bf92c260eaceea0`.
  A predeclared systematic sample requested 96 rows. Only 23 were acquired;
  73 requests failed. The resulting 14 generated and nine real images are
  incomplete and potentially biased. Original decoded bytes were preserved.
- Both datasets carry CC-BY-NC-SA-4.0 terms. Media stays local and is not
  redistributed. Research results do not establish commercial-use eligibility.
- Unique filenames or hashes are no longer accepted as proof of independent
  observations by the release checker; explicit reviewed provenance is required.

### Reproduction

`backend/fetch_candidate_weights.py` downloads the three pinned safetensors
candidates. `backend/benchmark_generation.py` accepts a candidate, local weights,
verified manifest and new report path. `--jpeg-quality 85` evaluates recompression
as a paired robustness variant; variants must never inflate independent support.
Model identifiers and hashes live in `generation_candidates.py`.

B-Free is nonprofit-only; its original license is retained in
`backend/inference_pipeline/licenses/BFREE_LICENSE.txt`. Its weights are from
the authors' BFREE_dino2reg4 archive, not the Hugging Face downloader. FSD remains
a separate local research experiment. It detected all 12 GPT Image 2 pilot samples,
but two of nine originals were falsely flagged at its unchanged -2.0 threshold.
Its 35-image CPU run took 1,613 seconds (46 seconds/image on average).
It is not approved for production verdicts. Reproduction instructions, source
patch, license and artifact hashes are in `experiments/README.md`.
