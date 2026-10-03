# Frozen image validation wave - 3 October 2026

Goal: measure the frozen FSD baseline on fresh-to-this-project examples after
the observed BigGAN blind spot. This is validation research, not model fitting
or independent commercial release certification.

Before acquisition or inference: select 200 originals and 25 examples from each
of eight generators (400 total), using fixed shuffled 100-row pages from the
pinned Tiny-GenImage source validation partition. Exclude all prior local pilot,
calibration and test manifest IDs, bytes and decoded pixel hashes. Do not select
or discard examples based on model outputs. Acquisition failure or missing
quotas must be reported rather than quietly changing the evaluation population.

Model: verified FSD v1.2.0 with the existing reviewed streaming implementation.
Use the frozen calibration threshold -1.5486366817143395 and also report unchanged
upstream -2 as the predeclared baseline. No fitting on this wave. Report accuracy,
balanced accuracy, class precision/recall, original false flags, abstentions,
95% intervals and every generator slice. Target remains strictly above 90% with
the existing support, independence and confidence checks. No automatic promotion.

Use at most two CPU inference threads and process one model at a time because
the current PC has only 8 GB RAM. Save per-image checkpoints for interruption
recovery. Score source representations first; robustness tests follow only if
the baseline passes, avoiding expensive variants of an already-failed model.

Dataset card: https://huggingface.co/datasets/TheKernel01/Tiny-GenImage
Revision: 89c4fe9efd0ebc7ce5c7641ef57d578ccd639c69
Source terms: CC-BY-NC-SA-4.0, with underlying/derived rights requiring review.
This source was used previously, model-training overlap is unknown, and viewer
images may be encoded representations. Exact pixel exclusion does not establish
semantic/parent independence. `independence_verified` remains false. A successful
wave therefore cannot alone certify general production accuracy.

No changes to Supabase, cloud workers, credentials or public verdicts are part
of this experiment. Model or threshold changes require a new future holdout.

## Additional frozen candidate, before wave inference

Calibration-only inspection found that its one BigGAN example has unusually
high FSD likelihood (z=0.528), above all 24 calibration originals (maximum 0.443).
We will also evaluate a two-sided outlier rule: AI if z is strictly below the
minimum or above the maximum calibration-original z. Fit using the existing
calibration partition only, save the bounds before any new-wave predictions,
and do not tune them using the old or new holdout. This has zero empirical
calibration false positives but unmeasured population FPR and only one positive
high-tail calibration example. This is an overfitting risk, not a success claim.
Compare all predeclared candidates transparently; selecting one on this wave
would still require a separate future confirmation set for release.

## Acquisition deviation, recorded before inference

The source validation partition supplied no SD1.4 examples during acquisition.
The original 400-example plan therefore failed: 375 samples were obtained,
comprising 200 originals and 25 each from the other seven generators. Two image
representations also exceeded intake limits and are recorded as failures. No
model predictions were used for selection. Preserve the original contract and
acquisition record; do not call this a complete eight-generator test.

Run the exact 375 acquired samples only with explicit `--allow-missing-sd14`.
The report records the deviation and uses balanced accuracy to account for the
200/175 class sizes. The minimum 200-generated-example release gate cannot pass.
Do not silently fill SD1.4 from a training partition or change model thresholds.
Fresh SD1.4 and independent-source confirmation remain required separately.
