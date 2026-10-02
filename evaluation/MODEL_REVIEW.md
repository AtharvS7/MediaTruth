# CNNDetect baseline review

Checkpoint SHA-256:
`3533f3e58a3b82215f21197f2faf4e99b911ec42a4a6e2d7823e04d5f3fd245a`.
It loads strictly into ResNet-50 with one output using tensor-only deserialization.
Exact checkpoint origin and training variant remain unconfirmed.

Reference: [CNNDetection by Sheng-Yu Wang and colleagues](https://github.com/PeterWang512/CNNDetection).
The [upstream repository license](https://github.com/PeterWang512/CNNDetection/blob/master/LICENSE.txt)
is CC BY-NC-SA 4.0. Commercial approval for the local checkpoint is not established.

## Correction and measured result

The earlier implementation resized the entire image to 224 by 224, altering
pixel scale and aspect ratio. The bounded CPU implementation now uses the
upstream optional 224-pixel center crop without resizing, with ImageNet
normalization. This is not the full-resolution default. Cropping can miss edits
elsewhere; small images are padded. Reports record the transform and regression
tests verify it. Non-finite model scores are rejected.

Both preprocessing versions flagged **0 of 12** synthetic SafeIMG pilot images
at the existing 0.5 threshold. The corrected run had no inference failures;
its scores ranged from 0 to 0.2476. No threshold was fitted to this pilot.
See `safeimg-native-crop224.json` for raw scores and checkpoint identity.

This shows poor detection on these examples, not overall accuracy. The sample
has no real-image controls and parent independence is unverified. The upstream
authors' example real/fake pair is checked separately as an implementation
fixture, not an independent validation set. Neither experiment enables verdicts.

Before release: confirm checkpoint provenance and licensing; acquire originals,
multiple modern generators and editing classes with independent parent groups;
compare candidate models with fixed preprocessing; select thresholds only on
calibration data; evaluate precision, recall, false positives, calibration and
compression robustness on held-out data. Enable only categories that pass.
