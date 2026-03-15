"""
SupabaseService — Database operations for scan storage and retrieval.

Tables:
  scans             — scan record metadata
  analysis_results  — full JSON result per scan
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from supabase import create_client, Client

logger = logging.getLogger(__name__)


def _get_client() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    return create_client(url, key)


class SupabaseService:
    def __init__(self):
        self.client = _get_client()

    async def save_scan(
        self,
        scan_id: str,
        user_id: Optional[str],
        file_type: str,
        filename: str,
        result: Dict[str, Any],
    ) -> None:
        try:
            self.client.table("scans").insert({
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
            }).execute()

            self.client.table("analysis_results").insert({
                "scan_id": scan_id,
                "result_json": json.dumps(result),
            }).execute()
        except Exception as e:
            logger.warning(f"Failed to persist scan {scan_id}: {e}")

    async def get_scan_history(
        self,
        user_id: Optional[str],
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        try:
            offset = (page - 1) * page_size
            query = (
                self.client.table("scans")
                .select("*")
                .order("created_at", desc=True)
                .range(offset, offset + page_size - 1)
            )
            if user_id:
                query = query.eq("user_id", user_id)
            response = query.execute()
            return {"scans": response.data, "page": page, "page_size": page_size}
        except Exception as e:
            logger.error(f"Failed to retrieve scan history: {e}")
            return {"scans": [], "page": page, "page_size": page_size}

    async def get_scan_by_id(self, scan_id: str) -> Optional[Dict[str, Any]]:
        try:
            scan_resp = (
                self.client.table("scans").select("*").eq("id", scan_id).single().execute()
            )
            result_resp = (
                self.client.table("analysis_results")
                .select("result_json")
                .eq("scan_id", scan_id)
                .single()
                .execute()
            )
            if not scan_resp.data:
                return None
            scan = scan_resp.data
            if result_resp.data:
                scan["full_result"] = json.loads(result_resp.data["result_json"])
            return scan
        except Exception as e:
            logger.error(f"Failed to retrieve scan {scan_id}: {e}")
            return None
