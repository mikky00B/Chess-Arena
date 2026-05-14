from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.middleware import RateLimitMiddleware, RequestContextMiddleware
from app.core.rate_limit import InMemoryRateLimiter


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()
    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        RateLimitMiddleware,
        limiter=InMemoryRateLimiter(
            capacity=settings.rate_limit_capacity,
            window_seconds=settings.rate_limit_window_seconds,
        ),
        protected_prefixes=(
            "/api/games",
            "/api/matchmaking",
            "/api/challenges",
            "/api/settlements",
            "/api/tournaments",
            "/api/fair-play",
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["authorization", "content-type", "x-request-id"],
    )
    app.include_router(api_router)
    return app


app = create_app()
