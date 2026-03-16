"""
MediaTruth - AI Media Forensics Platform
Main FastAPI Application Entry Point
"""

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from dotenv import load_dotenv

from api.routes import image_router, video_router, scan_router, health_router
from services.model_loader import ModelLoader
from utils.logger import setup_logger

load_dotenv()
setup_logger()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: load models on startup, cleanup on shutdown."""
    logger.info("🚀 MediaTruth backend starting up...")
    loader = ModelLoader()
    await loader.load_all_models()
    app.state.model_loader = loader
    logger.info("✅ All models loaded successfully.")
    yield
    logger.info("🛑 Shutting down MediaTruth backend...")


app = FastAPI(
    title="MediaTruth API",
    description="AI Media Forensics Platform — Detect AI-generated, AI-edited, and traditionally edited media.",
    version="1.0.0",
    lifespan=lifespan,
)

# ── Middleware ──────────────────────────────────────────────────────────────────
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ─────────────────────────────────────────────────────────────────────
app.include_router(health_router, prefix="/health", tags=["Health"])
app.include_router(image_router, prefix="/image", tags=["Image Analysis"])
app.include_router(video_router, prefix="/video", tags=["Video Analysis"])
app.include_router(scan_router, prefix="/scan", tags=["Scan History"])


@app.get("/")
async def root():
    return {
        "service": "MediaTruth API",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": ["/image/analyze", "/video/analyze", "/scan/history", "/scan/{id}"],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("ENV", "production") == "development",
        workers=int(os.getenv("WORKERS", 1)),
    )
