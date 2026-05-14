from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Challenge, ChallengeStatus, SettlementRequest, SettlementStatus


class SettlementServiceError(ValueError):
    pass


class SettlementNotFoundError(SettlementServiceError):
    pass


@dataclass(frozen=True, slots=True)
class SettlementExecutionVerification:
    executed_tx_hash: str
    sender_address: str
    expected_multisig_address: str


class SettlementService:
    async def list_settlements(self, session: AsyncSession) -> list[SettlementRequest]:
        return list(await session.scalars(select(SettlementRequest)))

    async def get_settlement(
        self,
        session: AsyncSession,
        *,
        settlement_id: UUID,
    ) -> SettlementRequest:
        settlement = await session.get(SettlementRequest, settlement_id)
        if settlement is None:
            raise SettlementNotFoundError("settlement not found")
        return settlement

    async def approve_settlement(
        self,
        session: AsyncSession,
        *,
        settlement_id: UUID,
        multisig_tx_hash: str,
        now: datetime | None = None,
    ) -> SettlementRequest:
        settlement = await self.get_settlement(session, settlement_id=settlement_id)
        if settlement.status != SettlementStatus.PENDING:
            raise SettlementServiceError("only pending settlements can be approved")
        if not multisig_tx_hash:
            raise SettlementServiceError("multisig transaction hash is required")
        settlement.status = SettlementStatus.APPROVED
        settlement.multisig_tx_hash = multisig_tx_hash
        settlement.approved_at = now or datetime.now(UTC)
        await session.flush()
        return settlement

    async def verify_execution(
        self,
        session: AsyncSession,
        *,
        settlement_id: UUID,
        verification: SettlementExecutionVerification,
        now: datetime | None = None,
    ) -> SettlementRequest:
        settlement = await self.get_settlement(session, settlement_id=settlement_id)
        if settlement.status not in {SettlementStatus.PENDING, SettlementStatus.APPROVED}:
            raise SettlementServiceError("settlement is not executable")
        if not verification.executed_tx_hash:
            raise SettlementServiceError("executed transaction hash is required")
        if self.normalize_address(verification.sender_address) != self.normalize_address(
            verification.expected_multisig_address
        ):
            raise SettlementServiceError("settlement transaction was not sent by multisig")

        settlement.status = SettlementStatus.EXECUTED
        settlement.executed_tx_hash = verification.executed_tx_hash
        settlement.executed_at = now or datetime.now(UTC)

        challenge = await session.get(Challenge, settlement.source_id)
        if challenge is not None:
            challenge.status = ChallengeStatus.SETTLED
            challenge.settled_at = settlement.executed_at

        await session.flush()
        return settlement

    def normalize_address(self, address: str) -> str:
        return address.lower()
