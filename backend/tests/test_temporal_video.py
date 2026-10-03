"""Synthetic engineering controls, not detection-accuracy validation."""

import asyncio
import json
from unittest.mock import AsyncMock

import cv2
import numpy as np
import pytest

from utils.temporal_video import analyze_temporal_windows, measure_pair


def write_video(tmp_path, count=60, size=(64, 64)):
    path = str(tmp_path / "temporal.avi")
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"MJPG"), 10, size)
    assert writer.isOpened()
    for idx in range(count):
        writer.write(np.full((size[1], size[0], 3), 0 if idx < count // 2 else 255, np.uint8))
    writer.release()
    return path


def test_identical_frames_have_no_residual():
    frame = np.full((64, 64), 100, np.uint8)
    pair = measure_pair(frame, frame)
    assert pair["pixel_mae"] == 0
    assert pair["motion_compensated_mae"] == 0
    assert pair["histogram_distance"] == 0
    assert pair["valid_warp_fraction"] == 1


def test_motion_compensation_reduces_translation_residual():
    rng = np.random.default_rng(52)
    previous = cv2.GaussianBlur(rng.integers(0, 256, (96, 96), dtype=np.uint8), (5, 5), 0)
    current = cv2.warpAffine(previous, np.float32([[1, 0, 2], [0, 1, 0]]), (96, 96))
    pair = measure_pair(previous, current)
    assert 1.5 < pair["motion_median_pixels"] < 2.5
    assert pair["motion_compensated_mae"] < pair["pixel_mae"] / 2


def test_large_change_is_a_measurement_without_origin_claim():
    pair = measure_pair(np.zeros((64, 64), np.uint8), np.full((64, 64), 255, np.uint8))
    assert pair["pixel_mae"] == 1
    assert pair["histogram_distance"] == 1
    assert "verdict" not in pair and "ai_probability" not in pair


@pytest.mark.parametrize("count", [2, 4, 60])
def test_window_budget_adjacency_and_coverage(tmp_path, count):
    result = analyze_temporal_windows(write_video(tmp_path, count=count))
    assert result["status"] == "measured"
    assert result["classification_available"] is False
    assert result["used_for_verdict"] is False
    assert 2 <= result["frames_decoded"] <= 40
    assert result["frames_requested"] <= 40
    assert 1 <= len(result["pairs"]) <= 32
    assert result["sampled_frame_fraction"] == result["frames_decoded"] / count
    assert result["adjacent_pair_fraction"] == len(result["pairs"]) / (count - 1)
    for pair in result["pairs"]:
        assert pair["frame_indices"][1] == pair["frame_indices"][0] + 1
        assert pair["timestamps_seconds"][1] - pair["timestamps_seconds"][0] == pytest.approx(.1)
    json.dumps(result, allow_nan=False)


def test_resolution_is_bounded(tmp_path):
    result = analyze_temporal_windows(write_video(tmp_path, count=2, size=(640, 480)))
    assert result["pairs"][0]["analysis_width"] == 320
    assert result["pairs"][0]["analysis_height"] == 240


class FakeCapture:
    def __init__(self, fps=10, fail_at=None, seek_ok=True, count=5):
        self.fps, self.fail_at, self.seek_ok, self.count = fps, fail_at, seek_ok, count
        self.position = 0
        self.released = False

    def isOpened(self):
        return True

    def get(self, prop):
        return {cv2.CAP_PROP_FPS: self.fps, cv2.CAP_PROP_FRAME_COUNT: self.count,
                cv2.CAP_PROP_FRAME_WIDTH: 64, cv2.CAP_PROP_FRAME_HEIGHT: 64,
                cv2.CAP_PROP_POS_FRAMES: self.position}[prop]

    def set(self, prop, value):
        self.position = value
        return self.seek_ok

    def read(self):
        idx = self.position
        self.position += 1
        return (False, None) if idx == self.fail_at else (True, np.zeros((64, 64, 3), np.uint8))

    def release(self):
        self.released = True


def test_failed_decode_does_not_bridge_a_missing_frame(monkeypatch):
    cap = FakeCapture(fail_at=2)
    monkeypatch.setattr(cv2, "VideoCapture", lambda _: cap)
    result = analyze_temporal_windows("test")
    assert result["status"] == "partial"
    assert result["failed_frame_indices"] == [2]
    assert [pair["frame_indices"] for pair in result["pairs"]] == [[0, 1], [3, 4]]
    assert result["frames_decoded"] == 4
    assert cap.released


@pytest.mark.parametrize("fps", [0, float("nan"), float("inf")])
def test_invalid_metadata_fails_closed_and_releases(monkeypatch, fps):
    cap = FakeCapture(fps=fps)
    monkeypatch.setattr(cv2, "VideoCapture", lambda _: cap)
    result = analyze_temporal_windows("test")
    assert result["status"] == "unavailable"
    assert result["reason"] == "invalid_video_metadata"
    assert result["pairs"] == []
    assert cap.released


def test_failed_seek_is_not_reported_as_measured(monkeypatch):
    cap = FakeCapture(seek_ok=False)
    monkeypatch.setattr(cv2, "VideoCapture", lambda _: cap)
    result = analyze_temporal_windows("test")
    assert result["status"] == "unavailable"
    assert result["frames_decoded"] == 0
    assert result["failed_frame_indices"] == list(range(5))
    assert cap.released


def test_imprecise_seek_does_not_claim_requested_timestamps(monkeypatch):
    class ImpreciseCapture(FakeCapture):
        def set(self, prop, value):
            self.position = value + 1
            return True

    cap = ImpreciseCapture()
    monkeypatch.setattr(cv2, "VideoCapture", lambda _: cap)
    result = analyze_temporal_windows("test")
    assert result["status"] == "unavailable"
    assert result["pairs"] == []
    assert result["sampled_frame_indices"] == []
    assert cap.released


def test_flow_error_is_unavailable_and_releases(monkeypatch):
    cap = FakeCapture()
    monkeypatch.setattr(cv2, "VideoCapture", lambda _: cap)

    def fail(*args):
        raise cv2.error("controlled test failure")

    monkeypatch.setattr(cv2, "calcOpticalFlowFarneback", fail)
    result = analyze_temporal_windows("test")
    assert result["status"] == "unavailable"
    assert result["reason"] == "opencv_analysis_failed"
    assert result["pairs"] == []
    assert result["classification_available"] is False
    assert cap.released


def test_duration_limit_rejects_before_decoding(monkeypatch):
    cap = FakeCapture(count=1801)
    monkeypatch.setattr(cv2, "VideoCapture", lambda _: cap)
    result = analyze_temporal_windows("test")
    assert result["reason"] == "video_exceeds_resource_limits"
    assert result["frames_requested"] == 0
    assert cap.released


def test_video_integration_keeps_diagnostics_out_of_verdict(monkeypatch):
    from services import video_analyzer as module
    from inference_pipeline.aggregator import ConfidenceAggregator

    analyzer = module.VideoAnalyzer.__new__(module.VideoAnalyzer)
    analyzer.aggregator = ConfidenceAggregator()
    analyzer._analyze_frames_batch = AsyncMock(return_value=[{"ml_available": False}])
    monkeypatch.setattr(module, "get_video_metadata", lambda _: {"duration_seconds": 1, "frame_count": 10})
    monkeypatch.setattr(module, "extract_frames", lambda *_: ([np.zeros((8, 8, 3), np.uint8)], [0.]))
    monkeypatch.setattr(module, "inspect_provenance", lambda _: {})
    monkeypatch.setattr(module, "analyze_temporal_windows", lambda _: {
        "status": "measured", "pairs": [{"pixel_mae": 1., "motion_compensated_mae": 1.}],
        "used_for_verdict": False,
    })
    report = asyncio.run(analyzer.analyze("test", "scan"))
    assert report["final_verdict"] == "Inconclusive"
    assert report["confidence"] == 0
    assert report["ai_generated_probability"] == 0
    assert report["temporal_diagnostics"]["used_for_verdict"] is False
