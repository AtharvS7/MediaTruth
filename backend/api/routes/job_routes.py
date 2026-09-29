import uuid
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from services.jobs import QueueFull
from utils.auth import get_current_user, rate_limit_key
from slowapi import Limiter
from utils.file_utils import validate_image_file, validate_video_file, save_temp_file, cleanup_temp_file

router = APIRouter()
limiter = Limiter(key_func=rate_limit_key)


def public_job(job):
    return {"id": job.id, "status": job.status, "stage": job.stage,
            "error": job.error, "result": job.result if job.status == "completed" else None}


def owned_job(request, job_id, user):
    job = request.app.state.jobs.jobs.get(job_id)
    if job is None or job.owner != user["id"]:
        raise HTTPException(404, "Job not found or server restarted. Check saved history before retrying.")
    return job


@router.post("", status_code=202)
@limiter.limit("5/minute")
async def submit(request: Request, file: UploadFile = File(...), user=Depends(get_current_user)):
    path = None
    try:
        kind = "video" if (file.content_type or "").startswith("video/") else "image"
        await (validate_video_file(file) if kind == "video" else validate_image_file(file))
        path = await save_temp_file(file, str(uuid.uuid4()))
        job = request.app.state.jobs.submit(user["id"], kind, path, file.filename or "upload")
        path = None  # Job now owns cleanup.
        return public_job(job)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except QueueFull:
        raise HTTPException(503, "Queue full or you already have a pending job.", headers={"Retry-After": "10"})
    finally:
        if path:
            await cleanup_temp_file(path)


@router.get("/{job_id}")
async def status(job_id: str, request: Request, user=Depends(get_current_user)):
    return public_job(owned_job(request, job_id, user))


@router.delete("/{job_id}")
async def cancel(job_id: str, request: Request, user=Depends(get_current_user)):
    job = owned_job(request, job_id, user)
    if not await request.app.state.jobs.cancel(job):
        raise HTTPException(409, "Report saving has started; wait for completion.")
    return public_job(job)
