import io
import struct
from pathlib import Path
import sys

import pytest
from PIL import Image, PngImagePlugin
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.metadata_cleaner import clean_image_metadata
from inference_pipeline.metadata_analyzer import MetadataAnalyzer
from api.routes import image_routes
from utils.auth import get_current_user


def test_export_preserves_pixels_and_drops_png_metadata(tmp_path):
    original = Image.new("RGBA", (20, 10), (17, 42, 81, 110))
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("Software", "OpenAI")
    metadata.add_text("XML:com.adobe.xmp", "private provenance")
    metadata.add_text("parameters", "private prompt")
    path = tmp_path / "source.png"
    original.save(path, pnginfo=metadata)
    source_bytes = path.read_bytes()
    assert MetadataAnalyzer().analyze(str(path))["ai_software_claim"]
    result = clean_image_metadata(str(path))
    # Inspect actual PNG chunks, rather than trusting the same metadata reader.
    offset, chunks = 8, []
    while offset < len(result):
        length = struct.unpack(">I", result[offset:offset + 4])[0]
        chunks.append(result[offset + 4:offset + 8])
        offset += 12 + length
    assert set(chunks) == {b"IHDR", b"IDAT", b"IEND"}
    with Image.open(io.BytesIO(result)) as clean:
        assert clean.tobytes() == original.tobytes()
        assert clean.mode == "RGBA"
    assert path.read_bytes() == source_bytes


def test_export_applies_orientation_and_removes_exif(tmp_path):
    path = tmp_path / "rotated.jpg"
    exif = Image.Exif()
    exif[274] = 6
    exif[305] = "Photoshop"
    Image.new("RGB", (30, 10), "red").save(path, exif=exif)
    with Image.open(io.BytesIO(clean_image_metadata(str(path)))) as clean:
        assert clean.size == (10, 30)
        assert not clean.getexif()
        assert not clean.info


@pytest.mark.parametrize("extension", ["png", "jpg", "webp"])
def test_missing_metadata_is_neutral(tmp_path, extension):
    path = tmp_path / f"image.{extension}"
    Image.new("RGB", (10, 10), "blue").save(path)
    result = MetadataAnalyzer().analyze(str(path))
    assert result["anomaly_score"] == 0.0
    assert result["provenance_verified"] is False


def test_corrupt_image_is_rejected(tmp_path):
    path = tmp_path / "broken.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\ninvalid")
    with pytest.raises(ValueError, match="decoded"):
        clean_image_metadata(str(path))


def test_animation_and_pixel_limit_rejected(tmp_path, monkeypatch):
    path = tmp_path / "animated.png"
    first = Image.new("RGB", (10, 10), "red")
    first.save(path, save_all=True, append_images=[Image.new("RGB", (10, 10), "blue")], duration=100)
    with pytest.raises(ValueError, match="Animated"):
        clean_image_metadata(str(path))
    first.save(path)
    monkeypatch.setattr("services.metadata_cleaner.MAX_EXPORT_PIXELS", 50)
    with pytest.raises(ValueError, match="megapixels"):
        clean_image_metadata(str(path))


def test_export_route_auth_download_validation_and_cleanup(tmp_path, monkeypatch):
    app = FastAPI()
    from services.jobs import JobManager
    app.state.jobs = JobManager()
    app.state.limiter = image_routes.limiter
    app.include_router(image_routes.router, prefix="/image")
    client = TestClient(app)
    image = io.BytesIO()
    Image.new("RGB", (10, 10)).save(image, format="PNG")
    files = {"file": ("image.png", image.getvalue(), "image/png")}
    assert client.post("/image/clean-metadata", files=files).status_code in (401, 403)
    app.dependency_overrides[get_current_user] = lambda: {"id": "export-user"}
    monkeypatch.setattr("utils.file_utils.TEMP_DIR", tmp_path)
    response = client.post("/image/clean-metadata", files=files)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "no-store"
    assert not list(tmp_path.iterdir())
    response = client.post("/image/clean-metadata", files={"file": ("bad.png", b"bad", "image/png")})
    assert response.status_code == 422
    assert not list(tmp_path.iterdir())
