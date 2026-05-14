from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.game import Game
    from app.models.user import User


class TournamentStatus(StrEnum):
    DRAFT = "DRAFT"
    REGISTRATION_OPEN = "REGISTRATION_OPEN"
    REGISTRATION_CLOSED = "REGISTRATION_CLOSED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    PRIZES_DISTRIBUTED = "PRIZES_DISTRIBUTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    DISPUTED = "DISPUTED"


class TournamentFormat(StrEnum):
    SINGLE_ELIMINATION = "SINGLE_ELIMINATION"
    ROUND_ROBIN = "ROUND_ROBIN"
    SWISS = "SWISS"
    ARENA = "ARENA"


class PrizeAssetType(StrEnum):
    NFT = "NFT"
    ERC20 = "ERC20"
    NATIVE = "NATIVE"
    POINTS = "POINTS"
    OFF_CHAIN = "OFF_CHAIN"


class Tournament(Base):
    __tablename__ = "tournaments"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organizer_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text)
    format: Mapped[TournamentFormat] = mapped_column(
        Enum(TournamentFormat, native_enum=False, length=32),
        index=True,
    )
    status: Mapped[TournamentStatus] = mapped_column(
        Enum(TournamentStatus, native_enum=False, length=32),
        default=TournamentStatus.DRAFT,
        index=True,
    )
    max_players: Mapped[int] = mapped_column(Integer)
    time_control_initial_seconds: Mapped[int] = mapped_column(Integer)
    time_control_increment_seconds: Mapped[int] = mapped_column(Integer, default=0)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    registration_opens_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    registration_closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    organizer: Mapped[User] = relationship()
    participants: Mapped[list[TournamentParticipant]] = relationship(
        back_populates="tournament",
        cascade="all, delete-orphan",
    )
    rounds: Mapped[list[TournamentRound]] = relationship(
        back_populates="tournament",
        cascade="all, delete-orphan",
    )
    prizes: Mapped[list[Prize]] = relationship(
        back_populates="tournament",
        cascade="all, delete-orphan",
    )


class TournamentParticipant(Base):
    __tablename__ = "tournament_participants"
    __table_args__ = (
        UniqueConstraint("tournament_id", "user_id", name="uq_tournament_participant_user"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tournament_id: Mapped[UUID] = mapped_column(ForeignKey("tournaments.id"), index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    seed: Mapped[int | None] = mapped_column(Integer)
    eliminated: Mapped[bool] = mapped_column(default=False)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    tournament: Mapped[Tournament] = relationship(back_populates="participants")
    user: Mapped[User] = relationship()


class TournamentRound(Base):
    __tablename__ = "tournament_rounds"
    __table_args__ = (
        UniqueConstraint("tournament_id", "round_number", name="uq_tournament_round_number"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tournament_id: Mapped[UUID] = mapped_column(ForeignKey("tournaments.id"), index=True)
    round_number: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    tournament: Mapped[Tournament] = relationship(back_populates="rounds")
    matches: Mapped[list[TournamentMatch]] = relationship(
        back_populates="round",
        cascade="all, delete-orphan",
    )


class TournamentMatch(Base):
    __tablename__ = "tournament_matches"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tournament_id: Mapped[UUID] = mapped_column(ForeignKey("tournaments.id"), index=True)
    round_id: Mapped[UUID] = mapped_column(ForeignKey("tournament_rounds.id"), index=True)
    game_id: Mapped[UUID] = mapped_column(ForeignKey("games.id"), unique=True)
    white_participant_id: Mapped[UUID] = mapped_column(ForeignKey("tournament_participants.id"))
    black_participant_id: Mapped[UUID] = mapped_column(ForeignKey("tournament_participants.id"))
    winner_participant_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tournament_participants.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    round: Mapped[TournamentRound] = relationship(back_populates="matches")
    game: Mapped[Game] = relationship()
    white_participant: Mapped[TournamentParticipant] = relationship(
        foreign_keys=[white_participant_id]
    )
    black_participant: Mapped[TournamentParticipant] = relationship(
        foreign_keys=[black_participant_id]
    )
    winner_participant: Mapped[TournamentParticipant | None] = relationship(
        foreign_keys=[winner_participant_id]
    )


class Prize(Base):
    __tablename__ = "prizes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tournament_id: Mapped[UUID] = mapped_column(ForeignKey("tournaments.id"), index=True)
    rank: Mapped[int] = mapped_column(Integer)
    asset_type: Mapped[PrizeAssetType] = mapped_column(
        Enum(PrizeAssetType, native_enum=False, length=16),
    )
    token_address: Mapped[str | None] = mapped_column(String(64))
    token_id: Mapped[str | None] = mapped_column(String(128))
    amount: Mapped[int | None] = mapped_column(Numeric(38, 0))
    metadata_uri: Mapped[str | None] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text)

    tournament: Mapped[Tournament] = relationship(back_populates="prizes")


class PrizeDistribution(Base):
    __tablename__ = "prize_distributions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    prize_id: Mapped[UUID] = mapped_column(ForeignKey("prizes.id"), index=True)
    tournament_id: Mapped[UUID] = mapped_column(ForeignKey("tournaments.id"), index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="PENDING")
    tx_hash: Mapped[str | None] = mapped_column(String(80))
    distributed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    prize: Mapped[Prize] = relationship()
    tournament: Mapped[Tournament] = relationship()
    user: Mapped[User] = relationship()
