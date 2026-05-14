from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.models import Challenge, ChallengeStatus, DepositRole, EscrowDeposit, StakeAssetType
from app.services.challenge_service import (
    ChallengeService,
    ChallengeServiceError,
    DepositVerification,
    DepositVerificationError,
)


def make_challenge() -> Challenge:
    return Challenge(
        id=uuid4(),
        creator_id=uuid4(),
        opponent_id=uuid4(),
        game_id=uuid4(),
        status=ChallengeStatus.AWAITING_DEPOSITS,
        stake_asset_type=StakeAssetType.NATIVE,
        stake_token_address=None,
        stake_amount=100,
        chain_id=8453,
        escrow_contract_address="0xescrow",
        creator_wallet_address="0xwhite",
        opponent_wallet_address="0xblack",
        created_at=datetime.now(UTC),
        accepted_at=datetime.now(UTC),
        funded_at=None,
        expires_at=None,
        settled_at=None,
    )


def make_verification(challenge: Challenge) -> DepositVerification:
    return DepositVerification(
        user_id=challenge.creator_id,
        role=DepositRole.WHITE,
        wallet_address="0xwhite",
        tx_hash="0xtx",
        chain_id=challenge.chain_id,
        escrow_contract_address=challenge.escrow_contract_address,
        token_address=None,
        amount=challenge.stake_amount,
    )


def test_validate_deposit_binds_transaction_to_expected_player_wallet() -> None:
    challenge = make_challenge()
    verification = make_verification(challenge)

    ChallengeService().validate_deposit(challenge, verification)

    wrong_wallet = DepositVerification(
        user_id=verification.user_id,
        role=verification.role,
        wallet_address="0xwrong",
        tx_hash=verification.tx_hash,
        chain_id=verification.chain_id,
        escrow_contract_address=verification.escrow_contract_address,
        token_address=verification.token_address,
        amount=verification.amount,
    )
    with pytest.raises(DepositVerificationError, match="wallet"):
        ChallengeService().validate_deposit(challenge, wrong_wallet)


def test_validate_deposit_rejects_wrong_amount_chain_contract_and_role_reuse() -> None:
    challenge = make_challenge()
    service = ChallengeService()
    verification = make_verification(challenge)

    with pytest.raises(DepositVerificationError, match="amount"):
        service.validate_deposit(
            challenge,
            DepositVerification(
                user_id=verification.user_id,
                role=verification.role,
                wallet_address=verification.wallet_address,
                tx_hash=verification.tx_hash,
                chain_id=verification.chain_id,
                escrow_contract_address=verification.escrow_contract_address,
                token_address=verification.token_address,
                amount=99,
            ),
        )

    challenge.deposits.append(
        EscrowDeposit(
            id=uuid4(),
            challenge_id=challenge.id,
            user_id=challenge.creator_id,
            role=DepositRole.WHITE,
            wallet_address="0xwhite",
            tx_hash="0xused",
            chain_id=challenge.chain_id,
            token_address=None,
            amount=challenge.stake_amount,
            escrow_contract_address=challenge.escrow_contract_address,
            verified=True,
            verified_at=datetime.now(UTC),
            created_at=datetime.now(UTC),
        )
    )
    with pytest.raises(DepositVerificationError, match="already"):
        service.validate_deposit(challenge, verification)


def test_has_verified_deposits_requires_both_roles() -> None:
    challenge = make_challenge()
    service = ChallengeService()

    challenge.deposits.extend(
        [
            EscrowDeposit(
                id=uuid4(),
                challenge_id=challenge.id,
                user_id=challenge.creator_id,
                role=DepositRole.WHITE,
                wallet_address="0xwhite",
                tx_hash="0xwhite",
                chain_id=challenge.chain_id,
                token_address=None,
                amount=challenge.stake_amount,
                escrow_contract_address=challenge.escrow_contract_address,
                verified=True,
                verified_at=datetime.now(UTC),
                created_at=datetime.now(UTC),
            ),
            EscrowDeposit(
                id=uuid4(),
                challenge_id=challenge.id,
                user_id=challenge.opponent_id,
                role=DepositRole.BLACK,
                wallet_address="0xblack",
                tx_hash="0xblack",
                chain_id=challenge.chain_id,
                token_address=None,
                amount=challenge.stake_amount,
                escrow_contract_address=challenge.escrow_contract_address,
                verified=True,
                verified_at=datetime.now(UTC),
                created_at=datetime.now(UTC),
            ),
        ]
    )

    assert service.has_verified_deposits(challenge) is True


class FakeSession:
    async def flush(self) -> None:
        return None


async def test_cancel_challenge_rejects_verified_deposits() -> None:
    challenge = make_challenge()
    challenge.deposits.append(
        EscrowDeposit(
            id=uuid4(),
            challenge_id=challenge.id,
            user_id=challenge.creator_id,
            role=DepositRole.WHITE,
            wallet_address="0xwhite",
            tx_hash="0xwhite",
            chain_id=challenge.chain_id,
            token_address=None,
            amount=challenge.stake_amount,
            escrow_contract_address=challenge.escrow_contract_address,
            verified=True,
            verified_at=datetime.now(UTC),
            created_at=datetime.now(UTC),
        )
    )
    service = ChallengeService()

    async def get_challenge(*_args: object, **_kwargs: object) -> Challenge:
        return challenge

    service.get_challenge = get_challenge  # type: ignore[method-assign]

    with pytest.raises(ChallengeServiceError, match="refunded"):
        await service.cancel_challenge(FakeSession(), challenge_id=challenge.id)
