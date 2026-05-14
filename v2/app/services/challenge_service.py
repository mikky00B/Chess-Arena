from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.game.state import GameResult, GameSourceType, GameStatus, TimeControl
from app.models import (
    Challenge,
    ChallengeStatus,
    DepositRole,
    EscrowDeposit,
    SettlementRequest,
    SettlementSourceType,
    SettlementStatus,
    StakeAssetType,
    User,
)
from app.services.game_service import GameService


class ChallengeServiceError(ValueError):
    pass


class ChallengeNotFoundError(ChallengeServiceError):
    pass


class DepositVerificationError(ChallengeServiceError):
    pass


@dataclass(frozen=True, slots=True)
class DepositVerification:
    user_id: UUID
    role: DepositRole
    wallet_address: str
    tx_hash: str
    chain_id: int
    escrow_contract_address: str
    token_address: str | None
    amount: int


class ChallengeService:
    def __init__(self, *, game_service: GameService | None = None) -> None:
        self.game_service = game_service or GameService()

    async def create_challenge(
        self,
        session: AsyncSession,
        *,
        creator_id: UUID,
        creator_wallet_address: str,
        stake_asset_type: StakeAssetType,
        stake_amount: int,
        chain_id: int,
        escrow_contract_address: str,
        stake_token_address: str | None = None,
        expires_at: datetime | None = None,
        now: datetime | None = None,
    ) -> Challenge:
        creator = await session.get(User, creator_id)
        if creator is None:
            raise ChallengeServiceError("creator must exist")
        if stake_amount <= 0:
            raise ChallengeServiceError("stake amount must be positive")
        if stake_asset_type == StakeAssetType.ERC20 and not stake_token_address:
            raise ChallengeServiceError("ERC20 challenges require a token address")
        if stake_asset_type == StakeAssetType.NATIVE and stake_token_address is not None:
            raise ChallengeServiceError("native challenges cannot include a token address")
        if not creator_wallet_address:
            raise ChallengeServiceError("creator wallet address is required")

        challenge = Challenge(
            creator_id=creator_id,
            opponent_id=None,
            game_id=None,
            status=ChallengeStatus.CREATED,
            stake_asset_type=stake_asset_type,
            stake_token_address=self.normalize_address(stake_token_address),
            stake_amount=stake_amount,
            chain_id=chain_id,
            escrow_contract_address=self.normalize_address(escrow_contract_address) or "",
            creator_wallet_address=self.normalize_address(creator_wallet_address) or "",
            opponent_wallet_address=None,
            created_at=now or datetime.now(UTC),
            accepted_at=None,
            funded_at=None,
            expires_at=expires_at,
            settled_at=None,
        )
        session.add(challenge)
        await session.flush()
        return challenge

    async def accept_challenge(
        self,
        session: AsyncSession,
        *,
        challenge_id: UUID,
        opponent_id: UUID,
        opponent_wallet_address: str,
        time_control: TimeControl,
        rated: bool = False,
        now: datetime | None = None,
    ) -> Challenge:
        challenge = await self.get_challenge(session, challenge_id=challenge_id)
        if challenge.status != ChallengeStatus.CREATED:
            raise ChallengeServiceError("only created challenges can be accepted")
        if challenge.creator_id == opponent_id:
            raise ChallengeServiceError("creator cannot accept their own challenge")
        opponent = await session.get(User, opponent_id)
        creator = await session.get(User, challenge.creator_id)
        if opponent is None or creator is None:
            raise ChallengeServiceError("both challenge players must exist")
        if not opponent_wallet_address:
            raise ChallengeServiceError("opponent wallet address is required")

        accepted_at = now or datetime.now(UTC)
        game = self.game_service.build_general_game(
            white_player=creator,
            black_player=opponent,
            time_control=time_control,
            rated=rated,
            now=accepted_at,
        )
        game.status = GameStatus.WAITING_FOR_PLAYERS
        game.source_type = GameSourceType.CHALLENGE
        game.source_id = str(challenge.id)
        session.add(game)
        await session.flush()

        challenge.opponent_id = opponent_id
        challenge.opponent_wallet_address = self.normalize_address(opponent_wallet_address)
        challenge.game_id = game.id
        challenge.status = ChallengeStatus.AWAITING_DEPOSITS
        challenge.accepted_at = accepted_at
        await session.flush()
        return challenge

    async def verify_deposit(
        self,
        session: AsyncSession,
        *,
        challenge_id: UUID,
        verification: DepositVerification,
        now: datetime | None = None,
    ) -> EscrowDeposit:
        challenge = await self.get_challenge(session, challenge_id=challenge_id)
        self.validate_deposit(challenge, verification)
        existing_tx = await session.scalar(
            select(EscrowDeposit).where(EscrowDeposit.tx_hash == verification.tx_hash)
        )
        if existing_tx is not None:
            raise DepositVerificationError("deposit transaction has already been used")

        deposit = EscrowDeposit(
            challenge_id=challenge.id,
            user_id=verification.user_id,
            role=verification.role,
            wallet_address=self.normalize_address(verification.wallet_address) or "",
            tx_hash=verification.tx_hash,
            chain_id=verification.chain_id,
            token_address=self.normalize_address(verification.token_address),
            amount=verification.amount,
            escrow_contract_address=self.normalize_address(verification.escrow_contract_address)
            or "",
            verified=True,
            verified_at=now or datetime.now(UTC),
            created_at=now or datetime.now(UTC),
        )
        session.add(deposit)
        challenge.deposits.append(deposit)
        await session.flush()

        if self.has_verified_deposits(challenge):
            challenge.status = ChallengeStatus.FUNDED
            challenge.funded_at = now or datetime.now(UTC)
        await session.flush()
        return deposit

    async def start_funded_challenge(
        self,
        session: AsyncSession,
        *,
        challenge_id: UUID,
        now: datetime | None = None,
    ) -> Challenge:
        challenge = await self.get_challenge(session, challenge_id=challenge_id)
        if challenge.status != ChallengeStatus.FUNDED:
            raise ChallengeServiceError("challenge must be fully funded before start")
        if challenge.game is None:
            raise ChallengeServiceError("challenge has no game")
        self.game_service.start_general_game(challenge.game, now=now)
        challenge.status = ChallengeStatus.IN_PROGRESS
        await session.flush()
        return challenge

    async def cancel_challenge(
        self,
        session: AsyncSession,
        *,
        challenge_id: UUID,
    ) -> Challenge:
        challenge = await self.get_challenge(session, challenge_id=challenge_id)
        if challenge.status not in {
            ChallengeStatus.CREATED,
            ChallengeStatus.AWAITING_DEPOSITS,
        }:
            raise ChallengeServiceError("only unfunded challenges can be cancelled")
        if any(deposit.verified for deposit in challenge.deposits):
            raise ChallengeServiceError("funded deposits must be refunded, not cancelled")
        challenge.status = ChallengeStatus.CANCELLED
        await session.flush()
        return challenge

    async def create_settlement_request(
        self,
        session: AsyncSession,
        *,
        challenge_id: UUID,
        now: datetime | None = None,
    ) -> SettlementRequest:
        challenge = await self.get_challenge(session, challenge_id=challenge_id)
        if challenge.game is None:
            raise ChallengeServiceError("challenge has no game")
        game = challenge.game
        if game.status != GameStatus.FINISHED or game.result is None:
            raise ChallengeServiceError("challenge game must be finished before settlement")

        amount = challenge.stake_amount * 2
        recipient = None
        if game.result != GameResult.DRAW:
            if game.winner_id is None:
                raise ChallengeServiceError("winner settlement requires a winner")
            if game.winner_id == challenge.creator_id:
                recipient = challenge.creator_wallet_address
            elif game.winner_id == challenge.opponent_id:
                recipient = challenge.opponent_wallet_address
            else:
                raise ChallengeServiceError("winner is not a challenge participant")

        payload_hash = self.payload_hash(
            challenge_id=challenge.id,
            game_id=game.id,
            result=game.result,
            winner_id=game.winner_id,
            amount=amount,
            recipient_address=recipient,
        )
        settlement = SettlementRequest(
            source_type=SettlementSourceType.CHALLENGE,
            source_id=challenge.id,
            game_id=game.id,
            status=SettlementStatus.PENDING,
            result=game.result,
            winner_id=game.winner_id,
            asset_type=challenge.stake_asset_type,
            token_address=challenge.stake_token_address,
            amount=amount,
            recipient_address=recipient,
            payload_hash=payload_hash,
            multisig_tx_hash=None,
            executed_tx_hash=None,
            created_at=now or datetime.now(UTC),
            approved_at=None,
            executed_at=None,
        )
        session.add(settlement)
        challenge.status = ChallengeStatus.FINISHED
        await session.flush()
        return settlement

    async def get_challenge(self, session: AsyncSession, *, challenge_id: UUID) -> Challenge:
        statement = (
            select(Challenge)
            .where(Challenge.id == challenge_id)
            .options(selectinload(Challenge.deposits), selectinload(Challenge.game))
        )
        challenge = await session.scalar(statement)
        if challenge is None:
            raise ChallengeNotFoundError("challenge not found")
        return challenge

    def validate_deposit(
        self,
        challenge: Challenge,
        verification: DepositVerification,
    ) -> None:
        if challenge.status not in {ChallengeStatus.AWAITING_DEPOSITS, ChallengeStatus.FUNDED}:
            raise DepositVerificationError("challenge is not awaiting deposits")
        expected_user = challenge.opponent_id
        if verification.role == DepositRole.WHITE:
            expected_user = challenge.creator_id
        expected_wallet = (
            challenge.creator_wallet_address
            if verification.role == DepositRole.WHITE
            else challenge.opponent_wallet_address
        )
        if expected_user is None or expected_wallet is None:
            raise DepositVerificationError("deposit role is not assigned")
        if verification.user_id != expected_user:
            raise DepositVerificationError("deposit user does not match role")
        if self.normalize_address(verification.wallet_address) != expected_wallet:
            raise DepositVerificationError("deposit wallet does not match player wallet")
        if verification.chain_id != challenge.chain_id:
            raise DepositVerificationError("deposit chain does not match challenge")
        if (
            self.normalize_address(verification.escrow_contract_address)
            != challenge.escrow_contract_address
        ):
            raise DepositVerificationError("deposit contract does not match challenge")
        if self.normalize_address(verification.token_address) != challenge.stake_token_address:
            raise DepositVerificationError("deposit token does not match challenge")
        if verification.amount != challenge.stake_amount:
            raise DepositVerificationError("deposit amount does not match stake")
        role_already_verified = any(
            deposit.role == verification.role and deposit.verified
            for deposit in challenge.deposits
        )
        if role_already_verified:
            raise DepositVerificationError("deposit role has already been verified")

    def has_verified_deposits(self, challenge: Challenge) -> bool:
        verified_roles = {deposit.role for deposit in challenge.deposits if deposit.verified}
        return {DepositRole.WHITE, DepositRole.BLACK}.issubset(verified_roles)

    def payload_hash(
        self,
        *,
        challenge_id: UUID,
        game_id: UUID,
        result: GameResult,
        winner_id: UUID | None,
        amount: int,
        recipient_address: str | None,
    ) -> str:
        payload = "|".join(
            [
                str(challenge_id),
                str(game_id),
                result,
                str(winner_id or ""),
                str(amount),
                recipient_address or "",
            ]
        )
        return "0x" + sha256(payload.encode("utf-8")).hexdigest()

    def normalize_address(self, address: str | None) -> str | None:
        if address is None:
            return None
        return address.lower()
