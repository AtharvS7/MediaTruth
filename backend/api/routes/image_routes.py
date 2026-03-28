"""
Image analysis API routes.
POST /image/analyze — Upload and analyze an image file.

BUG-002 fix: Switched from get_current_user to get_optional_user
  so anonymous uploads are allowed for the portfolio demo.
"""

import uuid
import logging
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, Request, Depends
from fastapi.responses import JSONResponse

from services.image_analyzer import ImageAnalyzer
from services.supabase_service import SupabaseService
from utils.file_utils import validate_image_file, save_temp_file, cleanup_temp_file
from utils.auth import get_optional_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/analyze")
async def analyze_image(
    request: Request,
    file: UploadFile = File(...),
    user: Optional[dict] = Depends(get_optional_user),
) -> JSONResponse:
    """
    Analyze an uploaded image for authenticity.

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
        # Validate file type and size
        await validate_image_file(file)

        # Save to temp storage
        temp_path = await save_temp_file(file, scan_id)

        # Run full analysis pipeline
        analyzer = ImageAnalyzer(model_loader=request.app.state.model_loader)
        result = await analyzer.analyze(temp_path, scan_id)

        # Persist to Supabase
        db = SupabaseService()
        await db.save_scan(
            scan_id=scan_id,
            user_id=user["id"] if user else None,
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
