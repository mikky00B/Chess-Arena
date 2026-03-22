from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from main.models import Tournament, TournamentMatch, TournamentParticipant
from main.tournament_formats import (
    build_double_elim_skeleton,
    build_round_robin_rounds,
    build_single_elim_rounds,
    build_swiss_rounds,
)


def post_json(client, path, data):
    return client.post(path, data, HTTP_ACCEPT="application/json")


@pytest.mark.django_db
def test_create_tournament_api(client):
    user = User.objects.create_user(username="creator", password="pw")
    assert client.login(username="creator", password="pw")

    response = post_json(
        client,
        "/chess/api/tournaments/create/",
        {
            "name": "Weekend Cup",
            "format": "round_robin",
            "min_players": "2",
            "max_players": "8",
            "games_per_pairing": "1",
            "entry_fee_eth": "0.01",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    tournament = Tournament.objects.get(id=payload["tournament_id"])
    assert tournament.name == "Weekend Cup"
    assert tournament.entry_fee_eth == Decimal("0.01")
    assert tournament.participants.filter(user=user).exists()


def test_round_robin_pairings_cover_players():
    rounds = build_round_robin_rounds([1, 2, 3, 4], games_per_pairing=1)
    assert len(rounds) == 3
    seeds_seen = set()
    for rnd in rounds:
        for pairing in rnd:
            seeds_seen.add(pairing.white_seed)
            seeds_seen.add(pairing.black_seed)
    assert seeds_seen == {1, 2, 3, 4}


def test_single_elim_supports_byes():
    rounds = build_single_elim_rounds([1, 2, 3], games_per_pairing=1)
    assert len(rounds) >= 1


def test_swiss_generates_configured_rounds():
    rounds = build_swiss_rounds([1, 2, 3, 4, 5, 6], rounds_count=4, games_per_pairing=1)
    assert len(rounds) == 4


def test_double_elim_has_grand_final_placeholder():
    rounds = build_double_elim_skeleton([1, 2, 3, 4], games_per_pairing=1)
    assert rounds[-1][0].metadata["bracket"] == "grand_final_placeholder"


@pytest.mark.django_db
def test_lock_start_and_report_flow(client):
    creator = User.objects.create_user(username="creator2", password="pw")
    u2 = User.objects.create_user(username="u2", password="pw")
    u3 = User.objects.create_user(username="u3", password="pw")

    t = Tournament.objects.create(
        creator=creator,
        name="Test T",
        format="round_robin",
        status="inviting",
        min_players=2,
        max_players=8,
        entry_fee_eth=Decimal("0"),
    )
    TournamentParticipant.objects.create(tournament=t, user=creator, status="accepted", deposit_verified=True, seed=1)
    TournamentParticipant.objects.create(tournament=t, user=u2, status="accepted", deposit_verified=True, seed=2)
    TournamentParticipant.objects.create(tournament=t, user=u3, status="accepted", deposit_verified=True, seed=3)

    assert client.login(username="creator2", password="pw")
    lock = post_json(client, f"/chess/api/tournaments/{t.id}/lock/", {})
    assert lock.status_code == 200
    start = post_json(client, f"/chess/api/tournaments/{t.id}/start/", {})
    assert start.status_code == 200
    t.refresh_from_db()
    assert t.status == "in_progress"

    match = TournamentMatch.objects.filter(tournament=t).first()
    assert match is not None
    assert match.game_id is not None
    report = post_json(
        client,
        f"/chess/api/tournaments/{t.id}/matches/{match.id}/report/",
        {"result": "draw"},
    )
    assert report.status_code == 200


@pytest.mark.django_db
def test_verify_deposit_before_checkin(client):
    creator = User.objects.create_user(username="creator3", password="pw")
    invited = User.objects.create_user(username="invited3", password="pw")
    t = Tournament.objects.create(
        creator=creator,
        name="Deposit T",
        format="round_robin",
        status="inviting",
        min_players=2,
        max_players=8,
        entry_fee_eth=Decimal("0.02"),
    )
    TournamentParticipant.objects.create(tournament=t, user=creator, status="accepted", deposit_verified=True)
    TournamentParticipant.objects.create(tournament=t, user=invited, status="accepted", deposit_verified=False)

    assert client.login(username="invited3", password="pw")
    check_in = post_json(client, f"/chess/api/tournaments/{t.id}/respond/", {"action": "check_in"})
    assert check_in.status_code == 400

    tx_hash = "0x" + "a" * 64
    verify = post_json(
        client,
        f"/chess/api/tournaments/{t.id}/verify-deposit/",
        {"tx_hash": tx_hash},
    )
    assert verify.status_code == 200

    check_in2 = post_json(client, f"/chess/api/tournaments/{t.id}/respond/", {"action": "check_in"})
    assert check_in2.status_code == 200


@pytest.mark.django_db
def test_tournament_detail_page_access(client):
    creator = User.objects.create_user(username="creator4", password="pw")
    participant = User.objects.create_user(username="participant4", password="pw")
    outsider = User.objects.create_user(username="outsider4", password="pw")
    t = Tournament.objects.create(
        creator=creator,
        name="Access T",
        format="round_robin",
        status="inviting",
        min_players=2,
        max_players=8,
        invite_only=True,
    )
    TournamentParticipant.objects.create(tournament=t, user=creator, status="accepted", deposit_verified=True)
    TournamentParticipant.objects.create(tournament=t, user=participant, status="accepted", deposit_verified=True)

    assert client.login(username="outsider4", password="pw")
    forbidden = client.get(f"/chess/tournaments/{t.id}/", follow=True)
    assert forbidden.status_code == 200

    assert client.login(username="participant4", password="pw")
    allowed = client.get(f"/chess/tournaments/{t.id}/")
    assert allowed.status_code == 200


@pytest.mark.django_db
def test_join_public_tournament_api(client):
    creator = User.objects.create_user(username="creator5", password="pw")
    joiner = User.objects.create_user(username="joiner5", password="pw")
    t = Tournament.objects.create(
        creator=creator,
        name="Public T",
        format="round_robin",
        status="inviting",
        min_players=2,
        max_players=8,
        invite_only=False,
        entry_fee_eth=Decimal("0"),
    )
    TournamentParticipant.objects.create(tournament=t, user=creator, status="accepted", deposit_verified=True)

    assert client.login(username="joiner5", password="pw")
    join = post_json(client, f"/chess/api/tournaments/{t.id}/join/", {})
    assert join.status_code == 200
    assert TournamentParticipant.objects.filter(tournament=t, user=joiner).exists()


@pytest.mark.django_db
def test_tournament_detail_redirects_to_active_game(client):
    creator = User.objects.create_user(username="creator6", password="pw")
    u2 = User.objects.create_user(username="u26", password="pw")
    t = Tournament.objects.create(
        creator=creator,
        name="Redirect T",
        format="single_elim",
        status="locked",
        min_players=2,
        max_players=4,
        entry_fee_eth=Decimal("0"),
    )
    TournamentParticipant.objects.create(tournament=t, user=creator, status="accepted", deposit_verified=True, seed=1)
    TournamentParticipant.objects.create(tournament=t, user=u2, status="accepted", deposit_verified=True, seed=2)

    assert client.login(username="creator6", password="pw")
    started = post_json(client, f"/chess/api/tournaments/{t.id}/start/", {})
    assert started.status_code == 200

    detail = client.get(f"/chess/tournaments/{t.id}/")
    assert detail.status_code == 302
    assert "/chess/game/" in detail.headers["Location"]


@pytest.mark.django_db
def test_create_tournament_form_redirects_to_detail(client):
    user = User.objects.create_user(username="creator_form", password="pw")
    assert client.login(username="creator_form", password="pw")
    response = client.post(
        "/chess/api/tournaments/create/",
        {
            "name": "Form Cup",
            "format": "round_robin",
            "min_players": "2",
            "max_players": "8",
            "games_per_pairing": "1",
            "entry_fee_eth": "0",
        },
        follow=False,
    )
    assert response.status_code == 302
    assert "/chess/tournaments/" in response.headers["Location"]


@pytest.mark.django_db
def test_invite_link_accepts_for_correct_user(client):
    owner = User.objects.create_user(username="owner_inv", password="pw")
    invitee = User.objects.create_user(username="invitee_inv", password="pw")
    t = Tournament.objects.create(
        creator=owner,
        name="Invite T",
        format="round_robin",
        status="inviting",
        min_players=2,
        max_players=8,
    )
    TournamentParticipant.objects.create(tournament=t, user=owner, status="accepted", deposit_verified=True)
    assert client.login(username="owner_inv", password="pw")
    invite_resp = client.post(f"/chess/api/tournaments/{t.id}/invite/", {"username": "invitee_inv"}, HTTP_ACCEPT="application/json")
    assert invite_resp.status_code == 200

    from main.models import TournamentInvite

    invite = TournamentInvite.objects.get(tournament=t, invitee=invitee)
    assert client.login(username="invitee_inv", password="pw")
    accept = client.get(f"/chess/tournaments/invite/{invite.token}/", follow=False)
    assert accept.status_code == 302
    assert f"/chess/tournaments/{t.id}/" in accept.headers["Location"]


@pytest.mark.django_db
def test_owner_can_cancel_before_deposits_not_after(client):
    owner = User.objects.create_user(username="owner_cancel", password="pw")
    u2 = User.objects.create_user(username="u2_cancel", password="pw")
    t = Tournament.objects.create(
        creator=owner,
        name="Cancel T",
        format="round_robin",
        status="inviting",
        min_players=2,
        max_players=8,
        entry_fee_eth=Decimal("0.05"),
    )
    TournamentParticipant.objects.create(tournament=t, user=owner, status="accepted", deposit_verified=False)
    TournamentParticipant.objects.create(tournament=t, user=u2, status="accepted", deposit_verified=False)

    assert client.login(username="owner_cancel", password="pw")
    cancel = post_json(client, f"/chess/api/tournaments/{t.id}/cancel/", {"reason": "test"})
    assert cancel.status_code == 200
    t.refresh_from_db()
    assert t.status == "cancelled"

    t2 = Tournament.objects.create(
        creator=owner,
        name="Cancel T2",
        format="round_robin",
        status="inviting",
        min_players=2,
        max_players=8,
        entry_fee_eth=Decimal("0.05"),
    )
    TournamentParticipant.objects.create(tournament=t2, user=owner, status="accepted", deposit_verified=True)
    blocked = post_json(client, f"/chess/api/tournaments/{t2.id}/cancel/", {"reason": "test"})
    assert blocked.status_code == 400

