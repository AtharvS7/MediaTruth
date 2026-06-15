"""
Video utilities — OpenCV-based frame extraction and metadata reading.

Features:
  - FPS fallback: assumes 25.0 if OpenCV returns invalid fps
  - Duration cap: validates against MAX_VIDEO_DURATION_SECONDS
  - Frame read guard: limits total read attempts to prevent hangs on corrupt files
"""

import logging
from typing import Dict, List, Tuple, Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)

MAX_VIDEO_DURATION_SECONDS: float = 180.0
_DEFAULT_FPS: float = 25.0


def _safe_fps(cap: cv2.VideoCapture, video_path: str) -> float:
    """Return FPS from capture, falling back to 25 if invalid."""
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps is None or fps <= 0:
        logger.warning(f"Could not read FPS for {video_path}, assuming {_DEFAULT_FPS}fps")
        return _DEFAULT_FPS
    return fps


def get_video_metadata(video_path: str) -> Dict[str, Any]:
    """Return duration, fps, resolution, and codec info."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    fps: float = _safe_fps(cap, video_path)
    frame_count: int = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width: int = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height: int = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration: float = frame_count / fps if fps > 0 else 0.0
    cap.release()

    findings: List[str] = []
    if duration == 0:
        findings.append("⚠️ Could not determine video duration.")
    if duration > MAX_VIDEO_DURATION_SECONDS:
        findings.append(
            f"⚠️ Video duration ({duration:.1f}s) exceeds {MAX_VIDEO_DURATION_SECONDS}s limit."
        )

    return {
        "duration_seconds": duration,
        "fps": fps,
        "frame_count": frame_count,
        "width": width,
        "height": height,
        "findings": findings,
    }


def extract_frames(
    video_path: str,
    max_frames: int = 60,
) -> Tuple[List[np.ndarray], List[float]]:
    """
    Extract evenly-spaced frames from a video.

    Safety features:
      - Validates fps > 0 (falls back to 25)
      - Validates duration <= MAX_VIDEO_DURATION_SECONDS
      - Limits total frame reads to prevent infinite loops on corrupt files

    Returns:
        frames: list of BGR numpy arrays
        timestamps: list of timestamps in seconds
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    fps: float = _safe_fps(cap, video_path)
    total_frames: int = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    duration: float = total_frames / fps if fps > 0 else 0.0
    if duration > MAX_VIDEO_DURATION_SECONDS:
        cap.release()
        raise ValueError(
            f"Video duration ({duration:.1f}s) exceeds maximum of "
            f"{MAX_VIDEO_DURATION_SECONDS}s."
        )

    # Calculate frame indices to sample
    if total_frames <= max_frames:
        sample_indices = list(range(total_frames))
    else:
        step = total_frames / max_frames
        sample_indices = [int(i * step) for i in range(max_frames)]

    frames: List[np.ndarray] = []
    timestamps: List[float] = []

    # Guard: limit total read attempts to prevent infinite loops on corrupt files
    max_read_attempts: int = len(sample_indices) * 2

    attempts: int = 0
    for idx in sample_indices:
        if attempts >= max_read_attempts:
            logger.warning(f"Max read attempts reached for {video_path}, stopping")
            break
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        attempts += 1
        if ret:
            frames.append(frame)
            timestamps.append(idx / fps)

    cap.release()
    logger.info(f"Extracted {len(frames)} frames from {video_path}")
    return frames, timestamps
