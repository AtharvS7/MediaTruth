from .routes.image_routes import router as image_router
from .routes.video_routes import router as video_router
from .routes.scan_routes import router as scan_router
from .routes.health_routes import router as health_router

__all__ = ["image_router", "video_router", "scan_router", "health_router"]
