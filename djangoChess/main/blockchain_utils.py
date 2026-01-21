"""
Blockchain integration utilities for Chess dApp
"""

from web3 import Web3
from eth_account import Account
from eth_account.messages import encode_defunct
from django.conf import settings
import json
import eth_abi

# Initialize Web3
w3 = Web3(Web3.HTTPProvider(settings.BLOCKCHAIN_RPC_URL))

# Load contract ABI from Moccasin compilation
from .contract_loader import CONTRACT_ABI

# Contract instance
chess_contract = w3.eth.contract(
    address=settings.CHESS_CONTRACT_ADDRESS, abi=CONTRACT_ABI
)

# Judge account (loaded from settings)
judge_account = Account.from_key(settings.JUDGE_PRIVATE_KEY)


def generate_winner_signature(game_id: int, winner_address: str) -> tuple:
    winner_address = w3.to_checksum_address(winner_address)
    contract_address = w3.to_checksum_address(settings.CHESS_CONTRACT_ADDRESS)

    print(f"Generating signature for Game {game_id}")

    # This matches Vyper's: convert(game_id, bytes32), convert(winner, bytes32), convert(self, bytes32)
    encoded_data = eth_abi.encode(
        ["uint256", "address", "address"], [game_id, winner_address, contract_address]
    )

    data_hash = w3.keccak(encoded_data)
    print(f"  Data hash: {data_hash.hex()}")

    message = encode_defunct(primitive=data_hash)

    signed_message = w3.eth.account.sign_message(
        message, private_key=settings.JUDGE_PRIVATE_KEY
    )

    v = signed_message.v
    r_hex = w3.to_hex(signed_message.r)
    s_hex = w3.to_hex(signed_message.s)

    print(f"  Signature v: {v}")
    print(
        f"  Recovered: {w3.eth.account.recover_message(message, vrs=(v, signed_message.r, signed_message.s))}"
    )

    return (v, r_hex, s_hex)


def generate_draw_signature(game_id: int) -> tuple:
    """
    Generate signature for draw settlement.
    Matches Vyper's: convert(game_id, bytes32), convert("DRAW", Bytes[4]), convert(self, bytes32)
    """
    contract_address = w3.to_checksum_address(settings.CHESS_CONTRACT_ADDRESS)

    # Convert "DRAW" to bytes (Vyper uses Bytes[4])
    draw_bytes = b"DRAW"  # This is exactly 4 bytes

    # Match Vyper's concat(convert(game_id, bytes32), convert("DRAW", Bytes[4]), convert(self, bytes32))
    # We need to manually build this since eth_abi doesn't have a "Bytes[4]" type

    # Convert game_id to bytes32 (left-padded)
    game_id_bytes = game_id.to_bytes(32, byteorder="big")

    # "DRAW" is just the raw bytes
    # draw_bytes is already b"DRAW"

    # Convert contract address to bytes32 (left-padded with 12 zero bytes)
    contract_bytes = bytes.fromhex(contract_address[2:].zfill(64))

    # Concatenate: game_id (32 bytes) + "DRAW" (4 bytes) + contract (32 bytes)
    concatenated = game_id_bytes + draw_bytes + contract_bytes

    # Hash the concatenated data
    data_hash = w3.keccak(concatenated)

    # Wrap with Ethereum Signed Message
    message = encode_defunct(primitive=data_hash)

    signed_message = w3.eth.account.sign_message(
        message, private_key=settings.JUDGE_PRIVATE_KEY
    )

    return (signed_message.v, w3.to_hex(signed_message.r), w3.to_hex(signed_message.s))


def get_challenge_details(game_id: int) -> dict:
    """
    Fetch challenge details from smart contract.

    Args:
        game_id: The game ID

    Returns:
        dict: Challenge details
    """
    try:
        challenge = chess_contract.functions.get_challenge(game_id).call()
        return {
            "player_white": challenge[0],
            "player_black": challenge[1],
            "bet_amount": challenge[2],
            "is_active": challenge[3],
            "is_completed": challenge[4],
        }
    except Exception as e:
        print(f"Error fetching challenge: {e}")
        return None


def verify_deposit_transaction(
    tx_hash: str, game_id: int, expected_amount: int
) -> bool:
    """
    Verify a deposit transaction was successful.

    Args:
        tx_hash: Transaction hash
        game_id: Game ID
        expected_amount: Expected deposit amount in wei

    Returns:
        bool: True if transaction is valid
    """
    try:
        receipt = w3.eth.get_transaction_receipt(tx_hash)

        # Check transaction succeeded
        if receipt["status"] != 1:
            return False

        # Check it was sent to our contract
        if receipt["to"].lower() != settings.CHESS_CONTRACT_ADDRESS.lower():
            return False

        # Verify amount and function called
        tx = w3.eth.get_transaction(tx_hash)
        if tx["value"] != expected_amount:
            return False

        # Decode function call to verify it's deposit(game_id)
        # This requires the ABI - simplified check here
        return True

    except Exception as e:
        print(f"Error verifying transaction: {e}")
        return False


def estimate_claim_gas(game_id: int, winner_address: str) -> int:
    """
    Estimate gas for claim_winnings transaction.

    Args:
        game_id: Game ID
        winner_address: Winner's address

    Returns:
        int: Estimated gas
    """
    winner_address = w3.to_checksum_address(winner_address)
    v, r, s = generate_winner_signature(game_id, winner_address)

    try:
        gas_estimate = chess_contract.functions.claim_winnings(
            game_id, winner_address, v, r, s
        ).estimate_gas({"from": winner_address})

        # Add 20% buffer
        return int(gas_estimate * 1.2)
    except Exception as e:
        print(f"Error estimating gas: {e}")
        return 200000  # Default fallback


# Helper to convert ETH to Wei
def eth_to_wei(eth_amount: float) -> int:
    """Convert ETH to Wei"""
    return w3.to_wei(eth_amount, "ether")


# Helper to convert Wei to ETH
def wei_to_eth(wei_amount: int) -> float:
    """Convert Wei to ETH"""
    return w3.from_wei(wei_amount, "ether")
