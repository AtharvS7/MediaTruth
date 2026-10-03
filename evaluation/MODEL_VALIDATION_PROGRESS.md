# Model validation evidence - 3 October 2026

Public verdicts remain withheld. Implementing an adapter is separate from proving
accuracy. Supabase recovery and cloud-worker replacement remain deferred.

## Image generation

The frozen 375-image exploratory wave is runnable with `run_validation_wave.py`.
See `VALIDATION_WAVE_20261003.md` for the original 400-image plan, explicit missing
SD1.4 deviation, exclusions, frozen thresholds and unknown training overlap.
Per-image checkpoints allow interrupted CPU runs to resume without changing
inputs. Baseline and both frozen candidates must be reported, including failures.
The new two-tail hypothesis fits only the existing calibration partition; it has
not passed release validation. No 90% claim follows from a fitted threshold.

## Editing localization

`trufor_research.py` loads pinned official TruFor source and weights with tensor
deserialization plus an explicit narrow NumPy numeric allowlist. Unknown globals,
changed source files and changed weights are rejected. No unrestricted pickle
fallback is used. CPU preprocessing matches upstream RGB/256 and outputs anomaly
maps at native resolution, bounded to 512x512 inputs. No AI/conventional/mixed
attribution is inferred from the map.

`benchmark_cocoglide.py` evaluated 12 original/GLIDE-edit pairs from the official
CocoGlide release. Pairs were chosen by fixed seeded shuffle before inference,
restricted to source license IDs 4/5 (CC BY / CC BY-SA). Images/masks stay local;
the report preserves selected paths, hashes, archive digest and license records.
Model rights remain informational/nonprofit only; commercial release needs
permission or a different model.

At the fixed 0.5 map threshold, mean edited IoU was **0.1063**, mean Dice **0.1478**,
and mean falsely flagged original pixel area **0.0232**. These are localization
metrics, not classification accuracy. The small source-published pilot is not
independent certification and the localization results are insufficient to promote
this candidate. Thresholds were not optimized on the test masks or maps inverted
to improve scores. See `trufor-pilot-20261003.json` for every result.

Upstream: https://github.com/grip-unina/TruFor
Dataset: https://www.grip.unina.it/download/prog/TruFor/CocoGlide.zip

## Video face manipulation

`inference_pipeline/mesonet_research.py` implements the official Apache-2.0 Meso4
architecture using PyTorch and reads only a pinned 156KB numeric HDF5 checkpoint.
Batch-normalization epsilon, NHWC flatten order and real-versus-fake output
orientation match upstream. Optional parity tooling uses Keras with a torch
backend; it is not TensorFlow parity or an independent accuracy benchmark.

Four official aligned-face examples scored 4/4 correctly. Maximum discrepancy
against the Keras-layer implementation was about 2.24e-8. These smoke examples
must not be reported as 100% video accuracy. Reports: `mesonet-pilot-20261003.json`
and `mesonet-parity-20261003.json`.

`video_candidate_evaluation.py` uses a hash-pinned YuNet face detector, at most
12 frames, and abstains without sufficient single-face coverage. It preserves
content hashes, source split checks and missing-face counts. It has no face
identity tracking and does not detect general generated videos, audio edits or
all conventional editing. No public model registry entries were enabled.

Independent video validation is blocked on dataset access: the official
Deepfake-Eval-2024 endpoint rejects the existing authenticated account with HTTP
403. Request access at https://huggingface.co/datasets/nuriachandra/Deepfake-Eval-2024.
The user has now submitted the access request; approval is pending.
Do not bypass access restrictions through mirrors. Other gated datasets similarly
need accepted terms. Training overlap, per-file rights and source/identity grouping
must still be reviewed after access is granted.

Upstream MesoNet: https://github.com/DariusAf/MesoNet
YuNet: https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet

## Still required before release

Fresh independent-source image confirmation, a stronger validated editing model,
AI/conventional/mixed attribution evidence, and independent labeled video tests
remain open. Passing software tests cannot close these scientific gaps. Models
must meet the revised above-90% classification policy on their declared scope;
localization requires separate meaningful mask metrics and false-alarm limits.

## Reproduction and software checks

The existing ML environment is used. Optional research packages for MesoNet are
`h5py==3.15.1` and `keras==3.11.3`; Keras is needed only for parity verification.
No production lockfile or serving dependency was changed. Downloaded model/data
artifacts are excluded from Git; preserve the source licenses and report hashes.

```powershell
.venv-upgrade/Scripts/python.exe backend/run_validation_wave.py evaluate .tools/fsd-repro .tools/accuracy_sources/fsd_source/weights evaluation/data/frozen-wave-20261003/test.jsonl evaluation/experiments/two-tail-policy-20261003.json evaluation/reports/calibration-20261002/frozen-policy.json evaluation/reports/frozen-wave-20261003 --allow-missing-sd14
```

The image run was launched on 3 October at approximately 13:53 IST. Its local
logs are `.tools/frozen-wave-20261003.stdout.log` and the corresponding stderr
file; checkpoint/report paths are under `evaluation/reports/frozen-wave-20261003`.
Do not launch a second copy while the recorded process is still active.

This implementation passed 241 backend tests and full backend Ruff checks.
Those tests verify software behavior, not 241 independently labeled media items.
