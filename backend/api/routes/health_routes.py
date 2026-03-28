"""
Health check routes.

BUG-021 fix: Public health endpoint only returns {"status": "healthy"}.
  Model details are not exposed to unauthenticated requests.
"""

import logging
from typing import Dict

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
async def health(request: Request) -> Dict[str, str]:
    """Public health check — returns service status only.

    Does NOT expose model names, device info, or internal state.
    For ops readiness, use /health/ready with an internal secret.
    """
    return {"status": "healthy"}


@router.get("/ready")
async def readiness(request: Request) -> Dict[str, bool]:
    """Readiness probe — indicates whether models have finished loading.

    This is intended for internal/ops use (e.g., Kubernetes readiness probe).
    """
    loader = getattr(request.app.state, "model_loader", None)
    return {"ready": loader.is_ready() if loader else False}
