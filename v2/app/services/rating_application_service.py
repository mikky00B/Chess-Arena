from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.game.rating import RatingService
from app.game.state import GameResult, GameStatus
from app.models import Game, RatingUpdate


class RatingApplicationError(ValueError):
    pass


class GameNotFoundError(RatingApplicationError):
    pass


class RatingAlreadyAppliedError(RatingApplicationError):
    pass


class PersistentRatingService:
    def __init__(self, *, rating_service: RatingService | None = None) -> None:
        self.rating_service = rating_service or RatingService()

    async def apply_for_game(
        self,
        session: AsyncSession,
        *,
        game_id: UUID,
        now: datetime | None = None,
    ) -> RatingUpdate | None:
        statement = (
            select(Game)
            .where(Game.id == game_id)
            .options(
                selectinload(Game.white_player),
                selectinload(Game.black_player),
                selectinload(Game.rating_update),
            )
            .with_for_update()
        )
        result = await session.execute(statement)
        game = result.scalar_one_or_none()
        if game is None:
            raise GameNotFoundError("game does not exist")

        update = self.apply_to_loaded_game(game, now=now)
        if update is not None:
            session.add(update)
            await session.flush()
        return update

    def apply_to_loaded_game(
        self,
        game: Game,
        *,
        now: datetime | None = None,
    ) -> RatingUpdate | None:
        if not game.rated:
            return None
        if game.status != GameStatus.FINISHED:
            raise RatingApplicationError("ratings can only be applied to finished games")
        if game.result is None:
            raise RatingApplicationError("finished rated game is missing a result")
        if game.result == GameResult.ABORTED:
            return None
        if game.rating_update is not None:
            raise RatingAlreadyAppliedError("ratings have already been applied for this game")

        rating_change = self.rating_service.calculate(
            white_rating=game.white_player.rating,
            black_rating=game.black_player.rating,
            result=game.result,
        )
        game.white_player.rating = rating_change.white_after
        game.black_player.rating = rating_change.black_after

        update = RatingUpdate(
            game_id=game.id,
            white_player_id=game.white_player_id,
            black_player_id=game.black_player_id,
            white_rating_before=rating_change.white_before,
            black_rating_before=rating_change.black_before,
            white_rating_after=rating_change.white_after,
            black_rating_after=rating_change.black_after,
            created_at=now or datetime.now(UTC),
        )
        game.rating_update = update
        return update
