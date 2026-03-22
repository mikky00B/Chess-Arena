from decimal import Decimal, InvalidOperation
import secrets
import re

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import (
    Tournament,
    TournamentInvite,
    TournamentMatch,
    TournamentParticipant,
)
from .tournament_service import apply_match_result, generate_tournament_matches
from .tournament_service import calculate_payouts, review_tournament_matches

TX_HASH_PATTERN = re.compile(r"^0x[a-fA-F0-9]{64}$")


def _redirect_json(request, success, message, redirect_name, redirect_kwargs=None, status=200, extra=None):
    redirect_kwargs = redirect_kwargs or {}
    extra = extra or {}
    if "application/json" in (request.headers.get("Accept") or ""):
        payload = {"success": success, "message": message, **extra}
        return JsonResponse(payload, status=status)
    if success:
        messages.success(request, message)
    else:
        messages.error(request, message)
    return redirect(redirect_name, **redirect_kwargs)


@login_required
@require_http_methods(["POST"])
def create_tournament(request):
    name = (request.POST.get("name") or "").strip()
    if not name:
        return _redirect_json(
            request,
            False,
            "Tournament name is required.",
            "tournament_create_page",
            status=400,
        )

    format_name = (request.POST.get("format") or "round_robin").strip()
    if format_name not in {"round_robin", "swiss", "single_elim", "double_elim"}:
        return _redirect_json(
            request, False, "Invalid tournament format.", "tournament_create_page", status=400
        )

    try:
        max_players = int(request.POST.get("max_players", "8"))
        min_players = int(request.POST.get("min_players", "2"))
        games_per_pairing = int(request.POST.get("games_per_pairing", "1"))
        swiss_rounds = int(request.POST.get("swiss_rounds", "0"))
        entry_fee = Decimal(request.POST.get("entry_fee_eth", "0"))
    except (ValueError, InvalidOperation):
        return _redirect_json(
            request, False, "Invalid numeric field.", "tournament_create_page", status=400
        )

    if min_players < 2 or max_players < min_players:
        return _redirect_json(
            request, False, "Invalid player limits.", "tournament_create_page", status=400
        )

    if entry_fee < 0:
        return _redirect_json(
            request, False, "Entry fee cannot be negative.", "tournament_create_page", status=400
        )

    tournament = Tournament.objects.create(
        creator=request.user,
        name=name,
        description=(request.POST.get("description") or "").strip(),
        format=format_name,
        status="inviting",
        max_players=max_players,
        min_players=min_players,
        games_per_pairing=max(1, games_per_pairing),
        swiss_rounds=max(0, swiss_rounds),
        entry_fee_eth=entry_fee,
        invite_only=request.POST.get("invite_only", "on") == "on",
    )
    TournamentParticipant.objects.create(
        tournament=tournament,
        user=request.user,
        status="accepted",
        deposit_verified=(entry_fee == 0),
        seed=1,
    )
    return _redirect_json(
        request,
        True,
        "Tournament created successfully.",
        "tournament_detail_page",
        {"tournament_id": tournament.id},
        extra={"tournament_id": tournament.id},
    )


@login_required
@require_http_methods(["POST"])
def invite_to_tournament(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    if request.user != tournament.creator:
        return _redirect_json(
            request,
            False,
            "Only the tournament owner can invite players.",
            "tournament_detail_page",
            {"tournament_id": tournament.id},
            status=403,
        )
    if tournament.status not in {"draft", "inviting"}:
        return _redirect_json(
            request,
            False,
            "Tournament is not accepting invites right now.",
            "tournament_detail_page",
            {"tournament_id": tournament.id},
            status=400,
        )

    username = (request.POST.get("username") or "").strip()
    if not username:
        return _redirect_json(
            request,
            False,
            "Username is required for invites.",
            "tournament_detail_page",
            {"tournament_id": tournament.id},
            status=400,
        )
    invitee = get_object_or_404(User, username=username)
    if invitee == tournament.creator:
        return _redirect_json(
            request,
            False,
            "Owner is already participating.",
            "tournament_detail_page",
            {"tournament_id": tournament.id},
            status=400,
        )

    if tournament.participants.filter(user=invitee).exists():
        return _redirect_json(
            request,
            False,
            "That user is already part of this tournament.",
            "tournament_detail_page",
            {"tournament_id": tournament.id},
            status=400,
        )

    if tournament.participants.count() >= tournament.max_players:
        return _redirect_json(
            request,
            False,
            "Tournament is full.",
            "tournament_detail_page",
            {"tournament_id": tournament.id},
            status=400,
        )

    invite, _ = TournamentInvite.objects.update_or_create(
        tournament=tournament,
        invitee=invitee,
        defaults={
            "inviter": request.user,
            "token": secrets.token_urlsafe(24),
            "status": "pending",
        },
    )
    TournamentParticipant.objects.update_or_create(
        tournament=tournament,
        user=invitee,
        defaults={"status": "invited", "deposit_verified": False},
    )
    join_link = request.build_absolute_uri(f"/chess/tournaments/invite/{invite.token}/")
    return _redirect_json(
        request,
        True,
        f"Invite sent to {invitee.username}. Invite link: {join_link}",
        "tournament_detail_page",
        {"tournament_id": tournament.id},
        extra={"invite_link": join_link},
    )


@login_required
@require_http_methods(["POST"])
def join_public_tournament(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    if tournament.invite_only:
        return _redirect_json(
            request,
            False,
            "Tournament is invite-only.",
            "tournament_detail_page",
            {"tournament_id": tournament.id},
            status=400,
        )
    if tournament.status not in {"draft", "inviting"}:
        return _redirect_json(
            request,
            False,
            "Tournament is not accepting participants.",
            "tournament_detail_page",
            {"tournament_id": tournament.id},
            status=400,
        )
    if tournament.participants.count() >= tournament.max_players:
        return _redirect_json(
            request,
            False,
            "Tournament is full.",
            "tournament_detail_page",
            {"tournament_id": tournament.id},
            status=400,
        )

    participant, created = TournamentParticipant.objects.get_or_create(
        tournament=tournament,
        user=request.user,
        defaults={
            "status": "accepted",
            "deposit_verified": tournament.entry_fee_eth == 0,
        },
    )
    if not created:
        return _redirect_json(
            request,
            False,
            "You are already participating.",
            "tournament_detail_page",
            {"tournament_id": tournament.id},
            status=400,
        )
    return _redirect_json(
        request,
        True,
        "You joined the tournament.",
        "tournament_detail_page",
        {"tournament_id": tournament.id},
        extra={"participant_status": participant.status},
    )


@login_required
@require_http_methods(["POST"])
def respond_tournament_invite(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    participant = get_object_or_404(TournamentParticipant, tournament=tournament, user=request.user)
    action = (request.POST.get("action") or "").strip()
    if action not in {"accept", "decline", "check_in"}:
        return _redirect_json(
            request,
            False,
            "Invalid invite action.",
            "tournament_detail_page",
            {"tournament_id": tournament.id},
            status=400,
        )

    if action == "decline":
        participant.status = "declined"
        participant.save(update_fields=["status", "updated_at"])
        TournamentInvite.objects.filter(tournament=tournament, invitee=request.user).update(status="declined")
        return _redirect_json(
            request,
            True,
            "Invite declined.",
            "tournament_detail_page",
            {"tournament_id": tournament.id},
            extra={"status": participant.status},
        )

    if action == "accept":
        participant.status = "accepted"
        if tournament.entry_fee_eth == 0:
            participant.deposit_verified = True
        participant.save(update_fields=["status", "deposit_verified", "updated_at"])
        TournamentInvite.objects.filter(tournament=tournament, invitee=request.user).update(status="accepted")
        return _redirect_json(
            request,
            True,
            "Invite accepted.",
            "tournament_detail_page",
            {"tournament_id": tournament.id},
            extra={"status": participant.status},
        )

    if not participant.deposit_verified and tournament.entry_fee_eth > 0:
        return _redirect_json(
            request,
            False,
            "Deposit must be verified before check-in.",
            "tournament_detail_page",
            {"tournament_id": tournament.id},
            status=400,
        )
    participant.status = "checked_in"
    participant.save(update_fields=["status", "updated_at"])
    return _redirect_json(
        request,
        True,
        "Check-in complete.",
        "tournament_detail_page",
        {"tournament_id": tournament.id},
        extra={"status": participant.status},
    )


@login_required
@require_http_methods(["POST"])
def verify_tournament_deposit(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    participant = get_object_or_404(TournamentParticipant, tournament=tournament, user=request.user)
    tx_hash = (request.POST.get("tx_hash") or "").strip()
    if not TX_HASH_PATTERN.match(tx_hash):
        return _redirect_json(
            request,
            False,
            "Invalid transaction hash.",
            "tournament_detail_page",
            {"tournament_id": tournament.id},
            status=400,
        )
    if tournament.entry_fee_eth <= 0:
        return _redirect_json(
            request,
            False,
            "No deposit required for this tournament.",
            "tournament_detail_page",
            {"tournament_id": tournament.id},
            status=400,
        )
    if participant.status not in {"accepted", "checked_in"}:
        return _redirect_json(
            request,
            False,
            "Accept invitation before verifying deposit.",
            "tournament_detail_page",
            {"tournament_id": tournament.id},
            status=400,
        )

    participant.deposit_verified = True
    participant.deposit_tx_hash = tx_hash
    participant.save(update_fields=["deposit_verified", "deposit_tx_hash", "updated_at"])
    return _redirect_json(
        request,
        True,
        "Tournament deposit verified.",
        "tournament_detail_page",
        {"tournament_id": tournament.id},
        extra={"deposit_verified": True},
    )


@login_required
@require_http_methods(["POST"])
def lock_tournament(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    if request.user != tournament.creator:
        return _redirect_json(
            request,
            False,
            "Only owner can lock this tournament.",
            "tournament_detail_page",
            {"tournament_id": tournament.id},
            status=403,
        )
    if tournament.status not in {"draft", "inviting"}:
        return _redirect_json(
            request,
            False,
            "Tournament cannot be locked now.",
            "tournament_detail_page",
            {"tournament_id": tournament.id},
            status=400,
        )

    ready = tournament.participants.filter(
        status__in=["accepted", "checked_in"], deposit_verified=True
    )
    if ready.count() < tournament.min_players:
        return _redirect_json(
            request,
            False,
            "Not enough ready participants.",
            "tournament_detail_page",
            {"tournament_id": tournament.id},
            status=400,
        )

    tournament.status = "locked"
    tournament.escrow_locked = True
    tournament.save(update_fields=["status", "escrow_locked", "updated_at"])
    return _redirect_json(
        request,
        True,
        "Tournament locked.",
        "tournament_detail_page",
        {"tournament_id": tournament.id},
        extra={"status": tournament.status},
    )


@login_required
@require_http_methods(["POST"])
def start_tournament(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    if request.user != tournament.creator:
        return _redirect_json(
            request,
            False,
            "Only owner can start this tournament.",
            "tournament_detail_page",
            {"tournament_id": tournament.id},
            status=403,
        )
    if tournament.status != "locked":
        return _redirect_json(
            request,
            False,
            "Tournament must be locked first.",
            "tournament_detail_page",
            {"tournament_id": tournament.id},
            status=400,
        )

    try:
        created = generate_tournament_matches(tournament)
    except ValueError as exc:
        return _redirect_json(
            request,
            False,
            str(exc),
            "tournament_detail_page",
            {"tournament_id": tournament.id},
            status=400,
        )

    tournament.status = "in_progress"
    tournament.started_at = timezone.now()
    tournament.save(update_fields=["status", "started_at", "updated_at"])
    return _redirect_json(
        request,
        True,
        f"Tournament started with {len(created)} match slots.",
        "tournament_detail_page",
        {"tournament_id": tournament.id},
        extra={"matches_created": len(created)},
    )


@login_required
@require_http_methods(["POST"])
def report_tournament_match(request, tournament_id, match_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    match = get_object_or_404(TournamentMatch, id=match_id, tournament=tournament)
    is_player = request.user in [
        getattr(match.white_participant, "user", None),
        getattr(match.black_participant, "user", None),
    ]
    if not (request.user == tournament.creator or request.user.is_staff or is_player):
        return _redirect_json(
            request,
            False,
            "Not authorized.",
            "tournament_detail_page",
            {"tournament_id": tournament.id},
            status=403,
        )

    result = (request.POST.get("result") or "").strip()
    try:
        apply_match_result(match, result)
    except ValueError as exc:
        return _redirect_json(
            request,
            False,
            str(exc),
            "tournament_detail_page",
            {"tournament_id": tournament.id},
            status=400,
        )

    match.result = result
    match.status = "completed"
    match.completed_at = timezone.now()
    match.save(update_fields=["result", "status", "completed_at", "updated_at"])

    if not tournament.matches.exclude(status="completed").exists():
        tournament.status = "reviewing" if tournament.review_required else "finalized"
        tournament.completed_at = timezone.now()
        if not tournament.review_required:
            tournament.review_completed_at = timezone.now()
        tournament.save(
            update_fields=["status", "completed_at", "review_completed_at", "updated_at"]
        )

    return _redirect_json(
        request,
        True,
        f"Match result recorded: {match.result}.",
        "tournament_detail_page",
        {"tournament_id": tournament.id},
        extra={"match_id": match.id, "result": match.result},
    )


@login_required
@require_http_methods(["POST"])
def review_tournament(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    if not (request.user == tournament.creator or request.user.is_staff):
        return _redirect_json(
            request,
            False,
            "Not authorized.",
            "tournament_detail_page",
            {"tournament_id": tournament.id},
            status=403,
        )
    if tournament.status not in {"reviewing", "in_progress"}:
        return _redirect_json(
            request,
            False,
            "Tournament is not ready for review.",
            "tournament_detail_page",
            {"tournament_id": tournament.id},
            status=400,
        )

    report = review_tournament_matches(tournament)
    return _redirect_json(
        request,
        True,
        f"Review complete. Reviewed: {report['reviewed']}, flagged: {report['flagged']}.",
        "tournament_detail_page",
        {"tournament_id": tournament.id},
        extra={"report": report, "status": tournament.status},
    )


@login_required
@require_http_methods(["POST"])
def finalize_tournament(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    if not (request.user == tournament.creator or request.user.is_staff):
        return _redirect_json(
            request,
            False,
            "Not authorized.",
            "tournament_detail_page",
            {"tournament_id": tournament.id},
            status=403,
        )
    if tournament.status not in {"reviewing", "finalized"}:
        return _redirect_json(
            request,
            False,
            "Tournament is not in review state.",
            "tournament_detail_page",
            {"tournament_id": tournament.id},
            status=400,
        )

    try:
        payouts = calculate_payouts(tournament)
    except ValueError as exc:
        return _redirect_json(
            request,
            False,
            str(exc),
            "tournament_detail_page",
            {"tournament_id": tournament.id},
            status=400,
        )

    return _redirect_json(
        request,
        True,
        f"Tournament finalized. Generated {len(payouts)} payout rows.",
        "tournament_detail_page",
        {"tournament_id": tournament.id},
        extra={"status": tournament.status, "payouts_created": len(payouts)},
    )


@login_required
def accept_tournament_invite(request, invite_token):
    invite = get_object_or_404(
        TournamentInvite.objects.select_related("tournament", "invitee"),
        token=invite_token,
    )
    if request.user != invite.invitee:
        messages.error(request, "This invite is for a different account.")
        return redirect("lobby")
    if invite.status != "pending":
        messages.info(request, "Invite already handled.")
        return redirect("tournament_detail_page", tournament_id=invite.tournament_id)

    participant, _ = TournamentParticipant.objects.get_or_create(
        tournament=invite.tournament,
        user=request.user,
        defaults={"status": "invited", "deposit_verified": False},
    )
    participant.status = "accepted"
    if invite.tournament.entry_fee_eth == 0:
        participant.deposit_verified = True
    participant.save(update_fields=["status", "deposit_verified", "updated_at"])
    invite.status = "accepted"
    invite.save(update_fields=["status", "updated_at"])
    messages.success(request, "Invite accepted. Welcome to the tournament.")
    return redirect("tournament_detail_page", tournament_id=invite.tournament_id)


@login_required
@require_http_methods(["POST"])
def cancel_tournament(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    if request.user != tournament.creator:
        return _redirect_json(
            request,
            False,
            "Only owner can cancel this tournament.",
            "tournament_detail_page",
            {"tournament_id": tournament.id},
            status=403,
        )
    if tournament.status not in {"draft", "inviting", "locked"}:
        return _redirect_json(
            request,
            False,
            "Tournament can only be cancelled before it starts.",
            "tournament_detail_page",
            {"tournament_id": tournament.id},
            status=400,
        )
    if tournament.participants.filter(deposit_verified=True).exists():
        return _redirect_json(
            request,
            False,
            "Cannot cancel after deposits are verified.",
            "tournament_detail_page",
            {"tournament_id": tournament.id},
            status=400,
        )

    tournament.status = "cancelled"
    tournament.cancellation_reason = (
        request.POST.get("reason", "").strip() or "Cancelled by owner before deposits."
    )
    tournament.save(update_fields=["status", "cancellation_reason", "updated_at"])
    return _redirect_json(
        request,
        True,
        "Tournament cancelled successfully.",
        "tournament_detail_page",
        {"tournament_id": tournament.id},
        extra={"status": tournament.status},
    )

