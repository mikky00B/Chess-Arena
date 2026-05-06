from datetime import UTC, datetime, timedelta

import pytest

from app.game.state import GameResult, GameState, GameStatus, ResultReason, TimeControl
from app.services.clock_service import ClockError, ClockService
from app.services.move_service import MoveService, MoveServiceError


def make_game(*, seconds: int = 300) -> GameState:
    return GameState(
        id="game-1",
        white_player_id="white",
        black_player_id="black",
        time_control=TimeControl(initial_seconds=seconds),
    )


def test_starting_game_starts_white_clock_immediately() -> None:
    game = make_game(seconds=60)
    start = datetime(2026, 5, 6, 12, 0, tzinfo=UTC)

    ClockService().start(game, now=start)
    snapshot = ClockService().snapshot(game, now=start + timedelta(seconds=9))

    assert game.status == GameStatus.IN_PROGRESS
    assert snapshot.white_time_seconds == 51
    assert snapshot.black_time_seconds == 60


def test_first_move_consumes_white_time() -> None:
    game = make_game(seconds=60)
    clock = ClockService()
    moves = MoveService(clock_service=clock)
    start = datetime(2026, 5, 6, 12, 0, tzinfo=UTC)
    clock.start(game, now=start)

    moves.submit_move(game, player_id="white", uci="e2e4", now=start + timedelta(seconds=12))

    assert game.white_time_seconds == 48
    assert game.black_time_seconds == 60


def test_move_service_rejects_moves_when_game_not_in_progress() -> None:
    game = make_game()

    with pytest.raises(MoveServiceError, match="in progress"):
        MoveService().submit_move(
            game,
            player_id="white",
            uci="e2e4",
            now=datetime.now(UTC),
        )


def test_timeout_can_be_claimed_without_waiting_for_another_move() -> None:
    game = make_game(seconds=5)
    clock = ClockService()
    start = datetime(2026, 5, 6, 12, 0, tzinfo=UTC)
    clock.start(game, now=start)

    clock.claim_timeout(game, claimant_id="black", now=start + timedelta(seconds=6))

    assert game.status == GameStatus.FINISHED
    assert game.result == GameResult.BLACK_WIN
    assert game.result_reason == ResultReason.TIMEOUT
    assert game.winner_id == "black"


def test_timeout_claim_requires_an_actual_expired_clock() -> None:
    game = make_game(seconds=30)
    clock = ClockService()
    start = datetime(2026, 5, 6, 12, 0, tzinfo=UTC)
    clock.start(game, now=start)

    with pytest.raises(ClockError, match="no player"):
        clock.claim_timeout(game, claimant_id="black", now=start + timedelta(seconds=10))


def test_resignation_finishes_game_for_opponent() -> None:
    game = make_game()
    clock = ClockService()
    start = datetime(2026, 5, 6, 12, 0, tzinfo=UTC)
    clock.start(game, now=start)

    MoveService(clock_service=clock).resign(game, player_id="white", now=start)

    assert game.result == GameResult.BLACK_WIN
    assert game.result_reason == ResultReason.RESIGNATION
    assert game.winner_id == "black"
