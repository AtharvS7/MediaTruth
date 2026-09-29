"""Read editable metadata claims; missing metadata is not evidence of AI."""
import logging
import re
from typing import Any, Dict, List
import exifread
from defusedxml import ElementTree
from PIL import Image

logger = logging.getLogger(__name__)
KNOWN_AI_SOFTWARE = [
    "midjourney", "dall-e", "stable diffusion", "firefly", "leonardo",
    "bing image creator", "generative fill", "openai", "stablediffusion",
    "invoke ai", "comfyui", "automatic1111", "novelai",
]
KNOWN_EDITOR_SOFTWARE = [
    "photoshop", "lightroom", "gimp", "affinity", "capture one",
    "darktable", "pixelmator", "snapseed", "facetune",
]
_NEURAL_RE = re.compile(r"\bneural\b", re.IGNORECASE)


def _is_ai_software(software: str) -> bool:
    return any(name in software.lower() for name in KNOWN_AI_SOFTWARE) or bool(
        _NEURAL_RE.search(software)
    )


class MetadataAnalyzer:
    def analyze(self, image_path: str) -> Dict[str, Any]:
        findings: List[str] = []
        raw_meta: Dict[str, Any] = {}
        image_format = "UNKNOWN"
        software_values = set()
        status = "read"
        try:
            with Image.open(image_path) as img:
                image_format = img.format or "UNKNOWN"
                software = img.getexif().get(305)
                if software:
                    software_values.add(str(software))
                for key, value in img.info.items():
                    if key.lower() == "software" and isinstance(value, str):
                        software_values.add(value)
                    if "xmp" in key.lower() and isinstance(value, (bytes, str)):
                        if len(value) <= 256 * 1024:
                            try:
                                root = ElementTree.fromstring(value)
                                for element in root.iter():
                                    if element.tag.rsplit("}", 1)[-1] in {"CreatorTool", "Software"} and element.text:
                                        software_values.add(element.text[:200])
                                    for name, text in element.attrib.items():
                                        if name.rsplit("}", 1)[-1] in {"CreatorTool", "Software"}:
                                            software_values.add(text[:200])
                            except Exception:
                                findings.append("XMP metadata could not be safely parsed; its claims were ignored.")
            with open(image_path, "rb") as stream:
                tags = exifread.process_file(stream, details=False)
            raw_meta = {str(k): str(v) for k, v in tags.items()}
            if tags.get("Image Software"):
                software_values.add(str(tags["Image Software"]))
            if not tags:
                findings.append("No EXIF metadata found. This does not establish AI generation, editing, or authenticity.")
            original = tags.get("EXIF DateTimeOriginal")
            digitized = tags.get("EXIF DateTimeDigitized")
            if original and digitized and str(original) != str(digitized):
                findings.append("Capture and digitization timestamps differ; this alone does not prove editing.")
        except Exception:
            logger.warning("Could not read image metadata")
            status = "unreadable"
            findings.append("Could not read file metadata; no conclusion can be drawn from its absence.")

        ai_claim = False
        editor_claim = False
        for software in sorted(software_values):
            if _is_ai_software(software):
                ai_claim = True
                findings.append(f"Unverified AI software claim in metadata: {software[:200]!r}.")
            elif any(name in software.lower() for name in KNOWN_EDITOR_SOFTWARE):
                editor_claim = True
                findings.append(
                    f"Editing software named in metadata: {software[:200]!r}. "
                    "This does not distinguish AI tools from conventional edits."
                )
        return {
            "anomaly_score": 0.6 if ai_claim else 0.0,
            "findings": findings, "raw_metadata": raw_meta,
            "image_format": image_format, "metadata_status": status,
            "ai_software_claim": ai_claim, "editor_software_claim": editor_claim,
            "provenance_verified": False,
        }
