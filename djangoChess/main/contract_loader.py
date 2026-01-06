"""
Load contract ABI from Moccasin compilation output
"""

import json
import os
from pathlib import Path


def get_contract_abi():
    """
    Load the ChessGame contract ABI from Moccasin output.

    Returns:
        list: Contract ABI
    """
    # Get the project root (assumes this file is in djangoChess/main/)
    django_root = Path(__file__).parent.parent
    project_root = django_root.parent

    # Path to Moccasin output
    abi_path = project_root / "chess_blockchain" / "out" / "chessgame.json"

    if not abi_path.exists():
        raise FileNotFoundError(
            f"Contract ABI not found at {abi_path}. "
            "Please run 'moccasin compile' in the chess_blockchain directory first."
        )

    with open(abi_path, "r") as f:
        contract_data = json.load(f)

    # Moccasin output includes abi, bytecode, etc.
    return contract_data["abi"]


def get_contract_bytecode():
    """
    Load the ChessGame contract bytecode from Moccasin output.

    Returns:
        str: Contract bytecode
    """
    django_root = Path(__file__).parent.parent
    project_root = django_root.parent

    abi_path = project_root / "chess_blockchain" / "out" / "chessgame.json"

    if not abi_path.exists():
        raise FileNotFoundError(
            f"Contract bytecode not found at {abi_path}. "
            "Please run 'moccasin compile' in the chess_blockchain directory first."
        )

    with open(abi_path, "r") as f:
        contract_data = json.load(f)

    return contract_data["bytecode"]["object"]


# Load ABI once at module import
try:
    CONTRACT_ABI = get_contract_abi()
except FileNotFoundError as e:
    print(f"Warning: {e}")
    CONTRACT_ABI = []
    print(CONTRACT_ABI)  # Empty ABI as fallback
