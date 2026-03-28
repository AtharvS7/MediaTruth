"""
SupabaseService — Database operations for scan storage and retrieval.

Tables:
  scans             — scan record metadata
  analysis_results  — full JSON result per scan

BUG-005 fixes:
  - Module-level singleton Supabase client (no per-request creation)
  - All sync .execute() calls wrapped in asyncio.run_in_executor()
  - Replaced .single() with .limit(1) to avoid exception on zero rows
IMPROVE-001:
  - save_scan logs WARNING with scan_id on persist failures
"""

import asyncio
import json
import logging
import os
from functools import lru_cache
from typing import Any, Dict, List, Optional

from supabase import create_client, Client

logger = logging.getLogger(__name__)

# ── Module-level singleton Supabase client ────────────────────────────────────

@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """Return a singleton Supabase client (created once, reused globally)."""
    url: str = os.environ["SUPABASE_URL"]
    key: str = os.environ["SUPABASE_SERVICE_KEY"]
    return create_client(url, key)


class SupabaseService:
    def __init__(self) -> None:
        self.client: Client = get_supabase_client()

    async def save_scan(
        self,
        scan_id: str,
        user_id: Optional[str],
        file_type: str,
        filename: str,
        result: Dict[str, Any],
    ) -> None:
        """Persist scan metadata and full result JSON to Supabase.

        Silently swallows errors so a DB failure never crashes the analysis
        response. Logs a WARNING with the scan_id for traceability.
        """
        try:
            loop = asyncio.get_running_loop()

            scan_query = self.client.table("scans").insert({
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
            })
            await loop.run_in_executor(None, scan_query.execute)

            result_query = self.client.table("analysis_results").insert({
                "scan_id": scan_id,
                "result_json": json.dumps(result),
            })
            await loop.run_in_executor(None, result_query.execute)

        except Exception as e:
            logger.warning(f"Failed to persist scan {scan_id}: {e}")

    async def get_scan_history(
        self,
        user_id: Optional[str],
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        try:
            loop = asyncio.get_running_loop()
            offset: int = (page - 1) * page_size

            query = (
                self.client.table("scans")
                .select("*")
                .order("created_at", desc=True)
                .range(offset, offset + page_size - 1)
            )
            if user_id:
                query = query.eq("user_id", user_id)
            else:
                # Anonymous: show scans with no owner
                query = query.is_("user_id", "null")

            response = await loop.run_in_executor(None, query.execute)
            return {"scans": response.data, "page": page, "page_size": page_size}
        except Exception as e:
            logger.error(f"Failed to retrieve scan history: {e}")
            return {"scans": [], "page": page, "page_size": page_size}

    async def get_scan_by_id(self, scan_id: str) -> Optional[Dict[str, Any]]:
        try:
            loop = asyncio.get_running_loop()

            # Use .limit(1) instead of .single() to avoid exception on 0 rows
            scan_query = (
                self.client.table("scans")
                .select("*")
                .eq("id", scan_id)
                .limit(1)
            )
            scan_resp = await loop.run_in_executor(None, scan_query.execute)

            if not scan_resp.data or len(scan_resp.data) == 0:
                return None

            scan: Dict[str, Any] = scan_resp.data[0]

            result_query = (
                self.client.table("analysis_results")
                .select("result_json")
                .eq("scan_id", scan_id)
                .limit(1)
            )
            result_resp = await loop.run_in_executor(None, result_query.execute)

            if result_resp.data and len(result_resp.data) > 0:
                scan["full_result"] = json.loads(result_resp.data[0]["result_json"])

            return scan
        except Exception as e:
            logger.error(f"Failed to retrieve scan {scan_id}: {e}")
            return None
