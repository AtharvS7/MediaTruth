# FSD research reproduction

This experiment is **not connected to production inference**. The fixed upstream
rule improved sensitivity but falsely flagged two of nine original controls.
Do not interpret its standardized log likelihood as a probability.

Source: [Forensic Self-Descriptions, CVPR 2025](https://github.com/ductai199x/Forensic-Self-Descriptions-CVPR25),
revision `50f2eae06efdac2e5a33f407ca9a27a2295133ac`, release weights v1.2.0.
Copyright 2025 Tai D. Nguyen, Multimedia Information Security Lab, Drexel University.
The upstream code and our streaming patch are licensed under
[CC-BY-NC-SA-4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode);
the authors' notice is retained in `FSD_LICENSE.txt`. Noncommercial research only.

Check out that revision in an ignored local directory. Apply `fsd_streaming.patch`
from the checkout root with `git apply --ignore-space-change` (handles Windows
line endings). Download the four release assets listed
in `fsd_artifacts.json` into a separate ignored weights directory. The runner checks
every imported upstream source file and all four weight digests before loading.
It never downloads or enables attribution models. All checkpoint loads use
`weights_only=True`.

Use a separate research environment with the project's CPU PyTorch/Pillow
dependencies and the recorded NumPy/SciPy versions. The initial results used
NumPy 2.4.6 and SciPy 1.15.3. Do not replace the worker's locked dependencies.
From the MediaTruth root:

```text
python backend/benchmark_fsd.py PATH_TO_CHECKOUT PATH_TO_WEIGHTS PATH_TO_MANIFEST NEW_REPORT_PATH
```

The patch streams spatial blocks instead of allocating all overlapping patches
at once. It retains the 1024-pixel residual preprocessing, float64 arithmetic,
scale order, pixel order, 16,384-pixel accumulation chunks and upstream threshold
of -2.0. A seeded 64-pixel parity fixture matched the unmodified computation
exactly. That fixture tests implementation parity, not classification accuracy.

`--jpeg-quality 85` produces a paired robustness experiment without modifying
the source image. It does not add independent test samples. Dimension limits
bound the local research workload; rejected inputs remain inconclusive in metrics.
