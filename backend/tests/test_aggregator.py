"""
Tests for ConfidenceAggregator — the core probability fusion engine.

All tests are pure Python — no external dependencies or mocking needed.
ConfidenceAggregator operates entirely on dictionaries of floats.

Note: We load the aggregator module directly from file to avoid
inference_pipeline/__init__.py which transitively imports torch.
"""

import sys
import importlib.util
from pathlib import Path

# Load aggregator module directly from file (bypasses __init__.py → torch)
_aggregator_path = Path(__file__).resolve().parent.parent / "inference_pipeline" / "aggregator.py"
_spec = importlib.util.spec_from_file_location("aggregator", _aggregator_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
ConfidenceAggregator = _mod.ConfidenceAggregator

import pytest


@pytest.fixture
def agg() -> ConfidenceAggregator:
    return ConfidenceAggregator()


class TestAggregatorBasic:

    # ── Test 1: All-zero inputs → authentic dominates ────────────────────

    def test_all_zero_gives_authentic(self, agg):
        """When all detectors report zero, the result should be authentic."""
        result = agg.aggregate(
            deepfake={"score": 0.0},
            gan={"score": 0.0},
            manipulation={"score": 0.0},
            metadata={"anomaly_score": 0.0},
        )
        assert result["authentic"] > 0.9, f"Expected authentic > 0.9, got {result['authentic']}"
        assert result["verdict"] == "Authentic / Original"

    # ── Test 2: High deepfake + GAN → ai_generated dominates ─────────────

    def test_high_deepfake_and_gan(self, agg):
        """High deepfake and GAN scores should produce ai_generated verdict."""
        result = agg.aggregate(
            deepfake={"score": 0.95},
            gan={"score": 0.90},
            manipulation={"score": 0.0},
            metadata={"anomaly_score": 0.0},
        )
        assert result["ai_generated"] > result["authentic"]
        assert result["ai_generated"] > result["traditional_edit"]
        assert result["verdict"] == "AI Generated"

    # ── Test 3: High manipulation score → authentic low ──────────────────

    def test_high_manipulation(self, agg):
        """High manipulation with no deepfake/GAN should indicate editing."""
        result = agg.aggregate(
            deepfake={"score": 0.0},
            gan={"score": 0.0},
            manipulation={"score": 0.95},
            metadata={"anomaly_score": 0.0},
        )
        assert result["authentic"] < 0.3

    # ── Test 4: Probabilities always sum to 1.0 ─────────────────────────

    @pytest.mark.parametrize("df,gan,manip,meta", [
        (0.0, 0.0, 0.0, 0.0),
        (1.0, 1.0, 1.0, 1.0),
        (0.5, 0.3, 0.7, 0.2),
        (0.1, 0.0, 0.0, 0.9),
        (0.0, 0.0, 1.0, 0.0),
    ])
    def test_probabilities_sum_to_one(self, agg, df, gan, manip, meta):
        """Four probabilities must always sum to 1.0 (within tolerance)."""
        result = agg.aggregate(
            deepfake={"score": df},
            gan={"score": gan},
            manipulation={"score": manip},
            metadata={"anomaly_score": meta},
        )
        total = (
            result["ai_generated"]
            + result["ai_edited"]
            + result["traditional_edit"]
            + result["authentic"]
        )
        assert abs(total - 1.0) < 0.001, f"Sum was {total}, expected ~1.0"

    # ── Test 5: Metadata anomaly reduces authentic ───────────────────────

    def test_metadata_anomaly_reduces_authentic(self, agg):
        """High metadata anomaly should decrease authentic probability."""
        result_clean = agg.aggregate(
            deepfake={"score": 0.0},
            gan={"score": 0.0},
            manipulation={"score": 0.0},
            metadata={"anomaly_score": 0.0},
        )
        result_meta = agg.aggregate(
            deepfake={"score": 0.0},
            gan={"score": 0.0},
            manipulation={"score": 0.0},
            metadata={"anomaly_score": 0.8},
        )
        assert result_meta["authentic"] < result_clean["authentic"]

    # ── Test 6: No probability is ever negative or >1 ────────────────────

    @pytest.mark.parametrize("df,gan,manip,meta", [
        (0.0, 0.0, 0.0, 0.0),
        (1.0, 1.0, 1.0, 1.0),
        (0.99, 0.99, 0.99, 0.99),
        (0.01, 0.01, 0.01, 0.01),
    ])
    def test_no_probability_out_of_range(self, agg, df, gan, manip, meta):
        """Every probability must be in [0.0, 1.0]."""
        result = agg.aggregate(
            deepfake={"score": df},
            gan={"score": gan},
            manipulation={"score": manip},
            metadata={"anomaly_score": meta},
        )
        for key in ["ai_generated", "ai_edited", "traditional_edit", "authentic"]:
            assert 0.0 <= result[key] <= 1.0, f"{key}={result[key]} out of range"

    # ── Test 7: aggregate_video with empty list → valid dict ─────────────

    def test_aggregate_video_empty(self, agg):
        """aggregate_video with no frames should still return a valid dict."""
        result = agg.aggregate_video([])
        assert "verdict" in result
        assert "confidence" in result
        assert "ai_generated" in result
        total = (
            result["ai_generated"]
            + result["ai_edited"]
            + result["traditional_edit"]
            + result["authentic"]
        )
        assert abs(total - 1.0) < 0.01

    # ── Test 8: aggregate_video with single frame ────────────────────────

    def test_aggregate_video_single_frame(self, agg):
        """aggregate_video with one frame should produce reasonable output."""
        single_frame = {
            "ai_generated_probability": 0.7,
            "ai_edited_probability": 0.1,
            "traditional_edit_probability": 0.1,
            "authentic_probability": 0.1,
        }
        result = agg.aggregate_video([single_frame])
        assert result["ai_generated"] > result["authentic"]

    # ── Test: result always contains expected keys ────────────────────────

    def test_result_contains_all_keys(self, agg):
        result = agg.aggregate(
            deepfake={"score": 0.5, "weights_available": True},
            gan={"score": 0.5, "weights_available": True},
            manipulation={"score": 0.5},
            metadata={"anomaly_score": 0.5},
        )
        required_keys = {
            "ai_generated", "ai_edited", "traditional_edit", "authentic",
            "verdict", "verdict_key", "confidence", "explanation", "limited_mode",
        }
        assert required_keys.issubset(result.keys())

    # ── Test: limited_mode detected when weights unavailable ─────────────

    def test_limited_mode_when_no_weights(self, agg):
        """When both deepfake and GAN report weights_available=False, limited_mode=True."""
        result = agg.aggregate(
            deepfake={"score": 0.0, "weights_available": False},
            gan={"score": 0.0, "weights_available": False},
            manipulation={"score": 0.0},
            metadata={"anomaly_score": 0.0},
        )
        assert result["limited_mode"] is True
        # Confidence should be capped at 0.75 in limited mode
        assert result["confidence"] <= 0.75

    def test_not_limited_mode_when_weights_available(self, agg):
        """When detectors have fine-tuned weights, limited_mode=False."""
        result = agg.aggregate(
            deepfake={"score": 0.8, "weights_available": True},
            gan={"score": 0.7, "weights_available": True},
            manipulation={"score": 0.0},
            metadata={"anomaly_score": 0.0},
        )
        assert result["limited_mode"] is False
