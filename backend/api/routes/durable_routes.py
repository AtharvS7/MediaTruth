"""Bounded upload handoff and lease-fenced worker API."""
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from services.durable_jobs import DurableJobs, public_job, wake_worker
from services.evidence import public_report
from utils.auth import get_current_user

router = APIRouter()


def coordinator():
    if os.getenv('JOB_BACKEND', 'local') != 'supabase':
        raise HTTPException(404, 'Durable uploads are not enabled')
    return DurableJobs()


async def action(db, name, **args):
    try:
        return await db.call(name, **args)
    except Exception as exc:
        # Do not expose provider responses, SQL details or credentials.
        message = str(exc)
        if 'Job not found' in message:
            raise HTTPException(404, 'Job not found') from None
        if any(word in message for word in ('Queue full', 'quota reached')):
            raise HTTPException(503, 'Capacity limit reached', headers={'Retry-After': '30'}) from None
        if any(word in message for word in ('Idempotency conflict', 'Expired worker lease')):
            raise HTTPException(409, 'Request conflicts with job state') from None
        raise HTTPException(503, 'Job service temporarily unavailable') from None


class UploadRequest(BaseModel):
    kind: Literal['image', 'video', 'clean']
    filename: str = Field(min_length=1, max_length=255)
    input_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    byte_size: int = Field(gt=0, le=50_000_000)
    idempotency_key: UUID


@router.post('/uploads', status_code=201)
async def initiate(body: UploadRequest, user=Depends(get_current_user), db=Depends(coordinator)):
    if not await db.worker_online():
        await wake_worker()
        raise HTTPException(503, 'Processing worker is offline or starting. Please try again shortly.')
    await db.cleanup()
    job = await action(db, 'reserve', owner=user['id'], **body.model_dump(mode='json'))
    upload = await db.upload_url(job) if job['status'] == 'uploading' else None
    return {'job': public_job(job), 'upload': upload}


@router.post('/uploads/{job_id}/finalize', status_code=202)
async def finalize(job_id: UUID, user=Depends(get_current_user), db=Depends(coordinator)):
    job = await action(db, 'get', id=str(job_id), owner=user['id'])
    if job['status'] == 'uploading':
        try:
            await db.check_object(job)
        except Exception:
            raise HTTPException(422, 'Upload is missing or does not match its reserved size') from None
    job = await action(db, 'finalize', id=str(job_id), owner=user['id'])
    await wake_worker()
    return public_job(job)


@router.get('/jobs/{job_id}/download')
async def download(job_id: UUID, user=Depends(get_current_user), db=Depends(coordinator)):
    job = await action(db, 'get', id=str(job_id), owner=user['id'])
    if job['kind'] != 'clean' or job['status'] != 'completed' or job['output_deleted']:
        raise HTTPException(404, 'Export unavailable or expired')
    # Enforce retention even if the worker/cleanup process has been asleep.
    created = datetime.fromisoformat(job['created_at'].replace('Z', '+00:00'))
    if created <= datetime.now(timezone.utc) - timedelta(hours=24):
        raise HTTPException(404, 'Export unavailable or expired')
    return {'url': await db.download_url(job, True)}


async def worker_auth(request: Request):
    expected = os.getenv('WORKER_SECRET', '')
    supplied = request.headers.get('Authorization', '').removeprefix('Bearer ')
    if len(expected) < 32 or not hmac.compare_digest(expected, supplied):
        raise HTTPException(401, 'Invalid worker credential')


class WorkerUpdate(BaseModel):
    lease: UUID
    stage: Literal['loading_models', 'analyzing', 'saving'] = 'analyzing'
    result: dict | None = None


@router.post('/worker/claim', dependencies=[Depends(worker_auth)])
async def claim(db=Depends(coordinator)):
    await db.checkin()
    await db.cleanup()
    job = await action(db, 'claim')
    if not job:
        return {'job': None}
    return {'job': {key: job[key] for key in
                   ('id', 'kind', 'lease', 'input_sha256', 'byte_size', 'filename')},
            'download_url': await db.download_url(job),
            'output_upload': await db.upload_url(job, True) if job['kind'] == 'clean' else None}


@router.post('/worker/{job_id}/{operation}', dependencies=[Depends(worker_auth)])
async def update(job_id: UUID, operation: Literal['heartbeat', 'complete', 'fail'],
                 body: WorkerUpdate, db=Depends(coordinator)):
    await db.checkin()
    args = body.model_dump(mode='json')
    if operation == 'complete':
        if body.result is None:
            raise HTTPException(422, 'Missing report')
        current = await action(db, 'inspect', id=str(job_id), lease=str(body.lease))
        if current['kind'] == 'clean':
            await db.check_object(current, True)
        # Export results carry no caller-selected paths or URLs.
        args['result'] = ({'export': 'metadata_removed', 'limitations': 'Invisible watermarks may remain'}
                          if current['kind'] == 'clean'
                          else public_report(body.result))
    job = await action(db, operation, id=str(job_id), **args)
    return public_job(job)
