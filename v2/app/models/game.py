from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.game.state import GameResult, GameSourceType, GameStatus, PlayerColor, ResultReason

if TYPE_CHECKING:
    from app.models.rating import RatingUpdate
    from app.models.user import User


class Game(Base):
    __tablename__ = "games"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    white_player_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    black_player_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[GameStatus] = mapped_column(
        Enum(GameStatus, native_enum=False, length=32),
        default=GameStatus.READY,
        index=True,
    )
    current_fen: Mapped[str] = mapped_column(Text)
    time_control_initial_seconds: Mapped[int] = mapped_column(Integer)
    time_control_increment_seconds: Mapped[int] = mapped_column(Integer, default=0)
    white_time_seconds: Mapped[int] = mapped_column(Integer)
    black_time_seconds: Mapped[int] = mapped_column(Integer)
    last_clock_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    turn: Mapped[PlayerColor] = mapped_column(Enum(PlayerColor, native_enum=False, length=8))
    rated: Mapped[bool] = mapped_column(Boolean, default=False)
    result: Mapped[GameResult | None] = mapped_column(
        Enum(GameResult, native_enum=False, length=16),
    )
    result_reason: Mapped[ResultReason | None] = mapped_column(
        Enum(ResultReason, native_enum=False, length=32),
    )
    winner_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    source_type: Mapped[GameSourceType] = mapped_column(
        Enum(GameSourceType, native_enum=False, length=32),
        index=True,
    )
    source_id: Mapped[str | None] = mapped_column(String(64), index=True)
    draw_offered_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    white_player: Mapped[User] = relationship(
        back_populates="white_games",
        foreign_keys=[white_player_id],
    )
    black_player: Mapped[User] = relationship(
        back_populates="black_games",
        foreign_keys=[black_player_id],
    )
    moves: Mapped[list[Move]] = relationship(
        back_populates="game",
        cascade="all, delete-orphan",
        order_by="Move.move_number",
    )
    rating_update: Mapped[RatingUpdate | None] = relationship(
        back_populates="game",
        cascade="all, delete-orphan",
    )


class Move(Base):
    __tablename__ = "moves"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    game_id: Mapped[UUID] = mapped_column(ForeignKey("games.id"), index=True)
    move_number: Mapped[int] = mapped_column(Integer)
    player_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    color: Mapped[PlayerColor] = mapped_column(Enum(PlayerColor, native_enum=False, length=8))
    uci: Mapped[str] = mapped_column(String(8))
    san: Mapped[str] = mapped_column(String(32))
    fen_after: Mapped[str] = mapped_column(Text)
    played_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    white_time_seconds: Mapped[int] = mapped_column(Integer)
    black_time_seconds: Mapped[int] = mapped_column(Integer)

    game: Mapped[Game] = relationship(back_populates="moves")
