from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from main.models import Game
from main.timer_sync import sync_game_clock


@pytest.mark.django_db
def test_sync_game_clock_no_drain_before_first_move():
    white = User.objects.create_user(username="timer_white", password="pw")
    black = User.objects.create_user(username="timer_black", password="pw")
    game = Game.objects.create(white_player=white, black_player=black)
    now = timezone.now()

    result = sync_game_clock(game, now=now)

    assert result["changed"] is False
    assert game.white_time == 600.0
    assert game.black_time == 600.0


@pytest.mark.django_db
def test_sync_game_clock_deducts_active_side_and_times_out():
    white = User.objects.create_user(username="timer_white2", password="pw")
    black = User.objects.create_user(username="timer_black2", password="pw")
    game = Game.objects.create(
        white_player=white,
        black_player=black,
        current_fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        white_time=1.0,
        black_time=200.0,
        last_move_timestamp=timezone.now() - timedelta(seconds=3),
        is_active=True,
    )

    result = sync_game_clock(game, now=timezone.now())

    assert result["changed"] is True
    assert result["timed_out"] is True
    assert game.white_time == 0.0
    assert game.is_active is False
    assert game.winner == black


@pytest.mark.django_db
def test_sync_game_clock_uses_black_clock_when_black_to_move():
    white = User.objects.create_user(username="timer_white3", password="pw")
    black = User.objects.create_user(username="timer_black3", password="pw")
    game = Game.objects.create(
        white_player=white,
        black_player=black,
        current_fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b KQkq - 0 1",
        white_time=300.0,
        black_time=300.0,
        last_move_timestamp=timezone.now() - timedelta(seconds=5),
        is_active=True,
    )

    sync_game_clock(game, now=timezone.now())

    assert game.white_time == 300.0
    assert game.black_time < 300.0
