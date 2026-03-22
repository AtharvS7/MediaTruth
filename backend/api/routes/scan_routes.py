"""
Scan history and retrieval routes.
GET /scan/history  — List all scans for the current user.
GET /scan/{id}     — Get a specific scan result by ID.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import JSONResponse

from services.supabase_service import SupabaseService
from utils.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/history")
async def get_scan_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user=Depends(get_current_user),
):
    """Return paginated scan history for the authenticated user."""
    try:
        db = SupabaseService()
        user_id = user["id"] if user else None
        scans = await db.get_scan_history(
            user_id=user_id,
            page=page,
            page_size=page_size,
        )
        return JSONResponse(content=scans)
    except Exception as e:
        logger.error(f"Failed to fetch scan history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve scan history.")


@router.get("/{scan_id}")
async def get_scan(scan_id: str, user=Depends(get_current_user)):
    """Return a specific scan result by scan ID."""
    try:
        db = SupabaseService()
        scan = await db.get_scan_by_id(scan_id)
        if not scan:
            raise HTTPException(status_code=404, detail="Scan not found.")
        
        # Prevent IDOR 
        if scan.get("user_id") != user["id"]:
            raise HTTPException(status_code=403, detail="Forbidden. You do not own this scan.")
            
        return JSONResponse(content=scan)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch scan {scan_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve scan.")
