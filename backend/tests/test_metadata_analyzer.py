"""
Tests for MetadataAnalyzer — EXIF analysis and AI software detection.

Note: We load the module directly from file to avoid
inference_pipeline/__init__.py which transitively imports torch.
"""

import sys
import importlib.util
from pathlib import Path

# Load metadata_analyzer module directly from file (bypasses __init__.py → torch)
_mod_path = Path(__file__).resolve().parent.parent / "inference_pipeline" / "metadata_analyzer.py"
_spec = importlib.util.spec_from_file_location("metadata_analyzer", _mod_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
MetadataAnalyzer = _mod.MetadataAnalyzer
_is_ai_software = _mod._is_ai_software

import pytest


class TestIsAiSoftware:
    """Unit tests for the _is_ai_software() helper."""

    # ── Test 1: Known AI software names are correctly flagged ────────────

    @pytest.mark.parametrize("name", [
        "Midjourney v5",
        "DALL-E 3",
        "Stable Diffusion XL",
        "Adobe Firefly",
        "OpenAI DALL-E",
    ])
    def test_known_ai_software_flagged(self, name: str):
        assert _is_ai_software(name), f"Expected {name!r} to be flagged as AI software"

    # ── Test 2: False-positive software names are NOT flagged ────────────

    @pytest.mark.parametrize("name", [
        "Paint Shop Pro",
        "Canva",
        "Bravia TV",
        "Grain Editor",
        "Picasa",
        "Thailand Photo App",
        "GIMP 2.10",
        "Lightroom Classic",
        "Affinity Photo 2",
    ])
    def test_common_software_not_flagged(self, name: str):
        assert not _is_ai_software(name), f"Expected {name!r} to NOT be flagged"

    # ── Test 3: "neural" as whole word IS flagged ────────────────────────

    def test_neural_whole_word_flagged(self):
        assert _is_ai_software("Neural Image Editor")
        assert _is_ai_software("Photo Neural Enhancer")

    # ── Test 4: "neural" as substring — only if it's a whole word ────────

    def test_neural_in_ai_context_flagged(self):
        # "Neuralytix" does NOT contain "\bneural\b" — the 'y' breaks the boundary
        assert not _is_ai_software("Neuralytix Business Suite")

    def test_general_network_not_flagged(self):
        """'GeneralNetwork Pro' does not contain 'neural'."""
        assert not _is_ai_software("GeneralNetwork Pro")

    # ── Test 5: Empty string → not flagged ───────────────────────────────

    def test_empty_string(self):
        assert not _is_ai_software("")

    # ── Additional edge cases ────────────────────────────────────────────

    def test_case_insensitive(self):
        assert _is_ai_software("MIDJOURNEY")
        assert _is_ai_software("stable DIFFUSION")

    def test_partial_match_ai_not_flagged(self):
        """The word 'ai' alone should NOT trigger false positives."""
        assert not _is_ai_software("ai")
        assert not _is_ai_software("Repair")
        assert not _is_ai_software("Mountain")


class TestMetadataAnalyzer:
    """Integration tests for MetadataAnalyzer.analyze()."""

    def test_analyze_returns_valid_structure(self, temp_jpeg_file: str):
        """analyze() should return dict with expected keys."""
        analyzer = MetadataAnalyzer()
        result = analyzer.analyze(temp_jpeg_file)

        assert "anomaly_score" in result
        assert "findings" in result
        assert "raw_metadata" in result
        assert isinstance(result["anomaly_score"], float)
        assert isinstance(result["findings"], list)
        assert isinstance(result["raw_metadata"], dict)
        assert 0.0 <= result["anomaly_score"] <= 1.0

    def test_analyze_nonexistent_file(self, tmp_path: Path):
        """analyze() on missing file should not crash."""
        analyzer = MetadataAnalyzer()
        result = analyzer.analyze(str(tmp_path / "does_not_exist.jpg"))
        assert "anomaly_score" in result
        assert isinstance(result["findings"], list)
