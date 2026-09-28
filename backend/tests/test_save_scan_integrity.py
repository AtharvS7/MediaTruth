"""
D1 — SupabaseService.save_scan must not leave an orphaned `scans` row.

If the second insert (analysis_results) fails, the already-committed scans row
is rolled back with a compensating delete before the error propagates, so the
route returns 500 over a clean database rather than a dangling record.

Runs the async methods via asyncio.run() so no pytest-asyncio dependency is
needed (the existing suite is dependency-light).
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_backend = str(Path(__file__).resolve().parent.parent)
if _backend not in sys.path:
    sys.path.insert(0, _backend)

from services.supabase_service import SupabaseService


def _make_service(results_insert_exc=None):
    scans_tbl = MagicMock(name="scans")
    results_tbl = MagicMock(name="analysis_results")

    scans_tbl.insert.return_value.execute.return_value = None
    scans_tbl.delete.return_value.eq.return_value.execute.return_value = None
    if results_insert_exc is not None:
        results_tbl.insert.return_value.execute.side_effect = results_insert_exc
    else:
        results_tbl.insert.return_value.execute.return_value = None

    client = MagicMock()
    client.table.side_effect = lambda name: scans_tbl if name == "scans" else results_tbl

    # Bypass __init__ (which would call get_supabase_client / real network client).
    svc = SupabaseService.__new__(SupabaseService)
    svc.client = client
    return svc, scans_tbl, results_tbl


def test_orphan_row_rolled_back_on_result_insert_failure():
    svc, scans_tbl, results_tbl = _make_service(results_insert_exc=RuntimeError("db down"))

    with pytest.raises(RuntimeError):
        asyncio.run(
            svc.save_scan("scan-1", "user-1", "image", "f.jpg", {"final_verdict": "x"})
        )

    # The scans row was rolled back for exactly this scan id.
    scans_tbl.delete.assert_called_once()
    scans_tbl.delete.return_value.eq.assert_called_once_with("id", "scan-1")


def test_happy_path_inserts_both_and_does_not_delete():
    svc, scans_tbl, results_tbl = _make_service()

    asyncio.run(
        svc.save_scan("scan-2", "user-1", "image", "f.jpg", {"final_verdict": "x"})
    )

    scans_tbl.insert.assert_called_once()
    results_tbl.insert.assert_called_once()
    scans_tbl.delete.assert_not_called()


def test_compensating_delete_never_masks_original_error():
    # Even if the rollback delete itself fails, the ORIGINAL error must surface.
    svc, scans_tbl, results_tbl = _make_service(results_insert_exc=RuntimeError("original"))
    scans_tbl.delete.return_value.eq.return_value.execute.side_effect = RuntimeError("cleanup failed")

    with pytest.raises(RuntimeError, match="original"):
        asyncio.run(
            svc.save_scan("scan-3", "user-1", "image", "f.jpg", {"final_verdict": "x"})
        )
