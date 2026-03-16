"""
File utilities — validation, temp storage, cleanup.
"""

import asyncio
import logging
import os
import tempfile
from pathlib import Path

import aiofiles
from fastapi import UploadFile

logger = logging.getLogger(__name__)

MAX_IMAGE_SIZE_MB = 50
MAX_VIDEO_SIZE_MB = 500

ALLOWED_IMAGE_TYPES = {
    "image/jpeg", "image/png", "image/webp", "image/bmp", "image/tiff",
}
ALLOWED_VIDEO_TYPES = {
    "video/mp4", "video/quicktime", "video/x-msvideo", "video/webm",
    "video/mpeg", "video/x-matroska",
}

TEMP_DIR = Path(tempfile.gettempdir()) / "mediatruth_uploads"
TEMP_DIR.mkdir(parents=True, exist_ok=True)


async def validate_image_file(file: UploadFile) -> None:
    content_type = file.content_type or ""
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise ValueError(f"Unsupported image type: {content_type}. Allowed: {ALLOWED_IMAGE_TYPES}")
    # Size check via header
    if file.size and file.size > MAX_IMAGE_SIZE_MB * 1024 * 1024:
        raise ValueError(f"Image exceeds {MAX_IMAGE_SIZE_MB}MB limit.")


async def validate_video_file(file: UploadFile) -> None:
    content_type = file.content_type or ""
    if content_type not in ALLOWED_VIDEO_TYPES:
        raise ValueError(f"Unsupported video type: {content_type}. Allowed: {ALLOWED_VIDEO_TYPES}")
    if file.size and file.size > MAX_VIDEO_SIZE_MB * 1024 * 1024:
        raise ValueError(f"Video exceeds {MAX_VIDEO_SIZE_MB}MB limit.")


async def save_temp_file(file: UploadFile, scan_id: str) -> str:
    suffix = Path(file.filename or "upload").suffix or ".tmp"
    dest = TEMP_DIR / f"{scan_id}{suffix}"
    async with aiofiles.open(dest, "wb") as out:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            await out.write(chunk)
    logger.debug(f"Saved temp file: {dest}")
    return str(dest)


async def cleanup_temp_file(path: str) -> None:
    try:
        if path and os.path.exists(path):
            os.unlink(path)
            logger.debug(f"Cleaned up temp file: {path}")
    except Exception as e:
        logger.warning(f"Failed to clean up {path}: {e}")
