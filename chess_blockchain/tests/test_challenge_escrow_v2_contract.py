from pathlib import Path


CONTRACT_PATH = Path(__file__).resolve().parents[1] / "src" / "challenge_escrow_v2.vy"


def _source() -> str:
    return CONTRACT_PATH.read_text(encoding="utf-8")


def test_contract_file_exists():
    assert CONTRACT_PATH.exists()


def test_required_entrypoints_exist():
    source = _source()
    for fn_name in (
        "create_challenge",
        "deposit",
        "settle_winner",
        "settle_draw",
        "refund_expired_unfunded",
    ):
        assert f"def {fn_name}(" in source


def test_settlement_is_authority_gated():
    source = _source()
    assert "settlement_authority" in source
    assert source.count('assert msg.sender == settlement_authority, "only authority"') == 2


def test_replay_protection_state_exists():
    source = _source()
    assert "used_settlements: public(HashMap[bytes32, bool])" in source
    assert "settlement replay" in source


def test_arbitrary_abandonment_claim_is_removed():
    source = _source()
    assert "claim_abandonment" not in source
    assert "GameAbandoned" not in source
