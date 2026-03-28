"""
Shared pytest fixtures for MediaTruth tests.

Provides minimal valid image byte sequences and temp file helpers
so tests can run without real images or external dependencies.
"""

import pytest
from pathlib import Path


# ── Minimal valid file byte sequences ─────────────────────────────────────────

JPEG_MINIMAL = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00"
    b"\x00\x01\x00\x01\x00\x00\xff\xd9"
)

PNG_MINIMAL = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
    b"\x00\x00\x00\x90wS\xde\x00\x00\x00\x0c"
    b"IDAT\x08\xd7c\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)

WEBP_MINIMAL = (
    b"RIFF\x24\x00\x00\x00WEBPVP8 "
    b"\x18\x00\x00\x000\x01\x00\x9d\x01\x2a"
    b"\x01\x00\x01\x00\x01\x40\x25\xa4\x00\x03"
    b"\x70\x00\xfe\xfb\x94\x00\x00"
)


@pytest.fixture
def minimal_jpeg() -> bytes:
    """Return bytes constituting a minimal valid JPEG file."""
    return JPEG_MINIMAL


@pytest.fixture
def minimal_png() -> bytes:
    """Return bytes constituting a minimal valid PNG file."""
    return PNG_MINIMAL


@pytest.fixture
def minimal_webp() -> bytes:
    """Return bytes constituting a minimal valid WebP file."""
    return WEBP_MINIMAL


@pytest.fixture
def temp_jpeg_file(tmp_path: Path, minimal_jpeg: bytes) -> str:
    """Write minimal JPEG to temp directory and return the path string."""
    fp = tmp_path / "test.jpg"
    fp.write_bytes(minimal_jpeg)
    return str(fp)


@pytest.fixture
def temp_png_file(tmp_path: Path, minimal_png: bytes) -> str:
    """Write minimal PNG to temp directory and return the path string."""
    fp = tmp_path / "test.png"
    fp.write_bytes(minimal_png)
    return str(fp)
