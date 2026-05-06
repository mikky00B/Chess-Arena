from datetime import UTC, datetime
from uuid import uuid4

import chess
import pytest

from app.game.state import GameResult, GameSourceType, GameStatus, PlayerColor, ResultReason
from app.models import Game, RatingUpdate, User
from app.services.rating_application_service import (
    PersistentRatingService,
    RatingAlreadyAppliedError,
    RatingApplicationError,
)


def make_user(username: str, rating: int) -> User:
    return User(id=uuid4(), username=username, rating=rating, created_at=datetime.now(UTC))


def make_game(
    *,
    white: User,
    black: User,
    rated: bool = True,
    status: GameStatus = GameStatus.FINISHED,
    result: GameResult | None = GameResult.WHITE_WIN,
) -> Game:
    now = datetime(2026, 5, 6, 12, 0, tzinfo=UTC)
    return Game(
        id=uuid4(),
        white_player_id=white.id,
        black_player_id=black.id,
        status=status,
        current_fen=chess.STARTING_FEN,
        time_control_initial_seconds=300,
        time_control_increment_seconds=0,
        white_time_seconds=280,
        black_time_seconds=275,
        last_clock_started_at=None,
        turn=PlayerColor.WHITE,
        rated=rated,
        result=result,
        result_reason=ResultReason.CHECKMATE if result is not None else None,
        winner_id=white.id if result == GameResult.WHITE_WIN else None,
        source_type=GameSourceType.GENERAL_MATCHMAKING,
        source_id=None,
        draw_offered_by=None,
        created_at=now,
        started_at=now,
        finished_at=now,
        updated_at=now,
        white_player=white,
        black_player=black,
    )


def test_apply_to_loaded_game_updates_ratings_once_from_pre_game_snapshots() -> None:
    white = make_user("white", 1600)
    black = make_user("black", 1400)
    game = make_game(white=white, black=black, result=GameResult.BLACK_WIN)

    update = PersistentRatingService().apply_to_loaded_game(
        game,
        now=datetime(2026, 5, 6, 13, 0, tzinfo=UTC),
    )

    assert update is not None
    assert update.white_rating_before == 1600
    assert update.black_rating_before == 1400
    assert update.white_rating_after == 1576
    assert update.black_rating_after == 1424
    assert white.rating == 1576
    assert black.rating == 1424
    assert game.rating_update is update


def test_unrated_games_do_not_create_rating_updates() -> None:
    white = make_user("white", 1200)
    black = make_user("black", 1200)
    game = make_game(white=white, black=black, rated=False)

    update = PersistentRatingService().apply_to_loaded_game(game)

    assert update is None
    assert white.rating == 1200
    assert black.rating == 1200


def test_rating_application_requires_finished_game() -> None:
    game = make_game(
        white=make_user("white", 1200),
        black=make_user("black", 1200),
        status=GameStatus.IN_PROGRESS,
        result=None,
    )

    with pytest.raises(RatingApplicationError, match="finished"):
        PersistentRatingService().apply_to_loaded_game(game)


def test_rating_application_rejects_second_application() -> None:
    white = make_user("white", 1200)
    black = make_user("black", 1200)
    game = make_game(white=white, black=black)
    game.rating_update = RatingUpdate(
        id=uuid4(),
        game_id=game.id,
        white_player_id=white.id,
        black_player_id=black.id,
        white_rating_before=1200,
        black_rating_before=1200,
        white_rating_after=1216,
        black_rating_after=1184,
        created_at=datetime.now(UTC),
    )

    with pytest.raises(RatingAlreadyAppliedError, match="already"):
        PersistentRatingService().apply_to_loaded_game(game)
