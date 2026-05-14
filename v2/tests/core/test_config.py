from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_rejects_default_local_database() -> None:
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            secret_key="x" * 40,
            database_url="postgresql+asyncpg://chess_arena:chess_arena@localhost/db",
            redis_url="redis://redis:6379/0",
            cors_allowed_origins=["https://chess.example"],
        )
