from fastapi import APIRouter, Request
router = APIRouter()

@router.get("/")
async def health(request: Request):
    loader = getattr(request.app.state, "model_loader", None)
    return {
        "status": "healthy",
        "models_loaded": loader.is_ready() if loader else False,
    }
