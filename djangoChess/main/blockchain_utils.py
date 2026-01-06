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
    # 1. Standardize addresses
    winner_address = w3.to_checksum_address(winner_address)
    contract_address = w3.to_checksum_address(settings.CHESS_CONTRACT_ADDRESS)

    print(f"Generating signature for Game {game_id}")

    # 2. ABI Encode the data (Matches Vyper's convert(x, bytes32) + concat)
    # This pads game_id, winner, and contract to 32 bytes each.
    encoded_data = eth_abi.encode(
        ["uint256", "address", "address"], [game_id, winner_address, contract_address]
    )

    # 3. Create the data hash
    data_hash = w3.keccak(encoded_data)
    print(f"  Data hash: {data_hash.hex()}")

    # 4. Wrap with EIP-191 prefix
    # encode_defunct is the standard way to do this in Web3.py
    message = encode_defunct(primitive=data_hash)

    # 5. Sign (using your existing judge_account logic)
    signed_message = w3.eth.account.sign_message(
        message, private_key=settings.JUDGE_PRIVATE_KEY
    )

    # 6. Extract components
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
    Generate signature for draw settlement using consistent ABI encoding.
    """
    contract_address = w3.to_checksum_address(settings.CHESS_CONTRACT_ADDRESS)

    # 1. Matches Vyper's concat(convert(game_id, bytes32), convert("DRAW", bytes32)...)
    # Note: "string" in eth_abi pads differently than a fixed bytes32.
    # If your Vyper contract uses 'bytes32' for the "DRAW" label, use 'bytes32' here.
    encoded_data = eth_abi.encode(
        ["uint256", "string", "address"], [game_id, "DRAW", contract_address]
    )

    # 2. Hash and wrap
    data_hash = w3.keccak(encoded_data)
    message = encode_defunct(primitive=data_hash)

    # 3. Sign using the standard Web3.py method
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
