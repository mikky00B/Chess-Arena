from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.api.matchmaking import get_matchmaking_service
from app.core.database import get_session
from app.game.state import GameSourceType
from app.main import create_app
from app.models import Game, User
from app.services.matchmaking_service import MatchmakingService


class FakeSession:
    def __init__(self) -> None:
        self.users: dict[UUID, User] = {}
        self.games: dict[UUID, Game] = {}

    async def get(self, model: type[Any], entity_id: UUID) -> Any:
        if model is User:
            return self.users.get(entity_id)
        if model is Game:
            return self.games.get(entity_id)
        return None

    def add(self, entity: Any) -> None:
        if isinstance(entity, Game):
            if entity.id is None:
                entity.id = uuid4()
            self.games[entity.id] = entity

    async def commit(self) -> None:
        return None

    async def refresh(self, _entity: Any) -> None:
        return None


def make_user(username: str) -> User:
    return User(id=uuid4(), username=username, rating=1200, created_at=datetime.now(UTC))


def make_client(session: FakeSession, service: MatchmakingService) -> TestClient:
    app = create_app()

    async def override_session() -> AsyncIterator[FakeSession]:
        yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_matchmaking_service] = lambda: service
    return TestClient(app)


def test_matchmaking_queue_then_status() -> None:
    session = FakeSession()
    player = make_user("player")
    session.users[player.id] = player
    client = make_client(session, MatchmakingService())

    response = client.post(
        "/api/matchmaking/queue",
        json={
            "player_id": str(player.id),
            "time_control": {"initial_seconds": 300, "increment_seconds": 2},
            "rated": True,
        },
    )
    status_response = client.get(
        "/api/matchmaking/status",
        params={"player_id": str(player.id)},
    )

    assert response.status_code == 201
    assert response.json()["matched"] is False
    assert status_response.json()["queued"] is True
    assert status_response.json()["rated"] is True


def test_matchmaking_creates_general_game_for_compatible_players() -> None:
    session = FakeSession()
    white = make_user("white")
    black = make_user("black")
    session.users[white.id] = white
    session.users[black.id] = black
    client = make_client(session, MatchmakingService())

    client.post(
        "/api/matchmaking/queue",
        json={
            "player_id": str(white.id),
            "time_control": {"initial_seconds": 300},
        },
    )
    response = client.post(
        "/api/matchmaking/queue",
        json={
            "player_id": str(black.id),
            "time_control": {"initial_seconds": 300},
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["matched"] is True
    assert body["game"]["source_type"] == GameSourceType.GENERAL_MATCHMAKING
    assert len(session.games) == 1
