"""
Tests for file_utils._check_image_magic — magic byte validation.

Tests verify that known image file headers pass validation, and that
non-image data (scripts, HTML, executables) are correctly rejected.
All tests are synchronous (no event loop needed).

We load the module directly from file.
"""

import sys
import importlib.util
from pathlib import Path

# Ensure backend root is on sys.path (needed for transitive imports like aiofiles)
_backend = str(Path(__file__).resolve().parent.parent)
if _backend not in sys.path:
    sys.path.insert(0, _backend)

# Load file_utils module directly from file
_mod_path = Path(__file__).resolve().parent.parent / "utils" / "file_utils.py"
_spec = importlib.util.spec_from_file_location("file_utils", _mod_path, submodule_search_locations=[])
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
_check_image_magic = _mod._check_image_magic

import pytest


class TestCheckImageMagic:
    """Unit tests for the _check_image_magic() function."""

    # ── Test 1: Valid JPEG header ────────────────────────────────────────

    def test_valid_jpeg(self, tmp_path: Path):
        fp = tmp_path / "test.jpg"
        fp.write_bytes(
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00"
            b"\x00\x01\x00\x01\x00\x00\xff\xd9"
        )
        _check_image_magic(str(fp), "image/jpeg")

    # ── Test 2: Valid PNG header ─────────────────────────────────────────

    def test_valid_png(self, tmp_path: Path):
        fp = tmp_path / "test.png"
        fp.write_bytes(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
            b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
            b"\x00\x00\x00\x90wS\xde"
        )
        _check_image_magic(str(fp), "image/png")

    # ── Test 3: Valid WebP header ────────────────────────────────────────

    def test_valid_webp(self, tmp_path: Path):
        fp = tmp_path / "test.webp"
        fp.write_bytes(
            b"RIFF\x24\x00\x00\x00WEBPVP8 "
            b"\x18\x00\x00\x000\x01\x00\x9d\x01\x2a"
        )
        _check_image_magic(str(fp), "image/webp")

    # ── Test 4: Python script → ValueError ───────────────────────────────

    def test_rejects_python_script(self, tmp_path: Path):
        fp = tmp_path / "evil.jpg"
        fp.write_bytes(b"#!/usr/bin/env python3\nimport os\nos.system('rm -rf /')\n")
        with pytest.raises(ValueError, match="does not match"):
            _check_image_magic(str(fp), "image/jpeg")

    # ── Test 5: HTML → ValueError ────────────────────────────────────────

    def test_rejects_html(self, tmp_path: Path):
        fp = tmp_path / "evil.jpg"
        fp.write_bytes(b"<!DOCTYPE html><html><body><script>alert('xss')</script></body></html>")
        with pytest.raises(ValueError, match="does not match"):
            _check_image_magic(str(fp), "image/jpeg")

    # ── Test 6: PE executable → ValueError ───────────────────────────────

    def test_rejects_pe_executable(self, tmp_path: Path):
        fp = tmp_path / "evil.jpg"
        fp.write_bytes(b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff")
        with pytest.raises(ValueError, match="does not match"):
            _check_image_magic(str(fp), "image/jpeg")

    # ── Test 7: TIFF with II byte order ──────────────────────────────────

    def test_valid_tiff_ii(self, tmp_path: Path):
        fp = tmp_path / "test.tiff"
        fp.write_bytes(b"II\x2a\x00\x08\x00\x00\x00" + b"\x00" * 20)
        _check_image_magic(str(fp), "image/tiff")

    def test_valid_tiff_mm(self, tmp_path: Path):
        fp = tmp_path / "test.tiff"
        fp.write_bytes(b"MM\x00\x2a\x00\x00\x00\x08" + b"\x00" * 20)
        _check_image_magic(str(fp), "image/tiff")

    # ── Test: BMP → valid ────────────────────────────────────────────────

    def test_valid_bmp(self, tmp_path: Path):
        fp = tmp_path / "test.bmp"
        fp.write_bytes(b"BM\x36\x00\x0c\x00\x00\x00\x00\x00\x36\x00\x00\x00")
        _check_image_magic(str(fp), "image/bmp")

    # ── Test: Empty file → ValueError ────────────────────────────────────

    def test_rejects_empty_file(self, tmp_path: Path):
        fp = tmp_path / "empty.jpg"
        fp.write_bytes(b"")
        with pytest.raises(ValueError, match="does not match"):
            _check_image_magic(str(fp), "image/jpeg")
