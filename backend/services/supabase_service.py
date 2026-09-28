"""
SupabaseService — Database persistence layer for scans and results.

Features:
  - Thread-safe singleton client with auto-recovery
  - All operations wrapped in asyncio.wait_for (12s timeout)
  - Blocking Supabase calls run in executor to keep event loop free
"""

import asyncio
import logging
import os
import threading
from typing import Any, Dict, List, Optional

from supabase import create_client, Client

logger = logging.getLogger(__name__)


def _strip_frame_heatmaps(result: dict) -> dict:
    """
    Remove manipulation_heatmap fields from per_frame_results before DB storage.

    BUG-04: Each frame's heatmap is 50–200KB base64. For a 60-frame video,
    this inflates the JSONB column by up to 12MB, causing:
      - Slow DB inserts and fetches
      - sessionStorage overflow on the frontend (5MB limit)
      - Excessive Supabase storage usage

    The heatmap is still returned to the client in the live API response
    (the result dict is returned BEFORE this function strips it for DB storage).
    """
    if "per_frame_results" not in result:
        return result
    cleaned = dict(result)
    cleaned["per_frame_results"] = [
        {k: v for k, v in frame.items() if k != "manipulation_heatmap"}
        for frame in result["per_frame_results"]
    ]
    return cleaned



# ── Thread-safe singleton client ──────────────────────────────────────────────
_supabase_client: Optional[Client] = None
_client_lock = threading.Lock()


def get_supabase_client() -> Client:
    """Return or create the Supabase client singleton.

    Thread-safe. If the client was previously None (e.g. failed init),
    this will attempt to create it again.
    """
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    with _client_lock:
        if _supabase_client is not None:
            return _supabase_client

        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set. "
                "Copy .env.example to .env and fill in your Supabase credentials."
            )
        _supabase_client = create_client(
            url, key,
            options=None,  # Use default options
        )
        logger.info("Supabase client initialised.")
        return _supabase_client


class SupabaseService:
    """High-level async wrapper for Supabase database operations."""

    DB_TIMEOUT: float = 12.0  # seconds

    def __init__(self) -> None:
        self.client: Client = get_supabase_client()

    async def save_scan(
        self,
        scan_id: str,
        user_id: Optional[str],
        file_type: str,
        filename: Optional[str],
        result: Dict[str, Any],
    ) -> None:
        """Persist a scan record and its full analysis result."""
        loop = asyncio.get_running_loop()

        # Insert scan summary row
        scan_row = {
            "id": scan_id,
            "user_id": user_id,
            "file_type": file_type,
            "filename": filename,
            "verdict": result.get("final_verdict"),
            "ai_generated_probability": result.get("ai_generated_probability"),
            "ai_edited_probability": result.get("ai_edited_probability"),
            "traditional_edit_probability": result.get("traditional_edit_probability"),
            "authentic_probability": result.get("authentic_probability"),
            "confidence": result.get("confidence"),
        }
        try:
            await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: self.client.table("scans").insert(scan_row).execute(),
                ),
                timeout=self.DB_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.error(f"Timeout saving scan {scan_id}")
            raise
        except Exception as e:
            logger.error(f"Failed to save scan {scan_id}: {e}")
            raise

        # Insert full result JSON
        # BUG-04 fix: strip per-frame heatmaps before DB storage.
        # Each heatmap is 50–200KB base64. For 60 frames = up to 12MB per record.
        # This would exceed sessionStorage limits and make fetches very slow.
        result_to_store = _strip_frame_heatmaps(result)
        result_row = {
            "scan_id": scan_id,
            "result_json": result_to_store,
        }
        try:
            await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: self.client.table("analysis_results").insert(result_row).execute(),
                ),
                timeout=self.DB_TIMEOUT,
            )
        except Exception as e:
            # D1: the scans row above is already committed. Roll it back with a
            # compensating delete so we never leave a scan with no analysis_results,
            # then propagate so the route returns 500 (BUG-01).
            logger.error(f"Failed to save analysis_results for {scan_id}: {e}")
            await self._delete_scan_row_best_effort(scan_id)
            raise

    async def _delete_scan_row_best_effort(self, scan_id: str) -> None:
        """D1 compensating delete: remove an orphaned scans row after a failed
        analysis_results insert. Best-effort — never raises, so a cleanup failure
        cannot mask the original error that triggered it."""
        loop = asyncio.get_running_loop()
        try:
            await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: self.client.table("scans").delete().eq("id", scan_id).execute(),
                ),
                timeout=self.DB_TIMEOUT,
            )
            logger.info(f"Rolled back orphaned scan row {scan_id} after result-insert failure")
        except Exception as cleanup_err:
            logger.error(
                f"Compensating delete failed for scan {scan_id}; manual cleanup may be "
                f"needed: {cleanup_err}"
            )

    async def get_scan_by_id(self, scan_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a scan and its full result by scan ID."""
        loop = asyncio.get_running_loop()
        try:
            scan_resp = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: (
                        self.client.table("scans")
                        .select("*")
                        .eq("id", scan_id)
                        .limit(1)
                        .execute()
                    ),
                ),
                timeout=self.DB_TIMEOUT,
            )
            if not scan_resp.data:
                return None
            scan = scan_resp.data[0]

            result_resp = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: (
                        self.client.table("analysis_results")
                        .select("result_json")
                        .eq("scan_id", scan_id)
                        .limit(1)
                        .execute()
                    ),
                ),
                timeout=self.DB_TIMEOUT,
            )
            if result_resp.data:
                scan["full_result"] = result_resp.data[0].get("result_json")

            return scan
        except asyncio.TimeoutError:
            logger.error(f"Timeout fetching scan {scan_id}")
            raise
        except Exception as e:
            logger.error(f"Failed to fetch scan {scan_id}: {e}")
            raise

    async def get_scan_history(
        self,
        user_id: Optional[str],
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """Return paginated scan history for a user or anonymous scans."""
        loop = asyncio.get_running_loop()
        offset = (page - 1) * page_size

        try:
            query = self.client.table("scans").select(
                "id, file_type, filename, verdict, confidence, created_at"
            )
            if user_id:
                query = query.eq("user_id", user_id)
            else:
                query = query.is_("user_id", "null")

            query = (
                query.order("created_at", desc=True)
                .range(offset, offset + page_size - 1)
            )

            resp = await asyncio.wait_for(
                loop.run_in_executor(None, query.execute),
                timeout=self.DB_TIMEOUT,
            )
            return {"scans": resp.data or [], "page": page, "page_size": page_size}
        except asyncio.TimeoutError:
            logger.error("Timeout fetching scan history")
            raise
        except Exception as e:
            logger.error(f"Failed to fetch scan history: {e}")
            raise

    async def delete_scan(self, scan_id: str) -> None:
        """Delete a scan record. Cascades to analysis_results via foreign key."""
        loop = asyncio.get_running_loop()
        try:
            await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: (
                        self.client.table("scans")
                        .delete()
                        .eq("id", scan_id)
                        .execute()
                    ),
                ),
                timeout=self.DB_TIMEOUT,
            )
            logger.info(f"Deleted scan {scan_id}")
        except asyncio.TimeoutError:
            logger.error(f"Timeout deleting scan {scan_id}")
            raise
        except Exception as e:
            logger.error(f"Failed to delete scan {scan_id}: {e}")
            raise

