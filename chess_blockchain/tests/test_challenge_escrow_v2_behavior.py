from pathlib import Path

import boa
from boa.interpret import set_cache_dir


CONTRACT_PATH = Path(__file__).resolve().parents[1] / "src" / "challenge_escrow_v2.vy"
CACHE_PATH = Path(__file__).resolve().parents[1] / ".boa_cache"


def deploy_contract():
    boa.reset_env()
    set_cache_dir(str(CACHE_PATH))
    authority = boa.env.generate_address("authority")
    white = boa.env.generate_address("white")
    black = boa.env.generate_address("black")
    outsider = boa.env.generate_address("outsider")
    for account in (authority, white, black, outsider):
        boa.env.set_balance(account, 10**20)
    contract = boa.load(str(CONTRACT_PATH), authority)
    return contract, authority, white, black, outsider


def test_deposits_fund_challenge_and_winner_settlement_pays_winner():
    contract, authority, white, black, _outsider = deploy_contract()
    amount = 10**15
    contract.create_challenge(1, white, black, amount, boa.env.timestamp + 3600)

    with boa.env.prank(white):
        contract.deposit(1, value=amount)
    with boa.env.prank(black):
        contract.deposit(1, value=amount)

    before = boa.env.get_balance(white)
    with boa.env.prank(authority):
        contract.settle_winner(1, white, b"\x01" * 32)

    assert boa.env.get_balance(white) == before + amount * 2
    assert contract.used_settlements(b"\x01" * 32) is True


def test_wrong_amount_wrong_player_duplicate_deposit_and_replay_are_rejected():
    contract, authority, white, black, outsider = deploy_contract()
    amount = 10**15
    contract.create_challenge(2, white, black, amount, boa.env.timestamp + 3600)

    with boa.env.prank(outsider):
        with boa.reverts("wrong player"):
            contract.deposit(2, value=amount)
    with boa.env.prank(white):
        with boa.reverts("wrong amount"):
            contract.deposit(2, value=amount - 1)
        contract.deposit(2, value=amount)
        with boa.reverts("white already deposited"):
            contract.deposit(2, value=amount)
    with boa.env.prank(black):
        contract.deposit(2, value=amount)
    with boa.env.prank(authority):
        contract.settle_draw(2, b"\x02" * 32)

    contract.create_challenge(3, white, black, amount, boa.env.timestamp + 3600)
    with boa.env.prank(white):
        contract.deposit(3, value=amount)
    with boa.env.prank(black):
        contract.deposit(3, value=amount)
    with boa.env.prank(authority):
        with boa.reverts("settlement replay"):
            contract.settle_winner(3, white, b"\x02" * 32)


def test_non_authority_cannot_settle_and_expired_unfunded_refunds_depositor():
    contract, _authority, white, black, outsider = deploy_contract()
    amount = 10**15
    contract.create_challenge(4, white, black, amount, boa.env.timestamp + 60)
    with boa.env.prank(white):
        contract.deposit(4, value=amount)

    with boa.env.prank(outsider):
        with boa.reverts("only authority"):
            contract.settle_winner(4, white, b"\x04" * 32)

    before = boa.env.get_balance(white)
    boa.env.time_travel(seconds=120)
    contract.refund_expired_unfunded(4)

    assert boa.env.get_balance(white) == before + amount
