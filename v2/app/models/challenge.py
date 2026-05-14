from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.game import Game
    from app.models.user import User


class ChallengeStatus(StrEnum):
    CREATED = "CREATED"
    ACCEPTED = "ACCEPTED"
    AWAITING_DEPOSITS = "AWAITING_DEPOSITS"
    FUNDED = "FUNDED"
    IN_PROGRESS = "IN_PROGRESS"
    FINISHED = "FINISHED"
    SETTLED = "SETTLED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    REFUNDED = "REFUNDED"
    DISPUTED = "DISPUTED"


class StakeAssetType(StrEnum):
    NATIVE = "NATIVE"
    ERC20 = "ERC20"


class DepositRole(StrEnum):
    WHITE = "WHITE"
    BLACK = "BLACK"


class SettlementStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    DISPUTED = "DISPUTED"


class SettlementSourceType(StrEnum):
    CHALLENGE = "CHALLENGE"
    TOURNAMENT = "TOURNAMENT"


class Challenge(Base):
    __tablename__ = "challenges"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    creator_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    opponent_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    game_id: Mapped[UUID | None] = mapped_column(ForeignKey("games.id"), unique=True)
    status: Mapped[ChallengeStatus] = mapped_column(
        Enum(ChallengeStatus, native_enum=False, length=32),
        default=ChallengeStatus.CREATED,
        index=True,
    )
    stake_asset_type: Mapped[StakeAssetType] = mapped_column(
        Enum(StakeAssetType, native_enum=False, length=16),
    )
    stake_token_address: Mapped[str | None] = mapped_column(String(64))
    stake_amount: Mapped[int] = mapped_column(Numeric(38, 0))
    chain_id: Mapped[int] = mapped_column(Integer)
    escrow_contract_address: Mapped[str] = mapped_column(String(64))
    creator_wallet_address: Mapped[str] = mapped_column(String(64))
    opponent_wallet_address: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    funded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    creator: Mapped[User] = relationship(foreign_keys=[creator_id])
    opponent: Mapped[User | None] = relationship(foreign_keys=[opponent_id])
    game: Mapped[Game | None] = relationship(foreign_keys=[game_id])
    deposits: Mapped[list[EscrowDeposit]] = relationship(
        back_populates="challenge",
        cascade="all, delete-orphan",
    )


class EscrowDeposit(Base):
    __tablename__ = "escrow_deposits"
    __table_args__ = (
        UniqueConstraint("tx_hash", name="uq_escrow_deposits_tx_hash"),
        UniqueConstraint("challenge_id", "role", name="uq_escrow_deposits_challenge_role"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    challenge_id: Mapped[UUID] = mapped_column(ForeignKey("challenges.id"), index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[DepositRole] = mapped_column(Enum(DepositRole, native_enum=False, length=8))
    wallet_address: Mapped[str] = mapped_column(String(64))
    tx_hash: Mapped[str] = mapped_column(String(80), index=True)
    chain_id: Mapped[int] = mapped_column(Integer)
    token_address: Mapped[str | None] = mapped_column(String(64))
    amount: Mapped[int] = mapped_column(Numeric(38, 0))
    escrow_contract_address: Mapped[str] = mapped_column(String(64))
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    challenge: Mapped[Challenge] = relationship(back_populates="deposits")
    user: Mapped[User] = relationship()


class SettlementRequest(Base):
    __tablename__ = "settlement_requests"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_type: Mapped[SettlementSourceType] = mapped_column(
        Enum(SettlementSourceType, native_enum=False, length=16),
        index=True,
    )
    source_id: Mapped[UUID] = mapped_column(index=True)
    game_id: Mapped[UUID] = mapped_column(ForeignKey("games.id"), index=True)
    status: Mapped[SettlementStatus] = mapped_column(
        Enum(SettlementStatus, native_enum=False, length=16),
        default=SettlementStatus.PENDING,
        index=True,
    )
    result: Mapped[str] = mapped_column(String(16))
    winner_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    asset_type: Mapped[StakeAssetType] = mapped_column(
        Enum(StakeAssetType, native_enum=False, length=16),
    )
    token_address: Mapped[str | None] = mapped_column(String(64))
    amount: Mapped[int] = mapped_column(Numeric(38, 0))
    recipient_address: Mapped[str | None] = mapped_column(String(64))
    payload_hash: Mapped[str] = mapped_column(String(66), unique=True)
    multisig_tx_hash: Mapped[str | None] = mapped_column(String(80))
    executed_tx_hash: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    game: Mapped[Game] = relationship()
    winner: Mapped[User | None] = relationship()
