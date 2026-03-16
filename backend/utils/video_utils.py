"""
Video utilities — OpenCV-based frame extraction and metadata reading.
"""

import logging
from typing import List, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def get_video_metadata(video_path: str) -> dict:
    """Return duration, fps, resolution, and codec info."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = frame_count / fps if fps > 0 else 0.0
    cap.release()

    findings = []
    if duration == 0:
        findings.append("⚠️ Could not determine video duration.")

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

    Returns:
        frames: list of BGR numpy arrays
        timestamps: list of timestamps in seconds
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Calculate frame indices to sample
    if total_frames <= max_frames:
        sample_indices = list(range(total_frames))
    else:
        step = total_frames / max_frames
        sample_indices = [int(i * step) for i in range(max_frames)]

    frames = []
    timestamps = []

    for idx in sample_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if ret:
            frames.append(frame)
            timestamps.append(idx / fps)

    cap.release()
    logger.info(f"Extracted {len(frames)} frames from {video_path}")
    return frames, timestamps
