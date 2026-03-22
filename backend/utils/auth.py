"""
Auth utility — optional JWT bearer token extraction.
Returns user dict if valid token provided, else None.
"""

import os
import logging
from typing import Optional
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from services.supabase_service import _get_client

logger = logging.getLogger(__name__)
SECRET = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
ALGORITHM = "HS256"

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    try:
        supabase = _get_client()
        token = credentials.credentials
        user_response = supabase.auth.get_user(token)
        user = user_response.user
        
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token payload")
            
        return {"id": user.id, "email": user.email}
    except Exception as e:
        logger.warning(f"Supabase network JWT verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired authorization token")


async def get_optional_user(request: Request) -> Optional[dict]:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
        return {"id": payload.get("sub"), "email": payload.get("email")}
    except JWTError:
        return None
