# Experimental temporal video diagnostics

The video pipeline now measures consecutive-frame windows in addition to its
existing uniform/scene-change image samples. This is descriptive instrumentation,
not a validated video manipulation detector. It never enters the confidence
aggregator and does not enable public verdicts.

## Implemented coverage

- At most eight uniformly positioned windows of five consecutive frames:
  40 explicit frame reads and 32 adjacent-frame comparisons, serially.
- Optical flow runs on grayscale frames downscaled to a maximum side of 320
  pixels. Only the current and previous analysis frames are retained.
- Each pair reports raw pixel mean absolute difference, grayscale histogram
  distance, median motion at analysis resolution, motion-compensated residual,
  and the fraction of warp coordinates inside the image.
- Frame indices, nominal timestamps, requested/decoded counts, failed reads,
  sampled-frame fraction and measured-adjacent-pair fraction are included.
- Failed reads break adjacency; failed seeks and invalid metadata cannot become
  successful measurements. OpenCV resources are released on failure.

The method uses OpenCV's [Farneback optical flow API](https://docs.opencv.org/4.x/dc/d6b/group__video__track.html).
Backward flow from the current frame to the previous frame supplies coordinates
for remapping the previous image. Borders outside the image are excluded;
occlusion and flow confidence are **not** estimated.

## Interpretation and limits

High residuals can come from natural motion, cuts, occlusion, lighting or
compression. Low residuals do not demonstrate authenticity. These measurements
cannot attribute AI generation, AI editing, conventional editing or face swaps.
There are no detection thresholds or accuracy claims. Face tracking, trained
temporal models, audio and lip-sync analysis remain unavailable.

Sparse windows can miss short events. Times are frame index divided by reported
FPS, so variable-frame-rate timing is approximate. Frame-seek/GOP decoding time
depends on the codec even though the explicit read count is bounded. This adds
no weights, model downloads or paid services.

## Verification and next validation gate

`backend/tests/test_temporal_video.py` uses synthetic controls for static images,
known translation, hard intensity changes, decoder failure, invalid metadata,
bounded coverage and verdict isolation. These are software correctness checks;
they are not a labeled-video benchmark.

Before any video classification can be enabled, obtain rights-cleared authentic,
generated, face-manipulated, conventionally edited and mixed-workflow videos with
originals, temporal edit annotations and source/identity-independent partitions.
Keep training, calibration and locked evaluation separate. Include camera motion,
low light, occlusion, cuts, interpolation, variable frame rate, recompression and
non-face videos as controls. Evaluate missed-event rates and false-positive rates
by source and transformation, abstention coverage and confidence intervals under
the project's release gates. Face models additionally require detection/tracking
coverage and identity/demographic failure analysis. No completion or accuracy
score is increased merely by adding this instrumentation.
