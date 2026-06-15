"""
FastAPI application entrypoint for MediaTruth backend.

Startup sequence:
  1. Validate required environment variables
  2. Configure CORS middleware
  3. Load ML models into memory (thread pool)
  4. Mount API routers

Security features:
  - Rate limiting via slowapi
  - Global exception handler prevents stack trace leakage
  - Environment variable validation on startup
"""

import logging
import os
import traceback
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from utils.logger import setup_logger
from services.model_loader import ModelLoader
from api.routes import image_routes, video_routes, scan_routes, health_routes

load_dotenv()
setup_logger()
logger = logging.getLogger(__name__)

# ── Environment validation ────────────────────────────────────────────────────
REQUIRED_VARS = ["SUPABASE_URL", "SUPABASE_SERVICE_KEY"]
for var in REQUIRED_VARS:
    if not os.getenv(var):
        raise RuntimeError(
            f"Missing required environment variable: {var}. "
            f"Copy .env.example to .env and fill in your values."
        )

# ── Rate limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: load ML models
    loader = ModelLoader()
    await loader.load_all_models()
    app.state.model_loader = loader
    logger.info("MediaTruth backend ready.")
    yield
    # Shutdown: cleanup
    logger.info("Shutting down MediaTruth backend.")


# ── App factory ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="MediaTruth API",
    description="AI Media Forensics — deepfake, GAN, and manipulation detection.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if os.getenv("ENV", "development") == "development" else None,
    redoc_url=None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Global exception handler ─────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions and return a generic 500 without leaking stack traces."""
    logger.error(f"Unhandled error on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again later."},
    )


# ── CORS ──────────────────────────────────────────────────────────────────────
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in allowed_origins],
    allow_credentials=True,
    # SEC-04: Explicit method/header lists — never use wildcards with allow_credentials
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With", "Accept"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health_routes.router, prefix="/health", tags=["Health"])
app.include_router(image_routes.router, prefix="/image", tags=["Image Analysis"])
app.include_router(video_routes.router, prefix="/video", tags=["Video Analysis"])
app.include_router(scan_routes.router, prefix="/scan", tags=["Scan History"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        workers=int(os.getenv("WORKERS", 1)),
        reload=os.getenv("ENV", "development") == "development",
    )
