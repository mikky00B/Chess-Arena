"""Blockchain utilities for signatures, contract state, and transaction verification."""

from decimal import Decimal, InvalidOperation
from functools import lru_cache
import logging
from typing import Optional

import eth_abi
from django.conf import settings
from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3

from .contract_loader import CONTRACT_ABI

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_web3():
    if not settings.BLOCKCHAIN_RPC_URL:
        raise ValueError("BLOCKCHAIN_RPC_URL not configured")

    w3 = Web3(Web3.HTTPProvider(settings.BLOCKCHAIN_RPC_URL))
    if not w3.is_connected():
        raise ConnectionError(
            f"Cannot connect to blockchain at {settings.BLOCKCHAIN_RPC_URL}"
        )
    if w3.eth.chain_id != settings.CHAIN_ID:
        raise ValueError(
            f"Chain ID mismatch: connected to {w3.eth.chain_id}, expected {settings.CHAIN_ID}"
        )
    return w3


@lru_cache(maxsize=1)
def get_chess_contract():
    if not settings.CHESS_CONTRACT_ADDRESS:
        raise ValueError("CHESS_CONTRACT_ADDRESS not set")
    if not CONTRACT_ABI:
        raise ValueError("Contract ABI not loaded")

    w3 = get_web3()
    address = w3.to_checksum_address(settings.CHESS_CONTRACT_ADDRESS)
    code = w3.eth.get_code(address)
    if code == b"" or code == b"0x":
        raise ValueError(f"No contract found at {address}")
    return w3.eth.contract(address=address, abi=CONTRACT_ABI)


@lru_cache(maxsize=1)
def get_judge_account():
    key = settings.JUDGE_PRIVATE_KEY
    if not key:
        raise ValueError("JUDGE_PRIVATE_KEY not set")
    if len(key) != 66 or not key.startswith("0x"):
        raise ValueError("JUDGE_PRIVATE_KEY must be 66 chars (0x + 64 hex)")
    return Account.from_key(key)


def generate_winner_signature(game_id: int, winner_address: str) -> tuple:
    w3 = get_web3()
    judge = get_judge_account()
    contract = get_chess_contract()

    winner_address = w3.to_checksum_address(winner_address)
    contract_address = w3.to_checksum_address(contract.address)
    encoded_data = eth_abi.encode(
        ["uint256", "address", "address"], [game_id, winner_address, contract_address]
    )
    data_hash = w3.keccak(encoded_data)
    message = encode_defunct(primitive=data_hash)
    signed = w3.eth.account.sign_message(message, private_key=settings.JUDGE_PRIVATE_KEY)

    recovered = w3.eth.account.recover_message(message, vrs=(signed.v, signed.r, signed.s))
    if recovered.lower() != judge.address.lower():
        raise ValueError("Generated signature does not recover to judge")

    return signed.v, w3.to_hex(signed.r), w3.to_hex(signed.s)


def generate_draw_signature(game_id: int) -> tuple:
    w3 = get_web3()
    judge = get_judge_account()
    contract = get_chess_contract()

    game_id_bytes = game_id.to_bytes(32, byteorder="big")
    draw_bytes = b"DRAW"
    contract_bytes = bytes.fromhex(contract.address[2:].zfill(64))
    data_hash = w3.keccak(game_id_bytes + draw_bytes + contract_bytes)
    message = encode_defunct(primitive=data_hash)
    signed = w3.eth.account.sign_message(message, private_key=settings.JUDGE_PRIVATE_KEY)

    recovered = w3.eth.account.recover_message(message, vrs=(signed.v, signed.r, signed.s))
    if recovered.lower() != judge.address.lower():
        raise ValueError("Generated draw signature does not recover to judge")

    return signed.v, w3.to_hex(signed.r), w3.to_hex(signed.s)


def get_challenge_details(game_id: int) -> Optional[dict]:
    try:
        challenge = get_chess_contract().functions.get_challenge(game_id).call()
        return {
            "player_white": challenge[0],
            "player_black": challenge[1],
            "bet_amount": challenge[2],
            "is_active": challenge[3],
            "is_completed": challenge[4],
        }
    except Exception as exc:
        logger.error("Error fetching challenge %s: %s", game_id, exc)
        return None


def verify_deposit_transaction(tx_hash: str, game_id: int, expected_amount: int) -> bool:
    w3 = get_web3()
    contract = get_chess_contract()
    try:
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        if receipt["status"] != 1:
            return False

        tx = w3.eth.get_transaction(tx_hash)
        if tx.get("to", "").lower() != contract.address.lower():
            return False
        if tx["value"] != expected_amount:
            return False

        fn, params = contract.decode_function_input(tx["input"])
        return fn.fn_name == "deposit" and int(params.get("game_id", -1)) == int(game_id)
    except Exception as exc:
        logger.error("Error verifying transaction %s: %s", tx_hash, exc)
        return False


def verify_payout_transaction(tx_hash: str, game_id: int, game) -> bool:
    w3 = get_web3()
    contract = get_chess_contract()
    try:
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        if receipt["status"] != 1:
            return False

        tx = w3.eth.get_transaction(tx_hash)
        if tx.get("to", "").lower() != contract.address.lower():
            return False

        fn, params = contract.decode_function_input(tx["input"])
        fn_name = fn.fn_name
        if fn_name not in {"claim_winnings", "settle_draw"}:
            return False
        if int(params.get("game_id", -1)) != int(game_id):
            return False

        tx_from = tx["from"].lower()
        white_addr = (getattr(game.white_player.profile, "ethereum_address", "") or "").lower()
        black_addr = (getattr(game.black_player.profile, "ethereum_address", "") or "").lower()

        if fn_name == "claim_winnings":
            if not game.winner or not game.winner.profile.ethereum_address:
                return False
            winner_addr = game.winner.profile.ethereum_address.lower()
            claim_winner = params.get("winner", "").lower()
            return winner_addr == claim_winner and tx_from == winner_addr

        return tx_from in {white_addr, black_addr}
    except Exception as exc:
        logger.error("Error verifying payout tx %s: %s", tx_hash, exc)
        return False


def estimate_claim_gas(game_id: int, winner_address: str) -> int:
    w3 = get_web3()
    contract = get_chess_contract()
    winner_address = w3.to_checksum_address(winner_address)
    try:
        v, r, s = generate_winner_signature(game_id, winner_address)
        gas = contract.functions.claim_winnings(
            game_id, winner_address, v, r, s
        ).estimate_gas({"from": winner_address})
        return int(gas * 1.2)
    except Exception as exc:
        logger.error("Error estimating gas for game %s: %s", game_id, exc)
        return 300000


def eth_to_wei(eth_amount) -> int:
    w3 = get_web3()
    try:
        amount = Decimal(str(eth_amount))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid ETH amount: {eth_amount}") from exc
    return w3.to_wei(amount, "ether")


def wei_to_eth(wei_amount: int) -> float:
    return get_web3().from_wei(wei_amount, "ether")


def get_network_info() -> dict:
    try:
        w3 = get_web3()
        contract = get_chess_contract()
        judge = get_judge_account()
        return {
            "success": True,
            "network": settings.BLOCKCHAIN_NETWORK,
            "network_name": settings.CURRENT_NETWORK_CONFIG["name"],
            "rpc_url": settings.BLOCKCHAIN_RPC_URL,
            "chain_id": w3.eth.chain_id,
            "contract_address": contract.address,
            "judge_address": judge.address,
            "is_connected": w3.is_connected(),
            "latest_block": w3.eth.block_number,
            "explorer_url": settings.CURRENT_NETWORK_CONFIG.get("explorer_url"),
        }
    except Exception as exc:
        logger.error("Error getting network info: %s", exc)
        return {
            "success": False,
            "error": str(exc),
            "network": settings.BLOCKCHAIN_NETWORK,
        }
