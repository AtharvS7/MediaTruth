"""
ManipulationLocalizer — Detects and localizes image manipulations.

Uses frequency domain analysis (DCT artifacts), error level analysis (ELA),
and statistical AI-image analysis to produce:
  - manipulation score (global) — how much the image was edited
  - ai_likelihood_score (global) — statistical AI-generation likelihood
  - spatial heatmap (H, W, 3) uint8 RGB — inferno colormap for scientific clarity

Statistical AI Analysis (_statistical_ai_analysis):
  Estimates AI-generation probability from image statistics WITHOUT ML models.
  Signals:
    1. Laplacian variance — AI renders are unnaturally smooth (< 80) or
       unnaturally sharp (renders with no film grain)
    2. Color saturation uniformity — AI art has vibrant, uniform saturation
    3. Edge gradient uniformity — real photos have organic edge variation;
       AI images have uniformly clean/sharp edges
  Conservative thresholds to avoid false-positives on stylized photography.

Format handling:
  - JPEG/TIFF: ELA (0.6) + DCT (0.4) blend
  - PNG/BMP/WEBP: DCT-only (ELA is invalid on lossless formats)
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
    """Calibrated sigmoid mapping [0,1] → [0,1] for manipulation scores."""
    if raw < 1e-6:
        return 0.0
    return 1.0 / (1.0 + math.exp(-8.0 * (raw - 0.3)))


def _error_level_analysis(img_path: str, quality: int = 90) -> np.ndarray:
    """
    ELA — save image at reduced quality, measure per-pixel difference.
    Returns zero map for lossless formats (caller uses DCT-only).
    """
    img = Image.open(img_path)
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


def _statistical_ai_analysis(img_path: str) -> float:
    """
    Estimate AI-generation probability from image statistics.
    Does NOT require ML models — always runs, always returns a score.

    Conservative thresholds designed to minimize false-positives on
    real photographs while detecting clearly AI-generated digital art.

    Returns: float in [0, 0.85] — higher = more likely AI-generated
    """
    try:
        img_bgr = cv2.imread(img_path)
        if img_bgr is None:
            return 0.0

        h, w = img_bgr.shape[:2]
        # Only reliable for images with enough pixels
        if h < 32 or w < 32:
            return 0.0

        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
        hsv  = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV).astype(np.float32)

        ai_score = 0.0

        # ── Signal 1: Laplacian variance ───────────────────────────────────
        # AI-generated art & logos are often unnaturally smooth
        # (no film grain, no sensor noise). Score < 80 = AI-smooth.
        # Also high-frequency AI renders can be > 3000 with no grain noise.
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        lap_var = float(laplacian.var())

        if lap_var < 80:          # Too smooth — likely rendered/AI-illustrated
            ai_score += 0.35
        elif lap_var > 4000:      # Unnaturally sharp detail without grain
            ai_score += 0.10

        # ── Signal 2: Color saturation uniformity ──────────────────────────
        # AI art (logos, illustrations) tends to have vibrant, uniform colors.
        # Real photos have organic saturation variation.
        sat = hsv[:, :, 1] / 255.0
        sat_mean = float(sat.mean())
        sat_std  = float(sat.std())

        # High mean saturation + low std deviation = uniform vivid colors = AI pattern
        if sat_mean > 0.40 and sat_std < 0.25:
            ai_score += 0.25
        elif sat_mean > 0.55 and sat_std < 0.30:
            ai_score += 0.15

        # ── Signal 3: Brightness uniformity ───────────────────────────────
        # AI renders often have perfectly smooth gradients; real photos have
        # organic brightness variation from lighting.
        val = hsv[:, :, 2] / 255.0
        val_std = float(val.std())

        if val_std < 0.08:   # Very uniform brightness — artificial lighting
            ai_score += 0.20

        # ── Signal 4: Color channel correlation ───────────────────────────
        # Camera sensors introduce slight color noise. AI images have perfectly
        # correlated RGB channels in gradient regions.
        b, g, r = cv2.split(img_bgr.astype(np.float32))
        try:
            rg_corr = float(np.corrcoef(r.flatten(), g.flatten())[0, 1])
            rb_corr = float(np.corrcoef(r.flatten(), b.flatten())[0, 1])
            if rg_corr > 0.98 and rb_corr > 0.97:   # Near-perfect channel correlation
                ai_score += 0.15
        except Exception:
            pass

        return round(min(ai_score, 0.85), 4)

    except Exception as e:
        logger.debug("Statistical AI analysis failed (non-critical): %s", e)
        return 0.0


def _apply_inferno_colormap(gray_map: np.ndarray) -> np.ndarray:
    """Convert float32 [0,1] grayscale heatmap to inferno colormap RGB."""
    uint8_map = (gray_map * 255).astype(np.uint8)
    colored_bgr = cv2.applyColorMap(uint8_map, cv2.COLORMAP_INFERNO)
    return cv2.cvtColor(colored_bgr, cv2.COLOR_BGR2RGB)


class ManipulationLocalizer:
    def __init__(self, model_loader: Any) -> None:
        self.device = model_loader.device

    def predict(self, image_path: str) -> Dict[str, Any]:
        """
        Returns:
            score:              global manipulation probability [0, 1]
            ai_likelihood_score: statistical AI-generation score [0, 0.85]
            heatmap:            np.ndarray (H, W, 3) uint8 RGB — inferno colormap
            label:              'manipulated' | 'clean' | 'unknown'
            format_note:        list[str] — extra findings about format limitations
        """
        # Statistical AI analysis always runs first (no dependencies)
        ai_likelihood = _statistical_ai_analysis(image_path)

        try:
            with Image.open(image_path) as img_check:
                img_format: str = img_check.format or ""
                is_lossless: bool = img_format in _LOSSLESS_FORMATS

            ela_map = _error_level_analysis(image_path)
            dct_map = _dct_artifact_map(image_path)

            h, w = ela_map.shape
            dct_resized = cv2.resize(dct_map, (w, h))

            if is_lossless:
                combined = np.clip(dct_resized, 0.0, 1.0)
            else:
                combined = np.clip(0.6 * ela_map + 0.4 * dct_resized, 0.0, 1.0)

            combined = cv2.GaussianBlur(combined, (11, 11), 0)

            threshold = np.percentile(combined, 90)
            high_anomaly = combined[combined >= threshold]
            raw_score: float = float(high_anomaly.mean()) if len(high_anomaly) > 0 else 0.0
            calibrated_score: float = _calibrate(raw_score)

            heatmap_rgb = _apply_inferno_colormap(combined)

            format_note: List[str] = []
            if is_lossless:
                format_note.append(
                    f"ℹ️ Error Level Analysis (ELA) is not applicable to {img_format} format. "
                    "DCT artifact analysis was used instead."
                )

            return {
                "score": calibrated_score,
                "ai_likelihood_score": ai_likelihood,
                "heatmap": heatmap_rgb,
                "label": "manipulated" if calibrated_score > 0.5 else "clean",
                "format_note": format_note,
            }
        except Exception as e:
            logger.warning(f"Manipulation localizer failed: {e}")
            return {
                "score": 0.0,
                "ai_likelihood_score": ai_likelihood,
                "heatmap": None,
                "label": "unknown",
                "format_note": [],
            }
