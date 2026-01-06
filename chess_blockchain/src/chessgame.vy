# @version ^0.4.0

# -------------------------------------------------
# STRUCTS
# -------------------------------------------------

struct Challenge:
    player_white: address
    player_black: address
    bet_amount: uint256
    is_active: bool
    is_completed: bool


# -------------------------------------------------
# STORAGE
# -------------------------------------------------

# Django server (judge) address - immutable for gas optimization
judge_address: public(immutable(address))

# game_id => Challenge
challenges: public(HashMap[uint256, Challenge])

# prevent signature replay
used_messages: HashMap[bytes32, bool]

# Track game creation timestamp for timeout handling
game_created_at: HashMap[uint256, uint256]

# Timeout period (24 hours in seconds)
TIMEOUT_PERIOD: constant(uint256) = 86400


# -------------------------------------------------
# EVENTS
# -------------------------------------------------

event ChallengeCreated:
    game_id: indexed(uint256)
    creator: address
    amount: uint256

event ChallengeStarted:
    game_id: indexed(uint256)
    opponent: address

event PayoutClaimed:
    game_id: indexed(uint256)
    winner: address
    amount: uint256

event DrawSettled:
    game_id: indexed(uint256)
    player_white: address
    player_black: address
    refund_amount: uint256

event GameAbandoned:
    game_id: indexed(uint256)
    claimer: address
    amount: uint256


# -------------------------------------------------
# CONSTRUCTOR
# -------------------------------------------------

@deploy
def __init__(judge: address):
    judge_address = judge


# -------------------------------------------------
# CHALLENGE DEPOSIT / JOIN
# -------------------------------------------------

@external
@payable
def deposit(game_id: uint256):
    """
    Creates or joins a wagered chess challenge.
    """
    challenge: Challenge = self.challenges[game_id]

    assert not challenge.is_completed, "Game already finished"
    assert msg.value > 0, "Bet must be > 0"

    # First player creates the challenge
    if challenge.player_white == empty(address):
        challenge.player_white = msg.sender
        challenge.bet_amount = msg.value
        challenge.is_active = False
        challenge.is_completed = False

        self.challenges[game_id] = challenge
        self.game_created_at[game_id] = block.timestamp
        
        log ChallengeCreated(
            game_id=game_id,
            creator=msg.sender,
            amount=msg.value
        )

    # Second player joins
    else:
        assert challenge.player_black == empty(address), "Game full"
        assert msg.value == challenge.bet_amount, "Bet mismatch"
        assert msg.sender != challenge.player_white, "Cannot play yourself"

        challenge.player_black = msg.sender
        challenge.is_active = True

        self.challenges[game_id] = challenge
        
        log ChallengeStarted(
            game_id=game_id,
            opponent=msg.sender
        )


# -------------------------------------------------
# CLAIM WINNINGS (JUDGE-SIGNED) - FIXED SIGNATURE
# -------------------------------------------------

@external
def claim_winnings(
    game_id: uint256,
    winner: address,
    v: uint256,
    r: bytes32,
    s: bytes32
):
    """
    Winner claims payout using EIP-191 compliant signature from Django judge.
    """
    challenge: Challenge = self.challenges[game_id]

    assert challenge.is_active, "Challenge not active"
    assert not challenge.is_completed, "Already paid"
    assert winner == challenge.player_white or winner == challenge.player_black, "Invalid winner"

    # FIXED: EIP-191 compliant message hash
    # First hash the data
    data_hash: bytes32 = keccak256(
        concat(
            convert(game_id, bytes32),
            convert(winner, bytes32),
            convert(self, bytes32)
        )
    )
    
    # Then wrap with Ethereum Signed Message prefix
    message_hash: bytes32 = keccak256(
        concat(
            convert("\x19Ethereum Signed Message:\n32", Bytes[28]),
            data_hash
        )
    )

    assert not self.used_messages[message_hash], "Signature already used"

    # Verify signature - convert v from uint256 to uint8
    signer: address = ecrecover(message_hash, convert(v, uint8), r, s)
    assert signer == judge_address, "Invalid judge signature"

    # Mark state BEFORE transfer (reentrancy-safe)
    challenge.is_completed = True
    challenge.is_active = False
    self.challenges[game_id] = challenge
    self.used_messages[message_hash] = True

    total_pot: uint256 = challenge.bet_amount * 2

    # Payout
    raw_call(
        winner,
        b"",
        value=total_pot,
        gas=2300,
        revert_on_failure=True
    )

    log PayoutClaimed(
        game_id=game_id,
        winner=winner,
        amount=total_pot
    )


# -------------------------------------------------
# DRAW SETTLEMENT (JUDGE-SIGNED)
# -------------------------------------------------

@external
def settle_draw(
    game_id: uint256,
    v: uint256,
    r: bytes32,
    s: bytes32
):
    """
    Settle a draw and refund both players.
    """
    challenge: Challenge = self.challenges[game_id]

    assert challenge.is_active, "Challenge not active"
    assert not challenge.is_completed, "Already settled"
    assert challenge.player_black != empty(address), "Need both players"

    # Create draw message hash
    data_hash: bytes32 = keccak256(
        concat(
            convert(game_id, bytes32),
            convert("DRAW", Bytes[4]),
            convert(self, bytes32)
        )
    )
    
    message_hash: bytes32 = keccak256(
        concat(
            convert("\x19Ethereum Signed Message:\n32", Bytes[28]),
            data_hash
        )
    )

    assert not self.used_messages[message_hash], "Signature already used"

    signer: address = ecrecover(message_hash, convert(v, uint8), r, s)
    assert signer == judge_address, "Invalid judge signature"

    # Mark state BEFORE transfers
    challenge.is_completed = True
    challenge.is_active = False
    self.challenges[game_id] = challenge
    self.used_messages[message_hash] = True

    refund_amount: uint256 = challenge.bet_amount

    # Refund both players
    raw_call(challenge.player_white, b"", value=refund_amount, gas=2300, revert_on_failure=True)
    raw_call(challenge.player_black, b"", value=refund_amount, gas=2300, revert_on_failure=True)

    log DrawSettled(
        game_id=game_id,
        player_white=challenge.player_white,
        player_black=challenge.player_black,
        refund_amount=refund_amount
    )


# -------------------------------------------------
# TIMEOUT / ABANDONMENT HANDLER
# -------------------------------------------------

@external
def claim_abandonment(game_id: uint256):
    """
    If opponent abandons after timeout period, claim the pot.
    """
    challenge: Challenge = self.challenges[game_id]
    
    assert challenge.is_active, "Challenge not active"
    assert not challenge.is_completed, "Already completed"
    assert block.timestamp >= self.game_created_at[game_id] + TIMEOUT_PERIOD, "Timeout not reached"
    
    # Only players can claim
    assert msg.sender == challenge.player_white or msg.sender == challenge.player_black, "Not a player"

    # Mark complete before transfer
    challenge.is_completed = True
    challenge.is_active = False
    self.challenges[game_id] = challenge

    total_pot: uint256 = challenge.bet_amount * 2

    raw_call(msg.sender, b"", value=total_pot, gas=2300, revert_on_failure=True)

    log GameAbandoned(
        game_id=game_id,
        claimer=msg.sender,
        amount=total_pot
    )


# -------------------------------------------------
# VIEW FUNCTION
# -------------------------------------------------

@view
@external
def get_challenge(game_id: uint256) -> Challenge:
    """
    Get challenge details.
    """
    return self.challenges[game_id]