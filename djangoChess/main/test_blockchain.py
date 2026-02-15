from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from main.models import Game
from main.utils import calculate_elo


@pytest.fixture
def players(db):
    white = User.objects.create_user(username="white", password="pw")
    black = User.objects.create_user(username="black", password="pw")
    white.profile.ethereum_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb4"
    black.profile.ethereum_address = "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed"
    white.profile.save(update_fields=["ethereum_address"])
    black.profile.save(update_fields=["ethereum_address"])
    return white, black


@pytest.fixture
def completed_game(players):
    white, black = players
    return Game.objects.create(
        white_player=white,
        black_player=black,
        bet_amount=Decimal("0.01"),
        is_active=False,
        winner=white,
    )


@pytest.mark.django_db
def test_elo_updates_on_game_end(players):
    white, black = players
    game = Game.objects.create(white_player=white, black_player=black)
    white_initial = white.profile.rating
    black_initial = black.profile.rating

    game.is_active = False
    game.winner = white
    game.save()

    white.profile.refresh_from_db()
    black.profile.refresh_from_db()
    assert white.profile.rating > white_initial
    assert black.profile.rating < black_initial


@pytest.mark.django_db
def test_calculate_elo_draw_expected_behavior():
    higher = 1600
    lower = 1200
    higher_after = calculate_elo(higher, lower, 0.5)
    lower_after = calculate_elo(lower, higher, 0.5)
    assert higher_after < higher
    assert lower_after > lower


@pytest.mark.django_db
def test_profile_created_via_signal():
    user = User.objects.create_user(username="new_user", password="pw")
    assert user.profile.rating == 1200


@pytest.mark.django_db
def test_game_signature_fields_present_after_completion(completed_game):
    completed_game.refresh_from_db()
    assert completed_game.is_active is False
    assert completed_game.winner is not None
