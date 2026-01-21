"""
Views for blockchain interactions
"""

from django.views.decorators.http import require_GET
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from .models import Game, Profile
from .blockchain_utils import (
    get_challenge_details,
    verify_deposit_transaction,
    estimate_claim_gas,
    wei_to_eth,
    eth_to_wei,
)
from .contract_loader import CONTRACT_ABI
import json


def get_contract_abi(request):
    """
    Return the contract ABI for frontend use
    """
    return JsonResponse({"success": True, "abi": CONTRACT_ABI})


@login_required
@require_http_methods(["POST"])
def verify_deposit(request, game_id):
    """
    Verify that a player's deposit transaction succeeded.
    """
    try:
        data = json.loads(request.body)
        tx_hash = data.get("tx_hash")

        game = get_object_or_404(Game, id=game_id)

        # Verify the transaction
        is_valid = verify_deposit_transaction(
            tx_hash, game_id, eth_to_wei(float(game.bet_amount))
        )

        if is_valid:
            # Store the transaction hash
            if request.user == game.white_player and not game.deposit_tx_hash:
                game.deposit_tx_hash = tx_hash
            elif request.user == game.black_player:
                # Could store separate field for black's deposit if needed
                pass

            game.save()

            return JsonResponse(
                {"success": True, "message": "Deposit verified successfully"}
            )
        else:
            return JsonResponse(
                {"success": False, "message": "Invalid transaction"}, status=400
            )

    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)


@login_required
def get_signature(request, game_id):
    """
    Return signature for claiming winnings or settling a draw.
    Always returns JSON (no redirects).
    """

    if not request.user.is_authenticated:
        return JsonResponse(
            {"success": False, "message": "Authentication required"},
            status=401,
        )

    game = get_object_or_404(Game, id=game_id)
    # Game must be finished
    if game.is_active:
        return JsonResponse(
            {"success": False, "message": "Game still in progress"},
            status=400,
        )

    # User must be a participant
    if request.user not in (game.white_player, game.black_player):
        return JsonResponse(
            {"success": False, "message": "Not authorized"},
            status=403,
        )

    # Prevent double payout
    if game.payout_claimed:
        return JsonResponse(
            {"success": False, "message": "Payout already claimed"},
            status=400,
        )

    # --- DRAW LOGIC ---
    if game.winner is None:
        # Draw → either player can refund
        if not all([game.signature_v, game.signature_r, game.signature_s]):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Draw signature not yet generated",
                },
                status=400,
            )

        return JsonResponse(
            {
                "success": True,
                "game_id": game.id,
                "is_draw": True,
                "signature": {
                    "v": game.signature_v,
                    "r": game.signature_r,
                    "s": game.signature_s,
                },
                "payout_claimed": game.payout_claimed,
            }
        )

    # --- WIN LOGIC ---
    if game.winner != request.user:
        return JsonResponse(
            {
                "success": False,
                "message": "Only the winner can claim winnings",
            },
            status=403,
        )

    if not all([game.signature_v, game.signature_r, game.signature_s]):
        return JsonResponse(
            {
                "success": False,
                "message": "Winning signature not yet generated",
            },
            status=400,
        )

    return JsonResponse(
        {
            "success": True,
            "game_id": game.id,
            "is_draw": False,
            "winner": game.winner.username,
            "winner_address": game.winner.profile.ethereum_address,
            "signature": {
                "v": game.signature_v,
                "r": game.signature_r,
                "s": game.signature_s,
            },
            "payout_claimed": game.payout_claimed,
        }
    )


@login_required
@require_http_methods(["POST"])
def mark_payout_claimed(request, game_id):
    """
    Mark that a payout has been claimed on-chain.
    """
    try:
        data = json.loads(request.body)
        tx_hash = data.get("tx_hash")

        game = get_object_or_404(Game, id=game_id)

        # Verify user is authorized
        if request.user not in [game.white_player, game.black_player]:
            return JsonResponse(
                {"success": False, "message": "Not authorized"}, status=403
            )

        # Update claim status
        game.claim_tx_hash = tx_hash
        game.payout_claimed = True
        game.save()

        return JsonResponse({"success": True, "message": "Payout claim recorded"})

    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)


@login_required
def get_challenge_info(request, game_id):
    """
    Get on-chain challenge information.
    """
    try:
        challenge = get_challenge_details(game_id)

        if challenge:
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
        else:
            return JsonResponse(
                {"success": False, "message": "Challenge not found on-chain"},
                status=404,
            )

    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def update_ethereum_address(request):
    """
    Update user's Ethereum address.
    """
    try:
        data = json.loads(request.body)
        ethereum_address = data.get("ethereum_address")

        # Basic validation
        if (
            not ethereum_address
            or len(ethereum_address) != 42
            or not ethereum_address.startswith("0x")
        ):
            return JsonResponse(
                {"success": False, "message": "Invalid Ethereum address"}, status=400
            )

        profile = request.user.profile
        profile.ethereum_address = ethereum_address
        profile.save()

        return JsonResponse({"success": True, "message": "Ethereum address updated"})

    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)


@login_required
def estimate_gas(request, game_id):
    """
    Estimate gas for claiming winnings.
    """
    try:
        game = get_object_or_404(Game, id=game_id)

        if not game.winner:
            return JsonResponse(
                {"success": False, "message": "No winner yet"}, status=400
            )

        winner_profile = Profile.objects.get(user=game.winner)

        if not winner_profile.ethereum_address:
            return JsonResponse(
                {"success": False, "message": "Winner has no Ethereum address"},
                status=400,
            )

        gas = estimate_claim_gas(game_id, winner_profile.ethereum_address)

        return JsonResponse({"success": True, "estimated_gas": gas})

    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)
