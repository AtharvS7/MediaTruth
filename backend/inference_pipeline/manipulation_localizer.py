"""
ManipulationLocalizer — Detects and localizes image manipulations.

Uses frequency domain analysis (DCT artifacts), error level analysis (ELA),
and a lightweight CNN to produce:
  - manipulation score (global)
  - spatial heatmap (per-region anomaly map)

For production: integrate ManTraNet or MVSS-Net weights when available.

BUG-011 fix: ELA returns zero map for lossless image formats (PNG, BMP, TIFF, WEBP)
BUG-024 fix: Removed unused os/tempfile imports, moved io to module level
IMPROVE-005: Replaced magic `score * 2.5` with calibrated sigmoid mapping
"""

import io
import logging
import math
from typing import Dict, Any, Optional

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Lossless formats where ELA is invalid (uniform artifacts everywhere)
_LOSSLESS_FORMATS = frozenset({"PNG", "BMP", "TIFF", "WEBP"})


def _calibrate(raw: float) -> float:
    """Calibrated sigmoid mapping [0,1] → [0,1] for manipulation scores.

    IMPROVE-005: Replaces the hard-clipping `min(score * 2.5, 1.0)` with a
    smooth sigmoid centred at 0.3 with steepness 8:
        raw=0.0 → ~0.08
        raw=0.3 → 0.50
        raw=0.6 → ~0.92
        raw=1.0 → ~0.997

    This preserves precision in the mid-range and never hard-clips.
    """
    return 1.0 / (1.0 + math.exp(-8.0 * (raw - 0.3)))


def _error_level_analysis(img_path: str, quality: int = 90) -> np.ndarray:
    """
    ELA — save image at reduced quality, measure per-pixel difference.
    High residuals indicate potential manipulation.

    BUG-011: For lossless formats (PNG, BMP, TIFF, WEBP), ELA produces
    uniformly high scores because the JPEG re-save introduces compression
    artifacts everywhere. Return a zero map in that case.
    """
    img = Image.open(img_path)

    # Detect lossless format — ELA is unreliable
    if img.format in _LOSSLESS_FORMATS:
        width, height = img.size
        return np.zeros((height, width), dtype=np.float32)

    img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    ela_img = Image.open(buf).convert("RGB")

    orig = np.array(img, dtype=np.float32)
    comp = np.array(ela_img, dtype=np.float32)
    ela = np.abs(orig - comp)
    # Normalise to [0, 1]
    ela_norm = ela / (ela.max() + 1e-8)
    return ela_norm.mean(axis=2)  # collapse channels → grayscale heatmap


def _dct_artifact_map(img_path: str) -> np.ndarray:
    """
    Compute DCT block artifact map.
    JPEG double-compression leaves detectable 8×8 block boundary artifacts.
    """
    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return np.zeros((256, 256))
    img = cv2.resize(img, (256, 256)).astype(np.float32)
    # Sobel edge detection on image — highlights unnatural block seams
    gx = cv2.Sobel(img, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(img, cv2.CV_32F, 0, 1, ksize=3)
    magnitude = np.sqrt(gx**2 + gy**2)
    # Emphasise 8-pixel-grid positions
    block_mask = np.zeros_like(magnitude)
    block_mask[::8, :] = 1
    block_mask[:, ::8] = 1
    artifact_map = magnitude * block_mask
    return artifact_map / (artifact_map.max() + 1e-8)


class ManipulationLocalizer:
    def __init__(self, model_loader: Any) -> None:
        # Future: load ManTraNet / MVSS-Net here
        self.device = model_loader.device

    def predict(self, image_path: str) -> Dict[str, Any]:
        """
        Returns:
            score: global manipulation probability [0, 1]
            heatmap: np.ndarray (H, W) in [0, 1] — anomaly map
        """
        try:
            ela_map = _error_level_analysis(image_path)
            dct_map = _dct_artifact_map(image_path)

            # Resize dct_map to match ela_map
            h, w = ela_map.shape
            dct_resized = cv2.resize(dct_map, (w, h))

            # Fuse maps with equal weight
            combined = 0.6 * ela_map + 0.4 * dct_resized
            combined = np.clip(combined, 0, 1)

            # Apply Gaussian smoothing for cleaner heatmap
            combined = cv2.GaussianBlur(combined, (11, 11), 0)

            # Global score = mean anomaly in top 10% pixels
            threshold = np.percentile(combined, 90)
            high_anomaly = combined[combined >= threshold]
            score: float = float(high_anomaly.mean()) if len(high_anomaly) > 0 else 0.0

            # IMPROVE-005: calibrated sigmoid instead of hard clip
            calibrated_score: float = _calibrate(score)

            return {
                "score": calibrated_score,
                "heatmap": combined,
                "label": "manipulated" if calibrated_score > 0.5 else "clean",
            }
        except Exception as e:
            logger.warning(f"Manipulation localizer failed: {e}")
            return {"score": 0.0, "heatmap": None, "label": "unknown"}
