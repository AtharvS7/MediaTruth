"""Bound multipart request intake before Starlette spools uploaded media."""
import asyncio
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse


class MediaIntakeMiddleware:
    def __init__(self, app, max_active=2):
        self.app = app
        self.slots = asyncio.Semaphore(max_active)

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        json_request = path.startswith('/worker/') or path.startswith('/uploads')
        if scope["type"] != "http" or scope.get("method") != "POST" or (not json_request and path not in {
            "/image/analyze", "/image/clean-metadata", "/video/analyze", "/jobs"
        }):
            return await self.app(scope, receive, send)
        limit = (500 if path in {"/video/analyze", "/jobs"} else 50) * 1024 * 1024 + 65536
        if json_request:
            limit = 600_000 if path.startswith('/worker/') else 16_384
        headers = dict(scope.get("headers", []))
        try:
            declared = int(headers.get(b"content-length", b"0"))
            if declared < 0:
                raise ValueError()
        except ValueError:
            return await JSONResponse({"detail": "Invalid Content-Length"}, 400)(scope, receive, send)
        if declared > limit:
            return await JSONResponse({"detail": "Upload too large"}, 413)(scope, receive, send)
        if self.slots.locked():
            return await JSONResponse({"detail": "Server busy. Try again shortly."}, 503,
                                      headers={"Retry-After": "10"})(scope, receive, send)
        async with self.slots:
            received = 0

            async def bounded_receive():
                nonlocal received
                message = await receive()
                received += len(message.get("body", b""))
                if received > limit:
                    raise HTTPException(413, "Upload too large")
                return message

            await self.app(scope, bounded_receive, send)
