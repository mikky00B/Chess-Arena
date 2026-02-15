from pathlib import Path


CONTRACT_PATH = Path(__file__).resolve().parents[1] / "src" / "chessgame.vy"


def _source() -> str:
    return CONTRACT_PATH.read_text(encoding="utf-8")


def test_contract_file_exists():
    assert CONTRACT_PATH.exists()


def test_core_entrypoints_exist():
    source = _source()
    for fn_name in ("deposit", "claim_winnings", "settle_draw", "claim_abandonment"):
        assert f"def {fn_name}(" in source


def test_timeout_constant_is_defined():
    source = _source()
    assert "TIMEOUT_PERIOD: constant(uint256)" in source


def test_replay_protection_state_exists():
    source = _source()
    assert "used_messages: HashMap[bytes32, bool]" in source
