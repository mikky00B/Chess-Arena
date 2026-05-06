import pytest

from app.game.rating import RatingService
from app.game.state import GameResult


def test_rating_calculates_both_players_from_pre_game_snapshots() -> None:
    service = RatingService(k_factor=32)

    change = service.calculate(white_rating=1600, black_rating=1400, result=GameResult.BLACK_WIN)

    assert change.white_before == 1600
    assert change.black_before == 1400
    assert change.white_after == 1576
    assert change.black_after == 1424
    assert change.white_delta == -24
    assert change.black_delta == 24


def test_aborted_games_do_not_change_ratings() -> None:
    with pytest.raises(ValueError, match="aborted"):
        RatingService().calculate(white_rating=1500, black_rating=1500, result=GameResult.ABORTED)
