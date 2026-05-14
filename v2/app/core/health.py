from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import cast

from redis.asyncio import Redis
from sqlalchemy import text

from app.core.database import engine


async def check_database() -> str:
    try:
        async with engine.connect() as connection:
            await asyncio.wait_for(connection.execute(text("SELECT 1")), timeout=2)
    except Exception:
        return "unavailable"
    return "ok"


async def check_redis(redis_url: str) -> str:
    redis = Redis.from_url(redis_url)
    try:
        await asyncio.wait_for(cast(Awaitable[bool], redis.ping()), timeout=2)
    except Exception:
        return "unavailable"
    finally:
        await redis.aclose()
    return "ok"
