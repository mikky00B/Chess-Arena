from datetime import UTC, datetime
from uuid import uuid4

import chess
import pytest

from app.game.state import GameSourceType, GameStatus, TimeControl
from app.models import User
from app.services.game_service import GameService, GameServiceError


def make_user(username: str) -> User:
    return User(id=uuid4(), username=username, rating=1200, created_at=datetime.now(UTC))


def test_build_general_game_requires_no_wallet_or_escrow_fields() -> None:
    white = make_user("white")
    black = make_user("black")
    now = datetime(2026, 5, 6, 12, 0, tzinfo=UTC)

    game = GameService().build_general_game(
        white_player=white,
        black_player=black,
        time_control=TimeControl(initial_seconds=300, increment_seconds=2),
        rated=True,
        now=now,
    )

    assert game.status == GameStatus.READY
    assert game.source_type == GameSourceType.GENERAL_MATCHMAKING
    assert game.current_fen == chess.STARTING_FEN
    assert game.white_time_seconds == 300
    assert game.black_time_seconds == 300
    assert game.time_control_increment_seconds == 2
    assert game.rated is True
    assert game.started_at is None
    assert game.white_player is white
    assert game.black_player is black


def test_build_private_general_game_uses_private_source_type() -> None:
    game = GameService().build_general_game(
        white_player=make_user("white"),
        black_player=make_user("black"),
        time_control=TimeControl(initial_seconds=600),
        private=True,
    )

    assert game.source_type == GameSourceType.PRIVATE_GENERAL_GAME


def test_build_general_game_rejects_same_player() -> None:
    player = make_user("player")

    with pytest.raises(GameServiceError, match="different"):
        GameService().build_general_game(
            white_player=player,
            black_player=player,
            time_control=TimeControl(initial_seconds=300),
        )


def test_start_general_game_starts_server_clock() -> None:
    service = GameService()
    start = datetime(2026, 5, 6, 12, 5, tzinfo=UTC)
    game = service.build_general_game(
        white_player=make_user("white"),
        black_player=make_user("black"),
        time_control=TimeControl(initial_seconds=300),
    )

    service.start_general_game(game, now=start)

    assert game.status == GameStatus.IN_PROGRESS
    assert game.started_at == start
    assert game.last_clock_started_at == start
