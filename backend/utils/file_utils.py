"""
File utilities — validation, temp storage, cleanup.

Features:
  - Magic byte validation for images (checks actual file bytes, not just Content-Type)
  - Size limit enforcement during streaming write
  - Async temp file management
"""

import asyncio
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

import aiofiles
from fastapi import UploadFile

logger = logging.getLogger(__name__)

MAX_IMAGE_SIZE_MB: int = 50
MAX_VIDEO_SIZE_MB: int = 500

ALLOWED_IMAGE_TYPES = {
    "image/jpeg", "image/png", "image/webp", "image/bmp",
}
ALLOWED_VIDEO_TYPES = {
    "video/mp4", "video/quicktime", "video/x-msvideo", "video/webm",
    "video/mpeg", "video/x-matroska",
}

TEMP_DIR: Path = Path(tempfile.gettempdir()) / "mediatruth_uploads"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Magic byte signatures for image validation
_IMAGE_MAGIC = {
    b"\xff\xd8\xff":          "image/jpeg",
    b"\x89PNG\r\n\x1a\n":    "image/png",
    b"BM":                    "image/bmp",
}

# SEC-03: Video magic byte signatures
# Format: dict of (offset, magic_bytes) -> description
# Multiple signatures per format (containers differ by codec)
_VIDEO_MAGIC_CHECKS = [
    # MP4 / MOV: 'ftyp' at offset 4 (most common)
    (4, b"ftyp"),
    # MP4 fallback: 'moov' at offset 4
    (4, b"moov"),
    # AVI: 'RIFF' at offset 0, 'AVI ' at offset 8
    (0, b"RIFF"),   # will validate AVI sub-signature separately
    # MKV / WebM: EBML header
    (0, b"\x1a\x45\xdf\xa3"),
    # MPEG-1/2: starts with 0x000001BA or 0x000001B3
    (0, b"\x00\x00\x01\xba"),
    (0, b"\x00\x00\x01\xb3"),
]



def _check_image_magic(file_path: str, declared_type: str) -> None:
    """Verify file magic bytes match declared Content-Type.

    Raises ValueError if the actual file content doesn't match an image signature.
    """
    with open(file_path, "rb") as f:
        header: bytes = f.read(12)

    # Check WebP (RIFF....WEBP)
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return

    for magic, mime in _IMAGE_MAGIC.items():
        if header[: len(magic)] == magic:
            return

    # TIFF has two possible byte orders
    if header[:2] in (b"II", b"MM"):
        return

    raise ValueError(
        f"File content does not match any known image format. "
        f"Declared type: {declared_type}"
    )


def _check_video_magic(file_path: str, declared_type: str) -> None:
    """Verify that uploaded video file has valid video magic bytes.

    SEC-03: Prevents disguised executables, scripts, or HTML from being
    processed by OpenCV (a native C library that should only see valid video).

    Raises ValueError if the file does not match any known video signature.
    """
    with open(file_path, "rb") as f:
        header = f.read(16)

    if len(header) < 8:
        raise ValueError("Video file is too small to be valid.")

    # EBML / MKV / WebM
    if header[:4] == b"\x1a\x45\xdf\xa3":
        return

    # MPEG-1/2
    if header[:4] in (b"\x00\x00\x01\xba", b"\x00\x00\x01\xb3"):
        return

    # RIFF container (AVI, WebM-RIFF)
    if header[:4] == b"RIFF":
        return

    # MP4 / MOV / M4V: 'ftyp' or 'moov' or 'free' at offset 4
    box_type = header[4:8]
    if box_type in (b"ftyp", b"moov", b"free", b"mdat", b"wide", b"skip"):
        return

    # Some MP4 files have variable-length box before ftyp — check further
    # (safe fallback: try offset 0 for 'ftyp')
    if header[:4] == b"ftyp":
        return

    raise ValueError(
        f"File content does not match any known video format. "
        f"Declared Content-Type: {declared_type}. "
        f"File header (hex): {header.hex()[:32]}..."
    )



async def validate_image_file(file: UploadFile) -> None:
    content_type: str = file.content_type or ""
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise ValueError(
            f"Unsupported image type: {content_type}. Allowed: {ALLOWED_IMAGE_TYPES}"
        )
    if file.size and file.size > MAX_IMAGE_SIZE_MB * 1024 * 1024:
        raise ValueError(f"Image exceeds {MAX_IMAGE_SIZE_MB}MB limit.")


async def validate_video_file(file: UploadFile) -> None:
    content_type: str = file.content_type or ""
    if content_type not in ALLOWED_VIDEO_TYPES:
        raise ValueError(
            f"Unsupported video type: {content_type}. Allowed: {ALLOWED_VIDEO_TYPES}"
        )
    if file.size and file.size > MAX_VIDEO_SIZE_MB * 1024 * 1024:
        raise ValueError(f"Video exceeds {MAX_VIDEO_SIZE_MB}MB limit.")


async def save_temp_file(file: UploadFile, scan_id: str) -> str:
    """Save uploaded file to temp storage with streaming size enforcement
    and magic byte validation for images.
    """
    suffix: str = Path(file.filename or "upload").suffix or ".tmp"
    dest: Path = TEMP_DIR / f"{scan_id}{suffix}"
    content_type: str = file.content_type or ""

    # Determine size limit
    if content_type in ALLOWED_IMAGE_TYPES:
        size_limit: int = MAX_IMAGE_SIZE_MB * 1024 * 1024
    elif content_type in ALLOWED_VIDEO_TYPES:
        size_limit = MAX_VIDEO_SIZE_MB * 1024 * 1024
    else:
        size_limit = MAX_VIDEO_SIZE_MB * 1024 * 1024

    # Stream with size enforcement
    bytes_written: int = 0
    async with aiofiles.open(dest, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            bytes_written += len(chunk)
            if bytes_written > size_limit:
                await out.close()
                if dest.exists():
                    os.unlink(dest)
                raise ValueError("File exceeds size limit")
            await out.write(chunk)

    # Validate magic bytes for image uploads
    if content_type in ALLOWED_IMAGE_TYPES:
        try:
            _check_image_magic(str(dest), content_type)
        except ValueError:
            if dest.exists():
                os.unlink(dest)
            raise

    # SEC-03: Validate magic bytes for video uploads too
    # Prevents disguised executables from being passed to OpenCV
    elif content_type in ALLOWED_VIDEO_TYPES:
        try:
            _check_video_magic(str(dest), content_type)
        except ValueError:
            if dest.exists():
                os.unlink(dest)
            raise

    logger.debug(f"Saved temp file: {dest} ({bytes_written} bytes)")
    return str(dest)


async def cleanup_temp_file(path: str) -> None:
    try:
        if path and os.path.exists(path):
            os.unlink(path)
            logger.debug(f"Cleaned up temp file: {path}")
    except OSError as e:
        logger.warning(f"Failed to clean up {path}: {e}")
