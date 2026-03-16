"""
Auth utility — optional JWT bearer token extraction.
Returns user dict if valid token provided, else None.
"""

import os
import logging
from typing import Optional
from fastapi import Request
from jose import jwt, JWTError

logger = logging.getLogger(__name__)
SECRET = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
ALGORITHM = "HS256"


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
