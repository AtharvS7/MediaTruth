"""
VideoAnalyzer — Full video forensics pipeline.

Pipeline:
  1. Extract frames with OpenCV
  2. Sample evenly (target: ~1 frame/3 seconds, max 60 frames)
  3. Run ImageAnalyzer on each frame in batches of 8
  4. Aggregate per-frame results to video-level verdict
"""

import asyncio
import logging
import os
import tempfile
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

from services.image_analyzer import ImageAnalyzer
from inference_pipeline.provenance import inspect_provenance
from inference_pipeline.aggregator import ConfidenceAggregator
from utils.video_utils import extract_frames, get_video_metadata

logger = logging.getLogger(__name__)

MAX_FRAMES: int = 20
TARGET_FPS_SAMPLE: float = 1 / 3  # 1 frame every 3 seconds


class VideoAnalyzer:
    """Orchestrates per-frame analysis and video-level aggregation."""

    def __init__(self, model_loader: Any) -> None:
        self.model_loader = model_loader
        self.image_analyzer = ImageAnalyzer(model_loader)
        self.aggregator = ConfidenceAggregator()

    async def analyze(self, video_path: str, scan_id: str) -> Dict[str, Any]:
        loop = asyncio.get_running_loop()

        # Extract video metadata
        meta: Dict[str, Any] = await loop.run_in_executor(
            None, get_video_metadata, video_path
        )

        duration: float = meta.get("duration_seconds", 0)
        if duration > 180:
            raise ValueError(
                f"Video exceeds maximum duration of 180 seconds ({duration:.1f}s)."
            )

        # Extract frames in thread pool
        frames, timestamps = await loop.run_in_executor(
            None, extract_frames, video_path, MAX_FRAMES
        )

        logger.info(
            f"[{scan_id}] Extracted {len(frames)} frames from {duration:.1f}s video."
        )

        # Analyze each frame (batched, concurrent)
        per_frame_results: List[Dict[str, Any]] = await self._analyze_frames_batch(
            frames, timestamps, scan_id
        )

        # Aggregate to video-level verdict
        video_verdict: Dict[str, Any] = self.aggregator.aggregate_video(
            per_frame_results
        )

        return {
            "file_type": "video",
            "provenance": await asyncio.to_thread(inspect_provenance, video_path),
            "sampled_frame_fraction": len(frames) / meta["frame_count"] if meta.get("frame_count", 0) > 0 else None,
            "coverage_note": "Sampled frames only; audio, face tracking and temporal manipulation models are not analyzed.",
            "score_semantics": "uncalibrated_heuristic",
            "duration_seconds": duration,
            "frames_analyzed": len(frames),
            "ai_generated_probability": video_verdict["ai_generated"],
            "ai_edited_probability": video_verdict["ai_edited"],
            "traditional_edit_probability": video_verdict["traditional_edit"],
            "authentic_probability": video_verdict["authentic"],
            "final_verdict": video_verdict["verdict"],
            "confidence": video_verdict["confidence"],
            "limited_mode": video_verdict["limited_mode"],
            "ml_available": video_verdict["ml_available"],
            "per_frame_results": per_frame_results,
            "metadata_findings": meta.get("findings", []),
            "explanation": video_verdict.get("explanation", ""),
        }

    async def _analyze_frames_batch(
        self,
        frames: List[np.ndarray],
        timestamps: List[float],
        scan_id: str,
        batch_size: int = 1,
    ) -> List[Dict[str, Any]]:
        """Analyze frames in batches to avoid memory exhaustion."""
        results: List[Dict[str, Any]] = []
        for i in range(0, len(frames), batch_size):
            batch_frames = frames[i : i + batch_size]
            batch_ts = timestamps[i : i + batch_size]
            tasks = [
                self._analyze_single_frame(frame, ts, scan_id, idx=i + j)
                for j, (frame, ts) in enumerate(zip(batch_frames, batch_ts))
            ]
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)
        return results

    async def _analyze_single_frame(
        self,
        frame: np.ndarray,
        timestamp: float,
        scan_id: str,
        idx: int,
    ) -> Dict[str, Any]:
        """Save frame to temp file and run image analysis."""
        tmp_path: Optional[str] = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                cv2.imwrite(tmp.name, frame)
                tmp_path = tmp.name

            result: Dict[str, Any] = await self.image_analyzer.analyze(
                tmp_path, f"{scan_id}_frame{idx}"
            )
            result.pop("manipulation_heatmap", None)
            result["timestamp"] = timestamp
            result["frame_index"] = idx
            return result
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError as e:
                    logger.warning(f"Failed to cleanup frame temp file {tmp_path}: {e}")
