"""
ManipulationLocalizer — Detects and localizes image manipulations.

Uses frequency domain analysis (DCT artifacts), error level analysis (ELA),
and a calibrated sigmoid scoring function to produce:
  - manipulation score (global)
  - spatial heatmap (H, W, 3) uint8 RGB — inferno colormap for scientific clarity

Format handling:
  - JPEG/TIFF: ELA (0.6) + DCT (0.4) blend
  - PNG/BMP/WEBP: DCT-only (ELA is invalid on lossless formats)
    A finding note is added to inform the user.

For production: integrate ManTraNet or MVSS-Net weights when available.
"""

import io
import logging
import math
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Lossless formats where ELA is invalid (uniform artifacts everywhere)
_LOSSLESS_FORMATS = frozenset({"PNG", "BMP", "TIFF", "WEBP"})


def _calibrate(raw: float) -> float:
    """Calibrated sigmoid mapping [0,1] → [0,1] for manipulation scores.

    Smooth sigmoid centred at 0.3 with steepness 8:
        raw=0.0 → 0.0  (short-circuited)
        raw=0.3 → 0.50
        raw=0.6 → ~0.92
        raw=1.0 → ~0.997
    """
    if raw < 1e-6:
        return 0.0
    return 1.0 / (1.0 + math.exp(-8.0 * (raw - 0.3)))


def _error_level_analysis(img_path: str, quality: int = 90) -> np.ndarray:
    """
    ELA — save image at reduced quality, measure per-pixel difference.
    High residuals indicate potential manipulation.

    For lossless formats (PNG, BMP, TIFF, WEBP), ELA produces uniformly
    high scores because JPEG re-save artifacts appear everywhere.
    Returns a zero map in that case (caller should use DCT-only).
    """
    img = Image.open(img_path)

    if img.format in _LOSSLESS_FORMATS:
        width, height = img.size
        return np.zeros((height, width), dtype=np.float32)

    # CRASH-02 fix: always convert to RGB before ELA.
    # Grayscale JPEGs (mode "L") would produce shape (H,W) vs (H,W,3) mismatch.
    img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    ela_img = Image.open(buf).convert("RGB")

    orig = np.array(img, dtype=np.float32)
    comp = np.array(ela_img, dtype=np.float32)
    ela = np.abs(orig - comp)
    ela_norm = ela / (ela.max() + 1e-8)
    return ela_norm.mean(axis=2)


def _dct_artifact_map(img_path: str) -> np.ndarray:
    """
    Compute DCT block artifact map.
    JPEG double-compression leaves detectable 8×8 block boundary artifacts.
    """
    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return np.zeros((256, 256), dtype=np.float32)
    img = cv2.resize(img, (256, 256)).astype(np.float32)
    gx = cv2.Sobel(img, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(img, cv2.CV_32F, 0, 1, ksize=3)
    magnitude = np.sqrt(gx**2 + gy**2)
    block_mask = np.zeros_like(magnitude)
    block_mask[::8, :] = 1
    block_mask[:, ::8] = 1
    artifact_map = magnitude * block_mask
    return artifact_map / (artifact_map.max() + 1e-8)


def _apply_inferno_colormap(gray_map: np.ndarray) -> np.ndarray:
    """
    Convert a float32 [0,1] grayscale heatmap to an inferno colormap RGB image.

    Inferno: dark-purple (low/clean) → orange → yellow (high/suspicious).
    This is the de-facto standard colormap for forensic & scientific visualisation.

    Returns:
        np.ndarray shape (H, W, 3) uint8 RGB
    """
    uint8_map = (gray_map * 255).astype(np.uint8)
    colored_bgr = cv2.applyColorMap(uint8_map, cv2.COLORMAP_INFERNO)
    colored_rgb = cv2.cvtColor(colored_bgr, cv2.COLOR_BGR2RGB)
    return colored_rgb


class ManipulationLocalizer:
    def __init__(self, model_loader: Any) -> None:
        self.device = model_loader.device

    def predict(self, image_path: str) -> Dict[str, Any]:
        """
        Returns:
            score:       global manipulation probability [0, 1]
            heatmap:     np.ndarray (H, W, 3) uint8 RGB — inferno colormap
            label:       'manipulated' | 'clean' | 'unknown'
            format_note: list[str] — extra findings about format limitations
        """
        try:
            # Detect format to decide ELA vs DCT-only path
            with Image.open(image_path) as img_check:
                img_format: str = img_check.format or ""
                is_lossless: bool = img_format in _LOSSLESS_FORMATS

            ela_map = _error_level_analysis(image_path)
            dct_map = _dct_artifact_map(image_path)

            # Align dimensions
            h, w = ela_map.shape
            dct_resized = cv2.resize(dct_map, (w, h))

            if is_lossless:
                # ELA is invalid for lossless — use 100% DCT weight
                combined = np.clip(dct_resized, 0.0, 1.0)
            else:
                # Normal JPEG blend: ELA dominant, DCT for block artifacts
                combined = np.clip(0.6 * ela_map + 0.4 * dct_resized, 0.0, 1.0)

            # Gaussian smoothing for cleaner heatmap
            combined = cv2.GaussianBlur(combined, (11, 11), 0)

            # Global score = mean anomaly in top 10% pixels
            threshold = np.percentile(combined, 90)
            high_anomaly = combined[combined >= threshold]
            raw_score: float = float(high_anomaly.mean()) if len(high_anomaly) > 0 else 0.0
            calibrated_score: float = _calibrate(raw_score)

            # Apply inferno colormap — scientific standard for forensic heatmaps
            heatmap_rgb = _apply_inferno_colormap(combined)

            # Format-specific findings
            format_note: List[str] = []
            if is_lossless:
                format_note.append(
                    f"ℹ️ Error Level Analysis (ELA) is not applicable to {img_format} format. "
                    "DCT artifact analysis was used instead."
                )

            return {
                "score": calibrated_score,
                "heatmap": heatmap_rgb,
                "label": "manipulated" if calibrated_score > 0.5 else "clean",
                "format_note": format_note,
            }
        except Exception as e:
            logger.warning(f"Manipulation localizer failed: {e}")
            return {"score": 0.0, "heatmap": None, "label": "unknown", "format_note": []}
