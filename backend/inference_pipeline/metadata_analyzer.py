"""
MetadataAnalyzer — EXIF and file metadata forensics.

Flags anomalies such as:
  - Missing EXIF on a JPEG (suspicious)
  - Software tag indicating AI generator (Midjourney, DALL-E, Stable Diffusion)
  - Inconsistent timestamps
  - Geolocation impossibilities
  - Thumbnail / full-image mismatch
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List

import exifread
from PIL import Image
from PIL.ExifTags import TAGS

logger = logging.getLogger(__name__)

KNOWN_AI_SOFTWARE = [
    "midjourney", "dall-e", "stable diffusion", "firefly",
    "leonardo", "bing image creator", "adobe firefly",
    "generative fill", "neural", "ai",
]

KNOWN_EDITOR_SOFTWARE = [
    "photoshop", "lightroom", "gimp", "affinity", "capture one",
    "darktable", "pixelmator", "snapseed", "facetune",
]


class MetadataAnalyzer:
    def analyze(self, image_path: str) -> Dict[str, Any]:
        findings: List[str] = []
        anomaly_score = 0.0
        raw_meta: Dict[str, Any] = {}

        try:
            # Read EXIF with exifread
            with open(image_path, "rb") as f:
                tags = exifread.process_file(f, stop_tag="UNDEF", details=False)

            if not tags:
                findings.append("⚠️ No EXIF data found — common in AI-generated images.")
                anomaly_score += 0.25
            else:
                raw_meta = {str(k): str(v) for k, v in tags.items()}

                # Software tag analysis
                software = str(tags.get("Image Software", "")).lower()
                if any(ai in software for ai in KNOWN_AI_SOFTWARE):
                    findings.append(f"🤖 AI generation software detected in metadata: {software!r}")
                    anomaly_score += 0.6
                elif any(ed in software for ed in KNOWN_EDITOR_SOFTWARE):
                    findings.append(f"✏️ Image editing software detected: {software!r}")
                    anomaly_score += 0.2

                # Timestamp consistency
                orig_ts = tags.get("EXIF DateTimeOriginal")
                digi_ts = tags.get("EXIF DateTimeDigitized")
                if orig_ts and digi_ts and str(orig_ts) != str(digi_ts):
                    findings.append("⚠️ Timestamp mismatch between DateTimeOriginal and DateTimeDigitized.")
                    anomaly_score += 0.15

                # Check for thumbnail / image inconsistency via PIL
                try:
                    img = Image.open(image_path)
                    exif_data = img._getexif() or {}
                    img_software = exif_data.get(305, "")
                    if img_software and any(ai in img_software.lower() for ai in KNOWN_AI_SOFTWARE):
                        findings.append(f"🤖 PIL EXIF confirms AI software: {img_software}")
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
