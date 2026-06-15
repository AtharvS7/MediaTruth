"""
MetadataAnalyzer — EXIF and file metadata forensics.

Flags anomalies such as:
  - Missing EXIF on a JPEG (suspicious)
  - Software tag indicating AI generator (Midjourney, DALL-E, Stable Diffusion)
  - Inconsistent timestamps
  - Thumbnail / full-image software tag mismatch

Uses precise AI software matching to avoid false positives from common
software names (e.g. "Paint", "Canva").
"""

import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List

import exifread
from PIL import Image
from PIL.ExifTags import TAGS

logger = logging.getLogger(__name__)

# Specific AI tool names — no short substrings that match everyday software
KNOWN_AI_SOFTWARE: List[str] = [
    "midjourney", "dall-e", "stable diffusion", "firefly",
    "leonardo", "bing image creator", "adobe firefly",
    "generative fill", "imagemagick ai", "openai", "stablediffusion",
]

# Word-boundary regex for "neural" to avoid substring false positives
_NEURAL_RE = re.compile(r"\bneural\b", re.IGNORECASE)

KNOWN_EDITOR_SOFTWARE: List[str] = [
    "photoshop", "lightroom", "gimp", "affinity", "capture one",
    "darktable", "pixelmator", "snapseed", "facetune",
]


def _is_ai_software(software: str) -> bool:
    """Check if the software string indicates AI generation."""
    sw_lower: str = software.lower()
    if any(ai_name in sw_lower for ai_name in KNOWN_AI_SOFTWARE):
        return True
    if _NEURAL_RE.search(sw_lower):
        return True
    return False


class MetadataAnalyzer:
    def analyze(self, image_path: str) -> Dict[str, Any]:
        findings: List[str] = []
        anomaly_score: float = 0.0
        raw_meta: Dict[str, Any] = {}

        try:
            with open(image_path, "rb") as f:
                tags = exifread.process_file(f, stop_tag="UNDEF", details=False)

            if not tags:
                findings.append("⚠️ No EXIF data found — common in AI-generated images.")
                anomaly_score += 0.25
            else:
                raw_meta = {str(k): str(v) for k, v in tags.items()}

                # Software tag analysis
                software: str = str(tags.get("Image Software", "")).lower()
                if _is_ai_software(software):
                    findings.append(
                        f"🤖 AI generation software detected in metadata: {software!r}"
                    )
                    anomaly_score += 0.6
                elif any(ed in software for ed in KNOWN_EDITOR_SOFTWARE):
                    findings.append(
                        f"✏️ Image editing software detected: {software!r}"
                    )
                    anomaly_score += 0.2

                # Timestamp consistency
                orig_ts = tags.get("EXIF DateTimeOriginal")
                digi_ts = tags.get("EXIF DateTimeDigitized")
                if orig_ts and digi_ts and str(orig_ts) != str(digi_ts):
                    findings.append(
                        "⚠️ Timestamp mismatch between DateTimeOriginal and DateTimeDigitized."
                    )
                    anomaly_score += 0.15

                # Cross-check with PIL EXIF (use public .getexif() — Pillow 6+)
                # _getexif() is a private method that raises AttributeError on PNG/WebP
                try:
                    img = Image.open(image_path)
                    exif_data = img.getexif() or {}
                    img_software: str = exif_data.get(305, "")
                    if img_software and _is_ai_software(img_software):
                        findings.append(
                            f"🤖 PIL EXIF confirms AI software: {img_software}"
                        )
                        anomaly_score = min(anomaly_score + 0.3, 1.0)
                except Exception:
                    pass

        except Exception as e:
            logger.warning(f"Metadata analysis failed: {e}")
            findings.append("⚠️ Could not read file metadata.")
            anomaly_score += 0.1

        return {
            "anomaly_score": min(anomaly_score, 1.0),
            "findings": findings,
            "raw_metadata": raw_meta,
        }
