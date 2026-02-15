"""HTTP views for blockchain interactions."""

import json
import re
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from .audit import log_security_event
from .blockchain_utils import (
    estimate_claim_gas,
    eth_to_wei,
    generate_draw_signature,
    generate_winner_signature,
    get_challenge_details,
    verify_deposit_transaction,
    verify_payout_transaction,
    wei_to_eth,
)
from .contract_loader import CONTRACT_ABI
from .models import Game, Profile

TX_HASH_PATTERN = re.compile(r"^0x[a-fA-F0-9]{64}$")


def _load_json_body(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return None


def _valid_tx_hash(tx_hash: str) -> bool:
    return bool(tx_hash and TX_HASH_PATTERN.match(tx_hash))


def get_contract_abi(request):
    return JsonResponse({"success": True, "abi": CONTRACT_ABI})


@login_required
@require_http_methods(["POST"])
def verify_deposit(request, game_id):
    data = _load_json_body(request)
    if data is None:
        return JsonResponse({"success": False, "message": "Invalid JSON payload"}, status=400)

    tx_hash = data.get("tx_hash")
    if not _valid_tx_hash(tx_hash):
        return JsonResponse({"success": False, "message": "Invalid transaction hash"}, status=400)

    game = get_object_or_404(Game, id=game_id)
    if request.user not in [game.white_player, game.black_player]:
        return JsonResponse({"success": False, "message": "Not authorized"}, status=403)

    if game.bet_amount <= 0:
        return JsonResponse({"success": False, "message": "No deposit required for this game"}, status=400)

    try:
        expected_amount_wei = eth_to_wei(Decimal(str(game.bet_amount)))
    except (ValueError, InvalidOperation):
        return JsonResponse({"success": False, "message": "Invalid game bet amount"}, status=400)

    if not verify_deposit_transaction(tx_hash, game_id, expected_amount_wei):
        log_security_event(
            "deposit_verify_failed",
            status="error",
            user=request.user,
            game=game,
            details={"tx_hash": tx_hash, "reason": "verification_failed"},
        )
        return JsonResponse({"success": False, "message": "Invalid transaction"}, status=400)

    if request.user == game.white_player and not game.deposit_tx_hash:
        game.deposit_tx_hash = tx_hash
        game.save(update_fields=["deposit_tx_hash"])

    log_security_event(
        "deposit_verified",
        user=request.user,
        game=game,
        details={"tx_hash": tx_hash},
    )
    return JsonResponse({"success": True, "message": "Deposit verified successfully"})


@login_required
def get_signature(request, game_id):
    game = get_object_or_404(Game, id=game_id)

    if game.is_active:
        return JsonResponse({"success": False, "message": "Game still in progress"}, status=400)

    if request.user not in (game.white_player, game.black_player):
        return JsonResponse({"success": False, "message": "Not authorized"}, status=403)

    if game.payout_claimed:
        return JsonResponse({"success": False, "message": "Payout already claimed"}, status=400)

    if game.bet_amount <= 0:
        return JsonResponse({"success": False, "message": "No payout for zero-bet game"}, status=400)

    if not all([game.signature_v, game.signature_r, game.signature_s]):
        try:
            if game.winner is None:
                v, r, s = generate_draw_signature(game.id)
            else:
                winner_address = game.winner.profile.ethereum_address
                if not winner_address:
                    return JsonResponse(
                        {"success": False, "message": "Winner has no Ethereum address set"},
                        status=400,
                    )
                v, r, s = generate_winner_signature(game.id, winner_address)

            game.signature_v = v
            game.signature_r = r
            game.signature_s = s
            game.save(update_fields=["signature_v", "signature_r", "signature_s"])
        except Exception as exc:
            msg = f"Could not generate signature: {exc}"
            log_security_event(
                "signature_generation_failed",
                status="error",
                user=request.user,
                game=game,
                details={"error": str(exc)},
            )
            return JsonResponse({"success": False, "message": msg}, status=500)
        log_security_event(
            "signature_generated",
            user=request.user,
            game=game,
            details={"is_draw": game.winner is None},
        )

    game.refresh_from_db(fields=["signature_v", "signature_r", "signature_s"])
    if not all([game.signature_v, game.signature_r, game.signature_s]):
        msg = "Draw signature not yet generated" if game.winner is None else "Winning signature not yet generated"
        return JsonResponse({"success": False, "message": msg}, status=400)

    if game.winner is None:
        return JsonResponse(
            {
                "success": True,
                "game_id": game.id,
                "is_draw": True,
                "signature": {"v": game.signature_v, "r": game.signature_r, "s": game.signature_s},
                "payout_claimed": game.payout_claimed,
            }
        )

    if game.winner != request.user:
        return JsonResponse({"success": False, "message": "Only the winner can claim winnings"}, status=403)

    return JsonResponse(
        {
            "success": True,
            "game_id": game.id,
            "is_draw": False,
            "winner": game.winner.username,
            "winner_address": game.winner.profile.ethereum_address,
            "signature": {"v": game.signature_v, "r": game.signature_r, "s": game.signature_s},
            "payout_claimed": game.payout_claimed,
        }
    )


@login_required
@require_http_methods(["POST"])
def mark_payout_claimed(request, game_id):
    data = _load_json_body(request)
    if data is None:
        return JsonResponse({"success": False, "message": "Invalid JSON payload"}, status=400)

    tx_hash = data.get("tx_hash")
    if not _valid_tx_hash(tx_hash):
        return JsonResponse({"success": False, "message": "Invalid transaction hash"}, status=400)

    game = get_object_or_404(Game, id=game_id)
    if request.user not in [game.white_player, game.black_player]:
        return JsonResponse({"success": False, "message": "Not authorized"}, status=403)
    if game.is_active:
        return JsonResponse({"success": False, "message": "Game still in progress"}, status=400)
    if game.payout_claimed:
        return JsonResponse({"success": False, "message": "Payout already recorded"}, status=400)

    if not verify_payout_transaction(tx_hash, game_id, game):
        log_security_event(
            "payout_mark_failed",
            status="error",
            user=request.user,
            game=game,
            details={"tx_hash": tx_hash, "reason": "verification_failed"},
        )
        return JsonResponse({"success": False, "message": "Payout transaction verification failed"}, status=400)

    game.claim_tx_hash = tx_hash
    game.payout_claimed = True
    game.save(update_fields=["claim_tx_hash", "payout_claimed"])
    log_security_event(
        "payout_marked_claimed",
        user=request.user,
        game=game,
        details={"tx_hash": tx_hash},
    )
    return JsonResponse({"success": True, "message": "Payout claim recorded"})


@login_required
def get_challenge_info(request, game_id):
    try:
        challenge = get_challenge_details(game_id)
        if not challenge:
            return JsonResponse({"success": False, "message": "Challenge not found on-chain"}, status=404)

        return JsonResponse(
            {
                "success": True,
                "challenge": {
                    "player_white": challenge["player_white"],
                    "player_black": challenge["player_black"],
                    "bet_amount_eth": wei_to_eth(challenge["bet_amount"]),
                    "is_active": challenge["is_active"],
                    "is_completed": challenge["is_completed"],
                },
            }
        )
    except Exception as exc:
        return JsonResponse({"success": False, "message": str(exc)}, status=500)


@login_required
@require_http_methods(["POST"])
def update_ethereum_address(request):
    data = _load_json_body(request)
    if data is None:
        return JsonResponse({"success": False, "message": "Invalid JSON payload"}, status=400)

    ethereum_address = (data.get("ethereum_address") or "").strip()
    if len(ethereum_address) != 42 or not ethereum_address.startswith("0x"):
        return JsonResponse({"success": False, "message": "Invalid Ethereum address"}, status=400)

    profile = request.user.profile
    profile.ethereum_address = ethereum_address
    profile.save(update_fields=["ethereum_address"])
    return JsonResponse({"success": True, "message": "Ethereum address updated"})


@login_required
def estimate_gas(request, game_id):
    game = get_object_or_404(Game, id=game_id)
    if not game.winner:
        return JsonResponse({"success": False, "message": "No winner yet"}, status=400)

    winner_profile = Profile.objects.get(user=game.winner)
    if not winner_profile.ethereum_address:
        return JsonResponse({"success": False, "message": "Winner has no Ethereum address"}, status=400)

    try:
        gas = estimate_claim_gas(game_id, winner_profile.ethereum_address)
        return JsonResponse({"success": True, "estimated_gas": gas})
    except Exception as exc:
        return JsonResponse({"success": False, "message": str(exc)}, status=500)
