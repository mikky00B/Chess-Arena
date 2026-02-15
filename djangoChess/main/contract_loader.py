"""Load compiled contract artifacts."""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _artifact_path() -> Path:
    django_root = Path(__file__).parent.parent
    project_root = django_root.parent
    return project_root / "chess_blockchain" / "out" / "chessgame.json"


def _load_artifact() -> dict:
    path = _artifact_path()
    if not path.exists():
        raise FileNotFoundError(
            f"Contract artifact not found at {path}. Run 'moccasin compile' in chess_blockchain."
        )
    with path.open("r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


def get_contract_abi():
    artifact = _load_artifact()
    abi = artifact.get("abi")
    if not abi:
        raise ValueError("ABI missing from compiled artifact")
    return abi


def get_contract_bytecode():
    artifact = _load_artifact()
    bytecode = artifact.get("bytecode", {}).get("object")
    if not bytecode:
        raise ValueError("Bytecode missing from compiled artifact")
    return bytecode


try:
    CONTRACT_ABI = get_contract_abi()
except Exception as exc:
    logger.warning("Contract ABI unavailable: %s", exc)
    CONTRACT_ABI = []
