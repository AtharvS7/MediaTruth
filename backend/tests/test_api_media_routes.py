"""
Integration tests for /image/analyze and /video/analyze.

These routes pull in the ML inference pipeline, so the route modules are imported
via pytest.importorskip — they run wherever the ML deps are installed (CI) and
skip cleanly where they are not. The analyzer and DB layers are patched so no
real inference or network calls occur.

Covers: auth enforcement, file-type validation (422), rate limiting (429), the
happy path (200), and the R1 server-side video timeout (504).
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_backend = str(Path(__file__).resolve().parent.parent)
if _backend not in sys.path:
    sys.path.insert(0, _backend)

from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Skip the whole module if the ML-backed route modules can't be imported.
image_routes = pytest.importorskip("api.routes.image_routes")
video_routes = pytest.importorskip("api.routes.video_routes")

from utils.auth import get_current_user  # noqa: E402

# Minimal valid JPEG (magic bytes 0xFFD8FF) and MP4 ('ftyp' box at offset 4).
import io
from PIL import Image
_image_bytes = io.BytesIO()
Image.new("RGB", (8, 8)).save(_image_bytes, format="JPEG")
JPEG = _image_bytes.getvalue()
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 16


@pytest.fixture(autouse=True)
def enable_legacy_route_unit_tests(monkeypatch):
    monkeypatch.setenv("ENABLE_LEGACY_ANALYSIS", "true")


def _build_app(router, limiter, authed=True):
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.state.model_loader = MagicMock()
    app.include_router(router)
    if authed:
        app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "email": "e@x.io"}
    return app


def _patch_image(monkeypatch, analyze_result=None):
    class FakeAnalyzer:
        def __init__(self, **kw):
            pass

        async def analyze(self, path, scan_id):
            return analyze_result or {"final_verdict": "Authentic / Original"}

    fake_db = MagicMock()

    async def _save(**kw):
        return None

    fake_db.save_scan = _save
    monkeypatch.setattr(image_routes, "ImageAnalyzer", FakeAnalyzer)
    monkeypatch.setattr(image_routes, "SupabaseService", lambda: fake_db)


# ── Auth ──────────────────────────────────────────────────────────────────────

def test_image_analyze_requires_auth():
    app = _build_app(image_routes.router, image_routes.limiter, authed=False)
    client = TestClient(app)
    r = client.post("/analyze", files={"file": ("a.jpg", JPEG, "image/jpeg")})
    assert r.status_code in (401, 403)  # HTTPBearer rejects missing credentials


# ── Happy path ────────────────────────────────────────────────────────────────

def test_image_analyze_happy_path(monkeypatch):
    _patch_image(monkeypatch)
    app = _build_app(image_routes.router, image_routes.limiter)
    client = TestClient(app)
    r = client.post(
        "/analyze",
        headers={"Authorization": "Bearer tok-happy"},
        files={"file": ("a.jpg", JPEG, "image/jpeg")},
    )
    assert r.status_code == 200
    assert r.json()["scan_id"]


# ── Validation (422) ──────────────────────────────────────────────────────────

def test_image_analyze_rejects_disguised_non_image(monkeypatch):
    _patch_image(monkeypatch)
    app = _build_app(image_routes.router, image_routes.limiter)
    client = TestClient(app)
    r = client.post(
        "/analyze",
        headers={"Authorization": "Bearer tok-bad"},
        files={"file": ("evil.jpg", b"#!/bin/sh\nrm -rf /\n", "image/jpeg")},
    )
    assert r.status_code == 422


# ── Rate limiting (429) ───────────────────────────────────────────────────────

def test_image_analyze_rate_limited(monkeypatch):
    _patch_image(monkeypatch)
    app = _build_app(image_routes.router, image_routes.limiter)
    client = TestClient(app)
    codes = []
    for _ in range(7):  # limit is 5/minute for one key
        r = client.post(
            "/analyze",
            headers={"Authorization": "Bearer tok-ratelimit-unique"},
            files={"file": ("a.jpg", JPEG, "image/jpeg")},
        )
        codes.append(r.status_code)
    assert 429 in codes


# ── R1: server-side video timeout (504) ───────────────────────────────────────

def test_video_analyze_times_out(monkeypatch):
    import asyncio

    monkeypatch.setattr(video_routes, "VIDEO_ANALYSIS_TIMEOUT", 0.05)

    class SlowAnalyzer:
        def __init__(self, **kw):
            pass

        async def analyze(self, path, scan_id):
            await asyncio.sleep(5)
            return {}

    fake_db = MagicMock()

    async def _save(**kw):
        return None

    fake_db.save_scan = _save
    monkeypatch.setattr(video_routes, "VideoAnalyzer", SlowAnalyzer)
    monkeypatch.setattr(video_routes, "SupabaseService", lambda: fake_db)

    app = _build_app(video_routes.router, video_routes.limiter)
    client = TestClient(app)
    r = client.post(
        "/analyze",
        headers={"Authorization": "Bearer tok-video"},
        files={"file": ("v.mp4", MP4, "video/mp4")},
    )
    assert r.status_code == 504
