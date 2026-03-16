"""
ImageAnalyzer — Full image forensics pipeline.

Runs multiple independent detectors and aggregates results
into a final confidence matrix with a verdict.
"""

import asyncio
import base64
import io
import logging
from pathlib import Path
from typing import Any, Dict

import numpy as np
from PIL import Image

from inference_pipeline.deepfake_detector import DeepfakeDetector
from inference_pipeline.gan_detector import GANDetector
from inference_pipeline.manipulation_localizer import ManipulationLocalizer
from inference_pipeline.metadata_analyzer import MetadataAnalyzer
from inference_pipeline.aggregator import ConfidenceAggregator

logger = logging.getLogger(__name__)


class ImageAnalyzer:
    """Orchestrates the complete image forensics pipeline."""

    def __init__(self, model_loader):
        self.model_loader = model_loader
        self.deepfake_detector = DeepfakeDetector(model_loader)
        self.gan_detector = GANDetector(model_loader)
        self.manipulation_localizer = ManipulationLocalizer(model_loader)
        self.metadata_analyzer = MetadataAnalyzer()
        self.aggregator = ConfidenceAggregator()

    async def analyze(self, image_path: str, scan_id: str) -> Dict[str, Any]:
        """
        Run full analysis pipeline on a single image.

        Returns a unified result dict ready to be serialised as JSON.
        """
        loop = asyncio.get_event_loop()

        # Run CPU/GPU-bound tasks in thread pool to keep event loop free
        (
            deepfake_result,
            gan_result,
            manip_result,
            metadata_result,
        ) = await asyncio.gather(
            loop.run_in_executor(None, self.deepfake_detector.predict, image_path),
            loop.run_in_executor(None, self.gan_detector.predict, image_path),
            loop.run_in_executor(None, self.manipulation_localizer.predict, image_path),
            loop.run_in_executor(None, self.metadata_analyzer.analyze, image_path),
        )

        # Aggregate signals into final verdict
        verdict = self.aggregator.aggregate(
            deepfake=deepfake_result,
            gan=gan_result,
            manipulation=manip_result,
            metadata=metadata_result,
        )

        # Encode heatmap as base64 PNG for frontend
        heatmap_b64 = self._encode_heatmap(manip_result.get("heatmap"))

        return {
            "scan_id": scan_id,
            "file_type": "image",
            "ai_generated_probability": verdict["ai_generated"],
            "ai_edited_probability": verdict["ai_edited"],
            "traditional_edit_probability": verdict["traditional_edit"],
            "authentic_probability": verdict["authentic"],
            "final_verdict": verdict["verdict"],
            "confidence": verdict["confidence"],
            "manipulation_heatmap": heatmap_b64,
            "detector_scores": {
                "deepfake_score": deepfake_result.get("score", 0.0),
                "gan_score": gan_result.get("score", 0.0),
                "manipulation_score": manip_result.get("score", 0.0),
                "metadata_anomaly_score": metadata_result.get("anomaly_score", 0.0),
            },
            "metadata_findings": metadata_result.get("findings", []),
            "explanation": verdict.get("explanation", ""),
        }

    @staticmethod
    def _encode_heatmap(heatmap: "Optional[np.ndarray]") -> "Optional[str]":
        if heatmap is None:
            return None
        img = Image.fromarray((heatmap * 255).astype(np.uint8))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
