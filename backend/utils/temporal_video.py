"""Bounded temporal measurements, never a manipulation or origin classifier."""

import math
from typing import Any, Dict

import cv2
import numpy as np

MAX_WINDOWS = 8
FRAMES_PER_WINDOW = 5
MAX_SIDE = 320
MAX_PIXELS = 8_294_400
LIMITATIONS = [
    "Experimental descriptive measurements; no validated AI or edit classification.",
    "Motion, scene cuts, lighting, occlusion and compression can all affect these measurements.",
    "Sparse short windows can miss brief events and do not cover the full video.",
    "Timestamps use frame index / reported FPS; variable-rate timing is approximate.",
    "Face tracking, facial manipulation, audio and lip-sync models are not evaluated.",
]


def measure_pair(previous: np.ndarray, current: np.ndarray) -> Dict[str, Any]:
    """Measure same-size uint8 grayscale frames at analysis resolution.

    Backward optical flow maps current pixels into the previous frame for remap.
    Exclude out-of-bounds correspondences, but do not claim occlusion rejection.
    """
    if (previous.ndim != 2 or current.shape != previous.shape
            or previous.dtype != np.uint8 or current.dtype != np.uint8):
        raise ValueError("Expected same-size uint8 grayscale frames.")
    flow = cv2.calcOpticalFlowFarneback(current, previous, None, .5, 3, 15, 3, 5, 1.2, 0)
    height, width = current.shape
    yy, xx = np.mgrid[:height, :width].astype(np.float32)
    map_x, map_y = xx + flow[..., 0], yy + flow[..., 1]
    valid = ((map_x >= 0) & (map_x <= width - 1)
             & (map_y >= 0) & (map_y <= height - 1))
    warped = cv2.remap(previous, map_x, map_y, cv2.INTER_LINEAR)
    residual = np.abs(current.astype(np.float32) - warped.astype(np.float32)) / 255.0
    histograms = [cv2.calcHist([frame], [0], None, [32], [0, 256])
                  for frame in (previous, current)]
    return {
        "pixel_mae": float(np.mean(cv2.absdiff(previous, current))) / 255.0,
        "histogram_distance": float(cv2.compareHist(*histograms, cv2.HISTCMP_BHATTACHARYYA)),
        "motion_median_pixels": float(np.median(np.linalg.norm(flow, axis=2))),
        "motion_compensated_mae": float(np.mean(residual[valid])) if valid.any() else None,
        "valid_warp_fraction": float(np.mean(valid)),
        "analysis_width": width,
        "analysis_height": height,
    }


def analyze_temporal_windows(video_path: str) -> Dict[str, Any]:
    """Decode <=40 frames, retaining at most two reduced frames at a time.

    Work limits bound explicit decode calls; backend seek/GOP decoding cost is
    codec-dependent. Measurements never enter the confidence aggregator.
    """
    report: Dict[str, Any] = {
        "method": "bounded_adjacent_frames_farneback_v1",
        "status": "unavailable",
        "classification_available": False,
        "used_for_verdict": False,
        "limitations": list(LIMITATIONS),
        "windows": [],
        "pairs": [],
        "frames_decoded": 0,
        "frames_requested": 0,
        "failed_frame_indices": [],
    }
    cap = cv2.VideoCapture(video_path)
    try:
        if not cap.isOpened():
            report["reason"] = "video_open_failed"
            return report
        fps = cap.get(cv2.CAP_PROP_FPS)
        count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        width, height = cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        if not all(math.isfinite(v) and v > 0 for v in (fps, count, width, height)):
            report["reason"] = "invalid_video_metadata"
            return report
        total = int(count)
        if total < 2:
            report["reason"] = "fewer_than_two_frames"
            return report
        if count / fps > 180 or width * height > MAX_PIXELS:
            report["reason"] = "video_exceeds_resource_limits"
            return report
        starts = np.linspace(0, max(0, total - FRAMES_PER_WINDOW),
                             min(MAX_WINDOWS, max(1, total // FRAMES_PER_WINDOW)), dtype=int)
        decoded = set()
        for window_id, start in enumerate(starts.tolist()):
            indices = list(range(start, min(total, start + FRAMES_PER_WINDOW)))
            report["windows"].append({"requested_frame_indices": indices})
            previous, previous_index = None, None
            seek_ok = cap.set(cv2.CAP_PROP_POS_FRAMES, start)
            for idx in indices:
                report["frames_requested"] += 1
                if not seek_ok:
                    report["failed_frame_indices"].append(idx)
                    continue
                ok, frame = cap.read()
                # Do not label an imprecise seek or a decode gap as adjacent frames.
                position = cap.get(cv2.CAP_PROP_POS_FRAMES)
                if not ok or frame is None or not math.isfinite(position) or abs(position - (idx + 1)) > .5:
                    report["failed_frame_indices"].append(idx)
                    previous, previous_index = None, None
                    continue
                h, w = frame.shape[:2]
                if h * w > MAX_PIXELS or min(h, w) < 2:
                    report["failed_frame_indices"].append(idx)
                    previous, previous_index = None, None
                    continue
                scale = min(1., MAX_SIDE / max(h, w))
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                if scale < 1:
                    gray = cv2.resize(gray, (max(2, round(w * scale)), max(2, round(h * scale))),
                                      interpolation=cv2.INTER_AREA)
                decoded.add(idx)
                if previous is not None and previous.shape == gray.shape:
                    pair = measure_pair(previous, gray)
                    pair.update({"window_index": window_id,
                                 "frame_indices": [previous_index, idx],
                                 "timestamps_seconds": [previous_index / fps, idx / fps]})
                    report["pairs"].append(pair)
                previous, previous_index = gray, idx
        report.update({
            "frames_decoded": len(decoded),
            "frame_count": total,
            "sampled_frame_indices": sorted(decoded),
            "sampled_frame_fraction": len(decoded) / total,
            "adjacent_pairs_measured": len(report["pairs"]),
            "adjacent_pair_fraction": len(report["pairs"]) / (total - 1),
            "measured_interval_seconds": len(report["pairs"]) / fps,
        })
        if report["pairs"]:
            report["status"] = "partial" if report["failed_frame_indices"] else "measured"
        else:
            report["reason"] = "no_usable_adjacent_pairs"
        return report
    except cv2.error:
        # A codec/flow failure must not turn missing diagnostics into reassurance.
        report["status"] = "unavailable"
        report["reason"] = "opencv_analysis_failed"
        report["pairs"] = []
        return report
    finally:
        cap.release()
