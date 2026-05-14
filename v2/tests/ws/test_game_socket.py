from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.core.database import get_session
from app.game.state import GameStatus, PlayerColor, TimeControl
from app.main import create_app
from app.models import Game, Move, User
from app.services.game_service import GameService
from app.services.persistent_gameplay_service import ParticipantAuthorizationError
from app.ws.game_socket import get_gameplay_service


class FakeSession:
    def __init__(self) -> None:
        self.games: dict[UUID, Game] = {}

    async def get(self, _model: type[Any], entity_id: UUID) -> Any:
        return self.games.get(entity_id)

    async def commit(self) -> None:
        return None


class FakeGameplayService:
    async def get_game(self, session: FakeSession, *, game_id: UUID) -> Game:
        return session.games[game_id]

    def ensure_participant(self, game: Game, *, player_id: UUID) -> None:
        if player_id not in {game.white_player_id, game.black_player_id}:
            raise ParticipantAuthorizationError("player is not a participant in this game")

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


def make_user(username: str) -> User:
    return User(id=uuid4(), username=username, rating=1200, created_at=datetime.now(UTC))


def test_game_socket_sends_initial_state_and_broadcasts_move() -> None:
    white = make_user("white")
    black = make_user("black")
    game = GameService().build_general_game(
        white_player=white,
        black_player=black,
        time_control=TimeControl(initial_seconds=300),
    )
    game.id = uuid4()
    GameService().start_general_game(game)
    session = FakeSession()
    session.games[game.id] = game
    app = create_app()

    async def override_session() -> AsyncIterator[FakeSession]:
        yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_gameplay_service] = lambda: FakeGameplayService()
    client = TestClient(app)

    with client.websocket_connect(f"/ws/games/{game.id}?player_id={white.id}") as websocket:
        initial = websocket.receive_json()
        assert initial["type"] == "game_state"
        assert initial["game"]["status"] == GameStatus.IN_PROGRESS

        websocket.send_json({"type": "move", "uci": "e2e4"})
        event = websocket.receive_json()

    assert event["type"] == "move"
    assert event["move"]["uci"] == "e2e4"
    assert event["game"]["turn"] == PlayerColor.BLACK
