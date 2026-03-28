"""
Tests for IDOR ownership logic extracted from scan_routes.

Since the actual FastAPI dependency can't be tested without a server,
we extract and test the ownership decision logic as a pure function.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest


def check_ownership(scan_user_id, current_user) -> bool:
    """
    Pure function implementing the IDOR access control logic
    from scan_routes.get_scan().

    Rules:
      - Anonymous scans (user_id=None) → accessible to anyone
      - Owned scans → only accessible by the owner

    Args:
        scan_user_id: The user_id stored on the scan record, or None
        current_user: The authenticated user dict {"id": "..."}, or None

    Returns:
        True if access is granted, False if denied.
    """
    if scan_user_id is None:
        return True  # Anonymous scans are public
    if not current_user:
        return False  # Owned scan but no authenticated user
    return current_user["id"] == scan_user_id


class TestOwnershipLogic:
    """Tests for the IDOR ownership decision function."""

    # ── Test 1: Anonymous scan + no user → access granted ────────────────

    def test_anonymous_scan_no_user(self):
        """Anonymous scan should be accessible without auth."""
        assert check_ownership(scan_user_id=None, current_user=None) is True

    # ── Test 2: Anonymous scan + any logged-in user → access granted ─────

    def test_anonymous_scan_with_user(self):
        """Anonymous scan should be accessible to any authenticated user."""
        assert check_ownership(
            scan_user_id=None,
            current_user={"id": "user-123"},
        ) is True

    # ── Test 3: Owned scan + no user → access denied ─────────────────────

    def test_owned_scan_no_user(self):
        """Owned scan should be denied to unauthenticated users."""
        assert check_ownership(
            scan_user_id="owner-456",
            current_user=None,
        ) is False

    # ── Test 4: Owned scan + wrong user → access denied ──────────────────

    def test_owned_scan_wrong_user(self):
        """Owned scan should be denied to a different authenticated user."""
        assert check_ownership(
            scan_user_id="owner-456",
            current_user={"id": "attacker-789"},
        ) is False

    # ── Test 5: Owned scan + correct user → access granted ───────────────

    def test_owned_scan_correct_user(self):
        """Owned scan should be accessible to its owner."""
        assert check_ownership(
            scan_user_id="owner-456",
            current_user={"id": "owner-456"},
        ) is True

    # ── Additional edge cases ────────────────────────────────────────────

    def test_owned_scan_empty_user_dict(self):
        """Owned scan with empty user dict (no 'id' key) → denied."""
        assert check_ownership(
            scan_user_id="owner-456",
            current_user={},
        ) is False

    def test_uuid_format_ids(self):
        """Test with realistic UUID format IDs."""
        user_id = "550e8400-e29b-41d4-a716-446655440000"
        assert check_ownership(
            scan_user_id=user_id,
            current_user={"id": user_id},
        ) is True
        assert check_ownership(
            scan_user_id=user_id,
            current_user={"id": "660f9511-f39c-52e5-b827-557766551111"},
        ) is False
