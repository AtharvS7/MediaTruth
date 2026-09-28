"""Private scan history and retrieval. Ownerless records are not public."""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import JSONResponse

from services.supabase_service import SupabaseService
from utils.auth import get_optional_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/history")
async def get_scan_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: Optional[dict] = Depends(get_optional_user),
) -> JSONResponse:
    """Return paginated scan history.

    If authenticated, returns scans owned by the user.
    Anonymous requests are rejected.
    """
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required.")
    try:
        db = SupabaseService()
        user_id: Optional[str] = user["id"] if user else None
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
async def get_scan(
    scan_id: str,
    user: Optional[dict] = Depends(get_optional_user),
) -> JSONResponse:
    """Return a specific scan result by scan ID.

    Access rules:
      - Ownerless scans (user_id=None): private; no user access.
      - Owned scans: only accessible by the owner.
    """
    try:
        db = SupabaseService()
        scan = await db.get_scan_by_id(scan_id)

        if not scan:
            raise HTTPException(status_code=404, detail="Scan not found.")

        # IDOR protection: owned scans require matching user
        owner_id: Optional[str] = scan.get("user_id")
        if not user or owner_id is None or user["id"] != owner_id:
            raise HTTPException(
                status_code=403, detail="Forbidden. You do not own this scan."
            )

        return JSONResponse(content=scan)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch scan {scan_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve scan.")


@router.delete("/{scan_id}")
async def delete_scan(
    scan_id: str,
    user: Optional[dict] = Depends(get_optional_user),
) -> JSONResponse:
    """Delete a scan by ID.

    Access rules:
      - Authentication required (anonymous users cannot delete scans).
      - Only the scan owner can delete their own scan.
      - Anonymous scans (user_id=None) are immutable forensic records.
    """
    if not user:
        raise HTTPException(
            status_code=401, detail="Authentication required to delete scans."
        )

    try:
        db = SupabaseService()
        scan = await db.get_scan_by_id(scan_id)

        if not scan:
            raise HTTPException(status_code=404, detail="Scan not found.")

        owner_id: Optional[str] = scan.get("user_id")
        if owner_id is None:
            raise HTTPException(
                status_code=403,
                detail="Anonymous scans are immutable forensic records and cannot be deleted.",
            )
        if user["id"] != owner_id:
            raise HTTPException(
                status_code=403, detail="Forbidden. You do not own this scan."
            )

        await db.delete_scan(scan_id)
        return JSONResponse(content={"deleted": scan_id})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete scan {scan_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete scan.")
