"""
Integration tests for /scan routes — IDOR access control.

Uses FastAPI TestClient against a minimal app that mounts only the scan router,
with get_optional_user overridden and SupabaseService patched to a fake DB, so
no real auth or network calls happen. These assert the ownership rules that keep
one user from reading or deleting another user's scans.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

_backend = str(Path(__file__).resolve().parent.parent)
if _backend not in sys.path:
    sys.path.insert(0, _backend)

from api.routes import scan_routes
from utils.auth import get_optional_user

SCAN_OWNED = {"id": "s1", "user_id": "owner-1", "verdict": "Authentic / Original"}
SCAN_ANON = {"id": "s2", "user_id": None, "verdict": "Authentic / Original"}


def _client(current_user, scan_record, monkeypatch):
    app = FastAPI()
    app.include_router(scan_routes.router, prefix="/scan")
    app.dependency_overrides[get_optional_user] = lambda: current_user

    fake_db = MagicMock()

    async def _get_scan_by_id(scan_id):
        return scan_record

    async def _delete_scan(scan_id):
        return None

    fake_db.get_scan_by_id = _get_scan_by_id
    fake_db.delete_scan = _delete_scan
    monkeypatch.setattr(scan_routes, "SupabaseService", lambda: fake_db)
    return TestClient(app), fake_db


# ── Read access (GET /scan/{id}) ──────────────────────────────────────────────

def test_owner_can_read_own_scan(monkeypatch):
    client, _ = _client({"id": "owner-1"}, SCAN_OWNED, monkeypatch)
    r = client.get("/scan/s1")
    assert r.status_code == 200
    assert r.json()["id"] == "s1"


def test_other_user_cannot_read_owned_scan(monkeypatch):
    client, _ = _client({"id": "intruder"}, SCAN_OWNED, monkeypatch)
    assert client.get("/scan/s1").status_code == 403


def test_anonymous_scan_is_private(monkeypatch):
    client, _ = _client(None, SCAN_ANON, monkeypatch)
    assert client.get("/scan/s2").status_code == 403


def test_ownerless_scan_is_private_even_for_signed_in_users(monkeypatch):
    client, _ = _client({"id": "someone"}, SCAN_ANON, monkeypatch)
    assert client.get("/scan/s2").status_code == 403


def test_anonymous_history_requires_authentication(monkeypatch):
    client, _ = _client(None, None, monkeypatch)
    assert client.get("/scan/history").status_code == 401


def test_missing_scan_returns_404(monkeypatch):
    client, _ = _client({"id": "owner-1"}, None, monkeypatch)
    assert client.get("/scan/nope").status_code == 404


# ── Delete access (DELETE /scan/{id}) ─────────────────────────────────────────

def test_delete_requires_authentication(monkeypatch):
    client, _ = _client(None, SCAN_OWNED, monkeypatch)
    assert client.delete("/scan/s1").status_code == 401


def test_delete_non_owner_forbidden(monkeypatch):
    client, _ = _client({"id": "intruder"}, SCAN_OWNED, monkeypatch)
    assert client.delete("/scan/s1").status_code == 403


def test_delete_anonymous_scan_forbidden(monkeypatch):
    client, _ = _client({"id": "someone"}, SCAN_ANON, monkeypatch)
    assert client.delete("/scan/s2").status_code == 403


def test_owner_can_delete_own_scan(monkeypatch):
    client, _ = _client({"id": "owner-1"}, SCAN_OWNED, monkeypatch)
    r = client.delete("/scan/s1")
    assert r.status_code == 200
    assert r.json()["deleted"] == "s1"
