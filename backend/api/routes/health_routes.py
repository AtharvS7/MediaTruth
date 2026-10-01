"""
Health check routes.

Public health endpoint returns only {status: healthy}.
Model details are NOT exposed to unauthenticated requests.
"""

import logging
import asyncio
import os
from typing import Dict

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
async def health(request: Request) -> Dict[str, str]:
    """Public health check — returns service status only."""
    return {"status": "healthy"}


@router.get("/ready")
async def readiness(request: Request):
    """Processing readiness; liveness remains independent of worker outages."""
    if os.getenv('JOB_BACKEND', 'local') == 'supabase':
        from services.durable_jobs import DurableJobs
        try:
            ready = bool(await asyncio.wait_for(DurableJobs().worker_online(), timeout=5))
        except Exception:
            ready = False
        return JSONResponse({'ready': ready}, status_code=200 if ready else 503)
    loader = getattr(request.app.state, "model_loader", None)
    return {"ready": bool(loader.ready) if loader else False}
