from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.game import Game


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    rating: Mapped[int] = mapped_column(Integer, default=1200)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    white_games: Mapped[list[Game]] = relationship(
        back_populates="white_player",
        foreign_keys="Game.white_player_id",
    )
    black_games: Mapped[list[Game]] = relationship(
        back_populates="black_player",
        foreign_keys="Game.black_player_id",
    )
