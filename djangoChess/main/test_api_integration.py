from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from main.models import Game, SecurityEvent


@pytest.fixture
def users(db):
    white = User.objects.create_user(username="white_api", password="pw")
    black = User.objects.create_user(username="black_api", password="pw")
    outsider = User.objects.create_user(username="outsider_api", password="pw")
    white.profile.ethereum_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb4"
    black.profile.ethereum_address = "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed"
    white.profile.save(update_fields=["ethereum_address"])
    black.profile.save(update_fields=["ethereum_address"])
    return white, black, outsider


@pytest.mark.django_db
def test_get_signature_generates_on_demand(client, users, monkeypatch):
    white, black, _ = users
    fake_sig = (27, "0x" + "1" * 64, "0x" + "2" * 64)
    monkeypatch.setattr("main.signals.generate_winner_signature", lambda *_: fake_sig)
    monkeypatch.setattr("main.blockchain_views.generate_winner_signature", lambda *_: fake_sig)

    game = Game.objects.create(
        white_player=white,
        black_player=black,
        bet_amount=Decimal("0.05"),
        is_active=False,
        winner=white,
    )

    assert client.login(username="white_api", password="pw")
    response = client.get(f"/chess/api/get-signature/{game.id}/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["signature"]["v"] == 27

    game.refresh_from_db()
    assert game.signature_v == 27
    assert game.signature_r == fake_sig[1]
    assert SecurityEvent.objects.filter(event_type="signature_generated", game=game).exists()


@pytest.mark.django_db
def test_mark_payout_claimed_requires_verified_tx(client, users, monkeypatch):
    white, black, _ = users
    game = Game.objects.create(
        white_player=white,
        black_player=black,
        bet_amount=Decimal("0.05"),
        is_active=False,
        winner=white,
        signature_v=27,
        signature_r="0x" + "1" * 64,
        signature_s="0x" + "2" * 64,
    )

    monkeypatch.setattr("main.blockchain_views.verify_payout_transaction", lambda *_: True)

    assert client.login(username="white_api", password="pw")
    tx_hash = "0x" + "a" * 64
    response = client.post(
        f"/chess/api/mark-payout/{game.id}/",
        data=f'{{"tx_hash": "{tx_hash}"}}',
        content_type="application/json",
    )
    assert response.status_code == 200

    game.refresh_from_db()
    assert game.payout_claimed is True
    assert game.claim_tx_hash == tx_hash
    assert SecurityEvent.objects.filter(event_type="payout_marked_claimed", game=game).exists()


@pytest.mark.django_db
def test_fairplay_report_authorization(client, users):
    white, black, outsider = users
    game = Game.objects.create(
        white_player=white,
        black_player=black,
        bet_amount=Decimal("0"),
        is_active=False,
    )

    assert client.login(username="outsider_api", password="pw")
    forbidden = client.get(f"/chess/api/fairplay-report/{game.id}/")
    assert forbidden.status_code == 403

    assert client.login(username="white_api", password="pw")
    allowed = client.get(f"/chess/api/fairplay-report/{game.id}/")
    assert allowed.status_code == 200
    payload = allowed.json()
    assert payload["success"] is True
    assert payload["report"]["risk"] in {"low", "medium", "high", "unknown"}


@pytest.mark.django_db
def test_health_endpoints(client):
    live = client.get("/chess/health/live/")
    assert live.status_code == 200
    ready = client.get("/chess/health/ready/")
    assert ready.status_code in (200, 503)
