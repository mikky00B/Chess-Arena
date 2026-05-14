# @version ^0.4.0

enum ChallengeStatus:
    EMPTY
    CREATED
    FUNDED
    SETTLED
    REFUNDED
    CANCELLED

struct Challenge:
    white: address
    black: address
    amount: uint256
    white_deposited: bool
    black_deposited: bool
    expires_at: uint256
    status: ChallengeStatus

settlement_authority: public(immutable(address))
challenges: public(HashMap[uint256, Challenge])
used_settlements: public(HashMap[bytes32, bool])

event ChallengeCreated:
    challenge_id: indexed(uint256)
    white: indexed(address)
    black: indexed(address)
    amount: uint256
    expires_at: uint256

event DepositReceived:
    challenge_id: indexed(uint256)
    player: indexed(address)
    amount: uint256

event ChallengeFunded:
    challenge_id: indexed(uint256)

event WinnerSettled:
    challenge_id: indexed(uint256)
    winner: indexed(address)
    amount: uint256
    settlement_id: bytes32

event DrawRefunded:
    challenge_id: indexed(uint256)
    white: address
    black: address
    amount: uint256
    settlement_id: bytes32

event ExpiredUnfundedRefunded:
    challenge_id: indexed(uint256)


@deploy
def __init__(authority: address):
    assert authority != empty(address), "authority required"
    settlement_authority = authority


@external
def create_challenge(
    challenge_id: uint256,
    white: address,
    black: address,
    amount: uint256,
    expires_at: uint256
):
    assert self.challenges[challenge_id].white == empty(address), "challenge exists"
    assert white != empty(address), "white required"
    assert black != empty(address), "black required"
    assert white != black, "players must differ"
    assert amount > 0, "amount required"
    assert expires_at > block.timestamp, "expiry must be future"

    self.challenges[challenge_id] = Challenge(
        white=white,
        black=black,
        amount=amount,
        white_deposited=False,
        black_deposited=False,
        expires_at=expires_at,
        status=ChallengeStatus.CREATED
    )

    log ChallengeCreated(
        challenge_id=challenge_id,
        white=white,
        black=black,
        amount=amount,
        expires_at=expires_at
    )


@external
@payable
def deposit(challenge_id: uint256):
    challenge: Challenge = self.challenges[challenge_id]
    assert challenge.status == ChallengeStatus.CREATED, "challenge not depositable"
    assert msg.sender == challenge.white or msg.sender == challenge.black, "wrong player"
    assert msg.value == challenge.amount, "wrong amount"

    if msg.sender == challenge.white:
        assert not challenge.white_deposited, "white already deposited"
        challenge.white_deposited = True
    else:
        assert not challenge.black_deposited, "black already deposited"
        challenge.black_deposited = True

    if challenge.white_deposited and challenge.black_deposited:
        challenge.status = ChallengeStatus.FUNDED

    self.challenges[challenge_id] = challenge

    log DepositReceived(challenge_id=challenge_id, player=msg.sender, amount=msg.value)
    if challenge.status == ChallengeStatus.FUNDED:
        log ChallengeFunded(challenge_id=challenge_id)


@external
def settle_winner(challenge_id: uint256, winner: address, settlement_id: bytes32):
    assert msg.sender == settlement_authority, "only authority"
    assert not self.used_settlements[settlement_id], "settlement replay"
    challenge: Challenge = self.challenges[challenge_id]
    assert challenge.status == ChallengeStatus.FUNDED, "challenge not funded"
    assert winner == challenge.white or winner == challenge.black, "invalid winner"

    self.used_settlements[settlement_id] = True
    challenge.status = ChallengeStatus.SETTLED
    self.challenges[challenge_id] = challenge

    payout: uint256 = challenge.amount * 2
    raw_call(winner, b"", value=payout, gas=2300, revert_on_failure=True)

    log WinnerSettled(
        challenge_id=challenge_id,
        winner=winner,
        amount=payout,
        settlement_id=settlement_id
    )


@external
def settle_draw(challenge_id: uint256, settlement_id: bytes32):
    assert msg.sender == settlement_authority, "only authority"
    assert not self.used_settlements[settlement_id], "settlement replay"
    challenge: Challenge = self.challenges[challenge_id]
    assert challenge.status == ChallengeStatus.FUNDED, "challenge not funded"

    self.used_settlements[settlement_id] = True
    challenge.status = ChallengeStatus.SETTLED
    self.challenges[challenge_id] = challenge

    raw_call(challenge.white, b"", value=challenge.amount, gas=2300, revert_on_failure=True)
    raw_call(challenge.black, b"", value=challenge.amount, gas=2300, revert_on_failure=True)

    log DrawRefunded(
        challenge_id=challenge_id,
        white=challenge.white,
        black=challenge.black,
        amount=challenge.amount,
        settlement_id=settlement_id
    )


@external
def refund_expired_unfunded(challenge_id: uint256):
    challenge: Challenge = self.challenges[challenge_id]
    assert challenge.status == ChallengeStatus.CREATED, "challenge not refundable"
    assert block.timestamp >= challenge.expires_at, "not expired"

    challenge.status = ChallengeStatus.REFUNDED
    self.challenges[challenge_id] = challenge

    if challenge.white_deposited:
        raw_call(challenge.white, b"", value=challenge.amount, gas=2300, revert_on_failure=True)
    if challenge.black_deposited:
        raw_call(challenge.black, b"", value=challenge.amount, gas=2300, revert_on_failure=True)

    log ExpiredUnfundedRefunded(challenge_id=challenge_id)
