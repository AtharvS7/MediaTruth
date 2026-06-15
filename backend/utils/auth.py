"""
Auth utility — JWT bearer token extraction for FastAPI.

Provides two auth dependencies:
  - get_current_user: Strict — raises HTTP 401 if token is invalid
  - get_optional_user: Lenient — returns None for anonymous access

Uses Supabase RS256 token verification via network call.
"""

import asyncio
import logging
from typing import Optional

from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from services.supabase_service import get_supabase_client

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=True)
optional_security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Strict auth dependency — raises HTTP 401 if token is invalid."""
    try:
        token: str = credentials.credentials
        supabase = get_supabase_client()

        loop = asyncio.get_running_loop()
        user_response = await loop.run_in_executor(
            None, supabase.auth.get_user, token
        )
        user = user_response.user

        if not user:
            raise HTTPException(status_code=401, detail="Invalid token payload")

        return {"id": user.id, "email": user.email}
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"JWT verification failed: {e}")
        raise HTTPException(
            status_code=401, detail="Invalid or expired authorization token"
        )


async def get_optional_user(request: Request) -> Optional[dict]:
    """
    Lenient auth dependency — returns None when no valid token is present.
    Used for endpoints that support anonymous access.

    Uses Supabase network verification (RS256-compatible).
    """
    auth: str = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None

    token: str = auth.removeprefix("Bearer ").strip()
    if not token:
        return None

    try:
        supabase = get_supabase_client()
        loop = asyncio.get_running_loop()
        user_response = await loop.run_in_executor(
            None, supabase.auth.get_user, token
        )
        user = user_response.user
        if user:
            return {"id": user.id, "email": user.email}
    except Exception as e:
        logger.debug(f"Optional auth failed (non-critical): {e}")

    return None
