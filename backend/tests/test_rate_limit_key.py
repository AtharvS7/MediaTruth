"""
Tests for utils.auth.rate_limit_key (S4 — per-session rate-limit keying).

The key function buckets authenticated callers by a hash of their bearer token
so users behind a shared NAT/IP get independent quotas, and falls back to the
client IP for anonymous traffic. The raw token must never appear in the key.
"""

import sys
from pathlib import Path

_backend = str(Path(__file__).resolve().parent.parent)
if _backend not in sys.path:
    sys.path.insert(0, _backend)

from utils.auth import rate_limit_key


class _FakeRequest:
    """Minimal stand-in for a Starlette Request (headers + client.host)."""

    def __init__(self, headers=None, client_host="1.2.3.4"):
        self.headers = headers or {}
        self.client = type("Client", (), {"host": client_host})()


def test_keys_on_token_when_bearer_present():
    key = rate_limit_key(_FakeRequest({"Authorization": "Bearer abc.def.ghi"}))
    assert key.startswith("user:")
    # Stable for the same token.
    assert key == rate_limit_key(_FakeRequest({"Authorization": "Bearer abc.def.ghi"}))


def test_different_tokens_get_different_keys():
    a = rate_limit_key(_FakeRequest({"Authorization": "Bearer token-a"}))
    b = rate_limit_key(_FakeRequest({"Authorization": "Bearer token-b"}))
    assert a != b


def test_falls_back_to_ip_when_no_token():
    assert rate_limit_key(_FakeRequest({}, client_host="9.9.9.9")) == "ip:9.9.9.9"


def test_empty_bearer_falls_back_to_ip():
    r = _FakeRequest({"Authorization": "Bearer "}, client_host="8.8.8.8")
    assert rate_limit_key(r) == "ip:8.8.8.8"


def test_does_not_leak_raw_token():
    raw = "super-secret-access-token"
    key = rate_limit_key(_FakeRequest({"Authorization": f"Bearer {raw}"}))
    assert raw not in key
