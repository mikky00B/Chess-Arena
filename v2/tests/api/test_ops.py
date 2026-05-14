from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def test_cors_preflight_allows_configured_origin() -> None:
    get_settings.cache_clear()
    client = TestClient(create_app())

    response = client.options(
        "/api/games",
        headers={
            "origin": "http://localhost:3000",
            "access-control-request-method": "POST",
            "access-control-request-headers": "content-type,x-request-id",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_rate_limit_protects_game_actions(monkeypatch) -> None:
    monkeypatch.setenv("CHESS_ARENA_RATE_LIMIT_CAPACITY", "1")
    monkeypatch.setenv("CHESS_ARENA_RATE_LIMIT_WINDOW_SECONDS", "60")
    get_settings.cache_clear()
    client = TestClient(create_app())

    first = client.post("/api/games", json={})
    second = client.post("/api/games", json={})

    assert first.status_code == 422
    assert second.status_code == 429
    get_settings.cache_clear()
