"""
Video analysis API routes.
POST /video/analyze — Upload and analyze a video file (up to 180 seconds).

Rate limited to 3 requests/minute per IP via slowapi.
Supports anonymous uploads via get_optional_user.
"""

import uuid
import logging
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, Request, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from services.video_analyzer import VideoAnalyzer
from services.supabase_service import SupabaseService
from utils.file_utils import validate_video_file, save_temp_file, cleanup_temp_file
from utils.auth import get_optional_user

logger = logging.getLogger(__name__)
router = APIRouter()

limiter = Limiter(key_func=get_remote_address)


@router.post("/analyze")
@limiter.limit("3/minute")
async def analyze_video(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: Optional[dict] = Depends(get_optional_user),
) -> JSONResponse:
    """
    Analyze an uploaded video for authenticity.

    Rate limited: 3 requests per minute per IP address.

    Pipeline:
        1. Extract frames with OpenCV
        2. Sample frames evenly (max 60 frames for 180s video)
        3. Run image detectors on each frame
        4. Aggregate per-frame probabilities
        5. Produce final video-level verdict
    """
    scan_id: str = str(uuid.uuid4())
    temp_path: Optional[str] = None

    try:
        await validate_video_file(file)
        temp_path = await save_temp_file(file, scan_id)

        analyzer = VideoAnalyzer(model_loader=request.app.state.model_loader)
        result = await analyzer.analyze(temp_path, scan_id)

        db = SupabaseService()
        await db.save_scan(
            scan_id=scan_id,
            user_id=user["id"] if user else None,
            file_type="video",
            filename=file.filename,
            result=result,
        )

        return JSONResponse(content={"scan_id": scan_id, **result})

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Video analysis failed for scan {scan_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Video analysis pipeline failed.")
    finally:
        if temp_path:
            background_tasks.add_task(cleanup_temp_file, temp_path)
