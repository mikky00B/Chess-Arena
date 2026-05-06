from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter()


@router.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "ok", "service": "chess-arena-v2"}


@router.get("/health/ready")
async def health_ready() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "environment": settings.environment,
        "database": "configured" if settings.database_url else "missing",
        "redis": "configured" if settings.redis_url else "missing",
    }

