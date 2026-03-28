"""
Auth utility — optional JWT bearer token extraction.
Returns user dict if valid token provided, else None.

BUG-001 fixes:
  - Added missing `from jose import jwt, JWTError` import
  - Supabase client is now a module-level singleton (no per-request creation)
  - Synchronous supabase.auth.get_user() wrapped in run_in_executor()
  - get_optional_user returns None instead of raising on invalid/missing token
"""

import asyncio
import logging
import os
from typing import Optional

from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

from services.supabase_service import get_supabase_client

logger = logging.getLogger(__name__)
SECRET: str = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
ALGORITHM: str = "HS256"

security = HTTPBearer(auto_error=True)
optional_security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Strict auth dependency — raises HTTP 401 if token is invalid."""
    try:
        token: str = credentials.credentials
        supabase = get_supabase_client()

        # Wrap blocking Supabase network call so it doesn't stall the event loop
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
    """
    auth: str = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None

    token: str = auth.removeprefix("Bearer ").strip()
    if not token:
        return None

    # Fast local JWT decode first (avoids network call for clearly bad tokens)
    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
        return {"id": payload.get("sub"), "email": payload.get("email")}
    except JWTError:
        pass

    # Fallback: try Supabase network verification
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
