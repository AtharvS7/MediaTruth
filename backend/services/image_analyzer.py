"""
ImageAnalyzer — Full image forensics pipeline.

Runs multiple independent detectors concurrently and aggregates
results into a final confidence matrix with a verdict.
"""

import asyncio
import base64
import io
import logging
from typing import Any, Dict, Optional

import numpy as np
from PIL import Image

from inference_pipeline.deepfake_detector import DeepfakeDetector
from inference_pipeline.gan_detector import GANDetector
from inference_pipeline.manipulation_localizer import ManipulationLocalizer
from inference_pipeline.metadata_analyzer import MetadataAnalyzer
from inference_pipeline.aggregator import ConfidenceAggregator
from inference_pipeline.provenance import inspect_provenance

logger = logging.getLogger(__name__)


class ImageAnalyzer:
    """Orchestrates the complete image forensics pipeline."""

    def __init__(self, model_loader: Any) -> None:
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
        loop = asyncio.get_running_loop()

        # Run CPU/GPU-bound tasks in thread pool to keep event loop free
        (
            deepfake_result,
            gan_result,
            manip_result,
            metadata_result,
            provenance,
        ) = await asyncio.gather(
            loop.run_in_executor(None, self.deepfake_detector.predict, image_path),
            loop.run_in_executor(None, self.gan_detector.predict, image_path),
            loop.run_in_executor(None, self.manipulation_localizer.predict, image_path),
            loop.run_in_executor(None, self.metadata_analyzer.analyze, image_path),
            loop.run_in_executor(None, inspect_provenance, image_path),
        )

        # Aggregate signals into final verdict
        # Pass statistical AI score from manipulation localizer
        statistical_score = manip_result.get("ai_likelihood_score", 0.0)
        verdict = self.aggregator.aggregate(
            deepfake=deepfake_result,
            gan=gan_result,
            manipulation=manip_result,
            metadata=metadata_result,
            statistical=statistical_score,
        )

        # Encode heatmap as base64 PNG for frontend
        heatmap_b64 = self._encode_heatmap(manip_result.get("heatmap"))

        # Merge format-specific notes from manipulation localizer into findings
        all_findings = (
            metadata_result.get("findings", []) + manip_result.get("format_note", [])
        )

        return {
            "file_type": "image",
            "processing_version": "1.1.0",
            "model_weights_sha256": getattr(self.model_loader, "weight_fingerprints", {}),
            "native_input_transform": "RGB; resize 224x224; ImageNet mean/std normalization",
            "provenance": provenance,
            "editing_assessment": {
                "status": "not_validated",
                "note": "Compression and metadata clues do not reliably distinguish AI edits from conventional edits.",
            },
            "score_semantics": "uncalibrated_heuristic",
            "ai_generated_probability": verdict["ai_generated"],
            "ai_edited_probability": verdict["ai_edited"],
            "traditional_edit_probability": verdict["traditional_edit"],
            "authentic_probability": verdict["authentic"],
            "final_verdict": verdict["verdict"],
            "confidence": verdict["confidence"],
            "limited_mode": verdict.get("limited_mode", False),
            "ml_available": verdict.get("ml_available", True),
            "manipulation_heatmap": heatmap_b64,
            "detector_scores": {
                "deepfake_score": deepfake_result.get("score", 0.0),
                "deepfake_api_success": deepfake_result.get("api_success", False),
                "gan_score": gan_result.get("score", 0.0),
                "gan_api_success": gan_result.get("api_success", False),
                "manipulation_score": manip_result.get("score", 0.0),
                "statistical_ai_score": manip_result.get("ai_likelihood_score", 0.0),
                "metadata_anomaly_score": metadata_result.get("anomaly_score", 0.0),
            },
            "metadata_findings": all_findings,
            "explanation": verdict.get("explanation", ""),
        }

    @staticmethod
    def _encode_heatmap(heatmap: Optional[np.ndarray]) -> Optional[str]:
        """Encode heatmap as base64 PNG.

        Supports both:
          - (H, W, 3) uint8 RGB  — colored inferno heatmap from ManipulationLocalizer
          - (H, W) float32 [0,1] — legacy grayscale fallback
        """
        if heatmap is None:
            return None
        if heatmap.ndim == 3:
            # Already a colored RGB uint8 array
            img = Image.fromarray(heatmap.astype(np.uint8))
        else:
            # Grayscale float32 — convert to uint8
            img = Image.fromarray((heatmap * 255).astype(np.uint8))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
