"""Validate decoded images, declared types, and reject forged headers."""
import pytest
from PIL import Image
from utils.file_utils import _check_image_magic, _check_video_magic

@pytest.mark.parametrize('fmt,mime', [('JPEG','image/jpeg'), ('PNG','image/png'), ('WEBP','image/webp'), ('BMP','image/bmp')])
def test_valid_image(tmp_path, fmt, mime):
    path = tmp_path / 'image'
    Image.new('RGB', (16, 16)).save(path, format=fmt)
    _check_image_magic(str(path), mime)

@pytest.mark.parametrize('payload', [b'', b'#!/usr/bin/python', b'<html>oops</html>', b'MZ\x90\x00', b'\xff\xd8\xff\xe0', b'\x89PNG\r\n\x1a\n', b'RIFF\x24\x00\x00\x00WEBPVP8 ', b'II\x2a\x00', b'MM\x00\x2a'])
def test_rejects_non_image_and_truncated_headers(tmp_path, payload):
    path = tmp_path / 'forged.jpg'
    path.write_bytes(payload)
    with pytest.raises(ValueError):
        _check_image_magic(str(path), 'image/jpeg')

def test_declared_type_must_match(tmp_path):
    path = tmp_path / 'image'
    Image.new('RGB', (16, 16)).save(path, format='PNG')
    with pytest.raises(ValueError, match='does not match'):
        _check_image_magic(str(path), 'image/jpeg')

def test_rejects_oversized_pixels(tmp_path):
    path = tmp_path / 'large.png'
    Image.new('1', (4001, 4000)).save(path)
    with pytest.raises(ValueError, match='megapixel'):
        _check_image_magic(str(path), 'image/png')

def test_riff_audio_is_not_video(tmp_path):
    path = tmp_path / 'audio.avi'
    path.write_bytes(b'RIFF\x00\x00\x00\x00WAVE' + b'\x00' * 20)
    with pytest.raises(ValueError):
        _check_video_magic(str(path), 'video/x-msvideo')


@pytest.mark.asyncio
async def test_interrupted_upload_is_removed(tmp_path, monkeypatch):
    from utils.file_utils import save_temp_file
    import asyncio
    monkeypatch.setattr('utils.file_utils.TEMP_DIR', tmp_path)
    class Upload:
        filename = 'image.png'
        content_type = 'image/png'
        calls = 0
        async def read(self, size):
            self.calls += 1
            if self.calls == 1:
                return b'partial data'
            raise asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await save_temp_file(Upload(), 'test-interrupted')
    assert not list(tmp_path.iterdir())
