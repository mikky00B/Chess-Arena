from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.api.games import get_game_service, get_gameplay_service
from app.core.database import get_session
from app.game.state import GameResult, GameSourceType, GameStatus, PlayerColor, ResultReason
from app.main import create_app
from app.models import Game, Move, User
from app.services.game_service import GameService
from app.services.persistent_gameplay_service import ParticipantAuthorizationError


class FakeSession:
    def __init__(self) -> None:
        self.users: dict[UUID, User] = {}
        self.games: dict[UUID, Game] = {}
        self.committed = False

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

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, _entity: Any) -> None:
        return None


class FakeGameplayService:
    async def get_game(self, session: FakeSession, *, game_id: UUID) -> Game:
        return session.games[game_id]

    async def submit_move(
        self,
        session: FakeSession,
        *,
        game_id: UUID,
        player_id: UUID,
        uci: str,
    ) -> Any:
        game = session.games[game_id]
        self.ensure_participant(game, player_id=player_id)
        move = Move(
            id=uuid4(),
            game_id=game_id,
            move_number=len(game.moves) + 1,
            player_id=player_id,
            color=game.turn,
            uci=uci,
            san="e4",
            fen_after=game.current_fen,
            played_at=datetime.now(UTC),
            white_time_seconds=game.white_time_seconds,
            black_time_seconds=game.black_time_seconds,
        )
        game.turn = PlayerColor.BLACK
        game.moves.append(move)
        return type("GameplayResult", (), {"game": game, "move": move})()

    async def resign(
        self,
        session: FakeSession,
        *,
        game_id: UUID,
        player_id: UUID,
    ) -> Game:
        game = session.games[game_id]
        self.ensure_participant(game, player_id=player_id)
        game.status = GameStatus.FINISHED
        game.result = GameResult.BLACK_WIN
        game.result_reason = ResultReason.RESIGNATION
        game.winner_id = game.black_player_id
        game.finished_at = datetime.now(UTC)
        return game

    def ensure_participant(self, game: Game, *, player_id: UUID) -> None:
        if player_id not in {game.white_player_id, game.black_player_id}:
            raise ParticipantAuthorizationError("player is not a participant in this game")


def make_user(username: str) -> User:
    return User(id=uuid4(), username=username, rating=1200, created_at=datetime.now(UTC))


def make_client(session: FakeSession) -> TestClient:
    app = create_app()

    async def override_session() -> AsyncIterator[FakeSession]:
        yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_game_service] = lambda: GameService()
    app.dependency_overrides[get_gameplay_service] = lambda: FakeGameplayService()
    return TestClient(app)


def test_create_public_general_game() -> None:
    session = FakeSession()
    white = make_user("white")
    black = make_user("black")
    session.users[white.id] = white
    session.users[black.id] = black
    client = make_client(session)

    response = client.post(
        "/api/games",
        json={
            "white_player_id": str(white.id),
            "black_player_id": str(black.id),
            "time_control": {"initial_seconds": 300, "increment_seconds": 2},
            "rated": True,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["invite_token"] is None
    assert body["game"]["status"] == GameStatus.READY
    assert body["game"]["source_type"] == GameSourceType.GENERAL_MATCHMAKING
    assert body["game"]["rated"] is True
    assert body["game"]["white_time_seconds"] == 300
    assert session.committed is True


def test_private_game_detail_requires_invite_token() -> None:
    session = FakeSession()
    white = make_user("white")
    black = make_user("black")
    session.users[white.id] = white
    session.users[black.id] = black
    client = make_client(session)

    created = client.post(
        "/api/games",
        json={
            "white_player_id": str(white.id),
            "black_player_id": str(black.id),
            "time_control": {"initial_seconds": 600},
            "private": True,
        },
    ).json()
    game_id = created["game"]["id"]

    forbidden = client.get(f"/api/games/{game_id}")
    allowed = client.get(f"/api/games/{game_id}", params={"invite_token": created["invite_token"]})

    assert forbidden.status_code == 403
    assert allowed.status_code == 200
    assert allowed.json()["source_type"] == GameSourceType.PRIVATE_GENERAL_GAME


def test_start_game_begins_server_clock() -> None:
    session = FakeSession()
    white = make_user("white")
    black = make_user("black")
    session.users[white.id] = white
    session.users[black.id] = black
    client = make_client(session)

    created = client.post(
        "/api/games",
        json={
            "white_player_id": str(white.id),
            "black_player_id": str(black.id),
            "time_control": {"initial_seconds": 300},
        },
    ).json()

    response = client.post(
        f"/api/games/{created['game']['id']}/start",
        json={"player_id": str(white.id)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == GameStatus.IN_PROGRESS
    assert body["started_at"] is not None
    assert body["last_clock_started_at"] == body["started_at"]


def test_submit_move_endpoint_returns_persisted_move() -> None:
    session = FakeSession()
    white = make_user("white")
    black = make_user("black")
    session.users[white.id] = white
    session.users[black.id] = black
    client = make_client(session)
    created = client.post(
        "/api/games",
        json={
            "white_player_id": str(white.id),
            "black_player_id": str(black.id),
            "time_control": {"initial_seconds": 300},
        },
    ).json()
    client.post(f"/api/games/{created['game']['id']}/start", json={"player_id": str(white.id)})

    response = client.post(
        f"/api/games/{created['game']['id']}/moves",
        json={"player_id": str(white.id), "uci": "e2e4"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["move"]["move_number"] == 1
    assert body["move"]["uci"] == "e2e4"
    assert body["game"]["turn"] == PlayerColor.BLACK


def test_resign_endpoint_requires_participant() -> None:
    session = FakeSession()
    white = make_user("white")
    black = make_user("black")
    outsider = make_user("outsider")
    session.users[white.id] = white
    session.users[black.id] = black
    client = make_client(session)
    created = client.post(
        "/api/games",
        json={
            "white_player_id": str(white.id),
            "black_player_id": str(black.id),
            "time_control": {"initial_seconds": 300},
        },
    ).json()

    response = client.post(
        f"/api/games/{created['game']['id']}/resign",
        json={"player_id": str(outsider.id)},
    )

    assert response.status_code == 403
