from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .fairplay import analyze_game_moves
from .models import Game, Tournament, TournamentMatch, TournamentParticipant, TournamentPayout
from .tournament_formats import (
    build_double_elim_skeleton,
    build_round_robin_rounds,
    build_single_elim_rounds,
    build_swiss_rounds,
)


def generate_tournament_matches(tournament: Tournament) -> list[TournamentMatch]:
    participants = list(
        tournament.participants.filter(
            status__in=["accepted", "checked_in"], deposit_verified=True
        ).order_by("seed", "id")
    )
    if len(participants) < tournament.min_players:
        raise ValueError("Not enough verified participants to generate schedule")

    participant_ids = [p.id for p in participants]
    format_name = tournament.format

    if format_name == "round_robin":
        rounds = build_round_robin_rounds(
            participant_ids, games_per_pairing=tournament.games_per_pairing
        )
    elif format_name == "swiss":
        rounds = build_swiss_rounds(
            participant_ids,
            rounds_count=tournament.swiss_rounds or None,
            games_per_pairing=tournament.games_per_pairing,
        )
    elif format_name == "single_elim":
        rounds = build_single_elim_rounds(
            participant_ids, games_per_pairing=tournament.games_per_pairing
        )
    elif format_name == "double_elim":
        rounds = build_double_elim_skeleton(
            participant_ids, games_per_pairing=tournament.games_per_pairing
        )
    else:
        raise ValueError("Unsupported tournament format")

    participant_map = {p.id: p for p in participants}

    created_matches: list[TournamentMatch] = []
    with transaction.atomic():
        tournament.matches.all().delete()
        for round_index, pairings in enumerate(rounds, start=1):
            for pairing in pairings:
                created_matches.append(
                    TournamentMatch.objects.create(
                        tournament=tournament,
                        white_participant=participant_map.get(pairing.white_seed),
                        black_participant=participant_map.get(pairing.black_seed),
                        game=(
                            Game.objects.create(
                                white_player=participant_map[pairing.white_seed].user,
                                black_player=participant_map[pairing.black_seed].user,
                                bet_amount=Decimal("0"),
                                is_active=True,
                            )
                            if pairing.white_seed is not None
                            and pairing.black_seed is not None
                            and pairing.white_seed in participant_map
                            and pairing.black_seed in participant_map
                            else None
                        ),
                        round_number=round_index,
                        board_number=pairing.board_number,
                        game_index=pairing.game_index,
                        metadata=pairing.metadata,
                        status=(
                            "active"
                            if pairing.white_seed is not None
                            and pairing.black_seed is not None
                            and pairing.white_seed in participant_map
                            and pairing.black_seed in participant_map
                            else "scheduled"
                        ),
                    )
                )
    return created_matches


def apply_match_result(match: TournamentMatch, result: str) -> None:
    if result not in {"white_win", "black_win", "draw", "forfeit_white", "forfeit_black"}:
        raise ValueError("Invalid tournament match result")

    white = match.white_participant
    black = match.black_participant
    if not white or not black:
        raise ValueError("Cannot score result without two participants")

    if result == "draw":
        white.points += 0.5
        black.points += 0.5
        white.draws += 1
        black.draws += 1
    elif result in {"white_win", "forfeit_black"}:
        white.points += 1.0
        white.wins += 1
        black.losses += 1
    else:
        black.points += 1.0
        black.wins += 1
        white.losses += 1

    white.save(update_fields=["points", "wins", "draws", "losses", "updated_at"])
    black.save(update_fields=["points", "wins", "draws", "losses", "updated_at"])


def review_tournament_matches(tournament: Tournament, threshold: float = 70.0) -> dict:
    reviewed = 0
    flagged = 0
    for match in tournament.matches.select_related("game").all():
        if match.game is None:
            continue
        report = analyze_game_moves(list(match.game.moves.order_by("move_number")))
        risk = report.get("risk")
        risk_to_score = {"unknown": 10.0, "low": 25.0, "medium": 70.0, "high": 90.0}
        score = risk_to_score.get(risk, 0.0)
        requires_manual_review = score >= threshold
        match.suspicion_score = score
        match.requires_manual_review = requires_manual_review
        match.status = "flagged" if requires_manual_review else match.status
        match.review_status = "pending" if requires_manual_review else "approved"
        match.save(
            update_fields=[
                "suspicion_score",
                "requires_manual_review",
                "status",
                "review_status",
                "updated_at",
            ]
        )
        reviewed += 1
        if requires_manual_review:
            flagged += 1

    tournament.status = "reviewing"
    tournament.save(update_fields=["status", "updated_at"])
    return {"reviewed": reviewed, "flagged": flagged}


def calculate_payouts(tournament: Tournament) -> list[TournamentPayout]:
    if tournament.status not in {"reviewing", "finalized"}:
        raise ValueError("Tournament must be in reviewing/finalized state before payouts")

    blocked_flags = tournament.matches.filter(requires_manual_review=True, review_status="pending").exists()
    if blocked_flags:
        raise ValueError("Cannot finalize payouts while flagged matches are unresolved")

    participants = list(
        tournament.participants.filter(status__in=["accepted", "checked_in"]).order_by(
            "-points", "-buchholz", "-sonneborn_berger", "id"
        )
    )
    if not participants:
        raise ValueError("No eligible participants")

    pool = Decimal(str(tournament.total_prize_pool_eth or 0))
    if pool <= 0:
        pool = Decimal(str(tournament.entry_fee_eth or 0)) * Decimal(len(participants))

    payout_splits = [Decimal("0.60"), Decimal("0.30"), Decimal("0.10")]
    created: list[TournamentPayout] = []

    with transaction.atomic():
        tournament.payouts.all().delete()
        for rank, participant in enumerate(participants, start=1):
            if rank <= 3:
                gross = (pool * payout_splits[rank - 1]).quantize(Decimal("0.000000000000000001"))
            else:
                gross = Decimal("0")
            payout = TournamentPayout.objects.create(
                tournament=tournament,
                participant=participant,
                rank=rank,
                gross_amount=gross,
                penalty_amount=Decimal("0"),
                net_amount=gross,
                status="approved",
            )
            created.append(payout)
        tournament.status = "finalized"
        tournament.review_completed_at = timezone.now()
        tournament.save(update_fields=["status", "review_completed_at", "updated_at"])
    return created

