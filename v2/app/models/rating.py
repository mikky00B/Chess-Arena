from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.game import Game


class RatingUpdate(Base):
    __tablename__ = "rating_updates"
    __table_args__ = (UniqueConstraint("game_id", name="uq_rating_updates_game_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    game_id: Mapped[UUID] = mapped_column(ForeignKey("games.id"), nullable=False)
    white_player_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    black_player_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    white_rating_before: Mapped[int] = mapped_column(Integer)
    black_rating_before: Mapped[int] = mapped_column(Integer)
    white_rating_after: Mapped[int] = mapped_column(Integer)
    black_rating_after: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    game: Mapped[Game] = relationship(back_populates="rating_update")
