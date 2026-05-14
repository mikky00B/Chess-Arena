from fastapi import APIRouter

from app.core.config import get_settings
from app.core.health import check_database, check_redis

router = APIRouter()


@router.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "ok", "service": "chess-arena-v2"}


@router.get("/health/ready")
async def health_ready() -> dict[str, object]:
    settings = get_settings()
    database_status = await check_database() if settings.strict_health_checks else "configured"
    redis_status = (
        await check_redis(settings.redis_url) if settings.strict_health_checks else "configured"
    )
    ready = database_status in {"ok", "configured"} and redis_status in {"ok", "configured"}
    return {
        "status": "ok" if ready else "degraded",
        "environment": settings.environment,
        "checks": {
            "app": "ok",
            "database": database_status if settings.database_url else "missing",
            "redis": redis_status if settings.redis_url else "missing",
        },
    }
