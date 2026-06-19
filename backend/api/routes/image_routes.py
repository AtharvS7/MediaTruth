"""
Image analysis API routes.
POST /image/analyze — Upload and analyze an image file.

Rate limited to 5 requests/minute per IP via slowapi.
Requires a valid Supabase JWT (Bearer token) — anonymous access is rejected.
"""

import uuid
import logging
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from services.image_analyzer import ImageAnalyzer
from services.supabase_service import SupabaseService
from utils.file_utils import validate_image_file, save_temp_file, cleanup_temp_file
from utils.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

# SEC-05: Module-level singleton Limiter — all requests share state.
# Each route module must have its OWN limiter; they cannot share the same
# limiter instance across modules or the slowapi state registration fails.
limiter = Limiter(key_func=get_remote_address, default_limits=[])


@router.post("/analyze")
@limiter.limit("5/minute")
async def analyze_image(
    request: Request,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
) -> JSONResponse:
    """
    Analyze an uploaded image for authenticity.

    Rate limited: 5 requests per minute per IP address.

    Returns:
        - ai_generated_probability
        - ai_edited_probability
        - traditional_edit_probability
        - authentic_probability
        - final_verdict
        - manipulation_heatmap (base64 encoded PNG)
        - metadata_findings
        - confidence_scores per detector
    """
    scan_id: str = str(uuid.uuid4())
    temp_path: Optional[str] = None

    try:
        await validate_image_file(file)
        temp_path = await save_temp_file(file, scan_id)

        analyzer = ImageAnalyzer(model_loader=request.app.state.model_loader)
        result = await analyzer.analyze(temp_path, scan_id)

        db = SupabaseService()
        await db.save_scan(
            scan_id=scan_id,
            user_id=user["id"],
            file_type="image",
            filename=file.filename,
            result=result,
        )

        return JSONResponse(content={"scan_id": scan_id, **result})

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Image analysis failed for scan {scan_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Analysis pipeline failed.")
    finally:
        if temp_path:
            await cleanup_temp_file(temp_path)
