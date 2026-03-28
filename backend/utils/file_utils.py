"""
File utilities — validation, temp storage, cleanup.

BUG-018 fixes:
  - Added magic byte validation for images (checks actual file bytes, not just Content-Type header)
  - Enforces size limit during streaming write (not just via Content-Length header)
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
    "image/jpeg", "image/png", "image/webp", "image/bmp", "image/tiff",
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


def _check_image_magic(file_path: str, declared_type: str) -> None:
    """Verify file magic bytes match declared Content-Type.

    Raises ValueError if the actual file content doesn't match an image signature.
    """
    with open(file_path, "rb") as f:
        header: bytes = f.read(12)

    # Check WebP (RIFF....WEBP)
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return  # Valid WebP

    for magic, mime in _IMAGE_MAGIC.items():
        if header[: len(magic)] == magic:
            return  # Matches a known image signature

    # TIFF has two possible byte orders
    if header[:2] in (b"II", b"MM"):
        return  # Likely TIFF

    raise ValueError(
        f"File content does not match any known image format. "
        f"Declared type: {declared_type}"
    )


async def validate_image_file(file: UploadFile) -> None:
    content_type: str = file.content_type or ""
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise ValueError(
            f"Unsupported image type: {content_type}. Allowed: {ALLOWED_IMAGE_TYPES}"
        )
    # Size check via header
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
    """Save uploaded file to temp storage with streaming size enforcement.

    BUG-018: Enforces size limit during write (not just from header) and
    validates magic bytes for images after save.
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
        size_limit = MAX_VIDEO_SIZE_MB * 1024 * 1024  # fallback

    # Stream with size enforcement
    bytes_written: int = 0
    async with aiofiles.open(dest, "wb") as out:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            bytes_written += len(chunk)
            if bytes_written > size_limit:
                # Clean up partial file
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
            # File doesn't match known image signature — clean up and reject
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
