from __future__ import annotations

import hmac
import secrets
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

import chess
from sqlalchemy.ext.asyncio import AsyncSession

from app.game.state import GameSourceType, GameStatus, PlayerColor, TimeControl
from app.models import Game, User
from app.services.clock_service import ClockService


class GameServiceError(ValueError):
    pass


class UserNotFoundError(GameServiceError):
    pass


class PrivateInviteError(GameServiceError):
    pass


class GameService:
    def __init__(self, *, clock_service: ClockService | None = None) -> None:
        self.clock_service = clock_service or ClockService()

    async def create_general_game(
        self,
        session: AsyncSession,
        *,
        white_player_id: UUID,
        black_player_id: UUID,
        time_control: TimeControl,
        rated: bool = False,
        private: bool = False,
        invite_token: str | None = None,
        now: datetime | None = None,
    ) -> Game:
        white_player = await session.get(User, white_player_id)
        black_player = await session.get(User, black_player_id)
        if white_player is None or black_player is None:
            raise UserNotFoundError("both players must exist")

        game = self.build_general_game(
            white_player=white_player,
            black_player=black_player,
            time_control=time_control,
            rated=rated,
            private=private,
            invite_token=invite_token,
            now=now,
        )
        session.add(game)
        await session.flush()
        return game

    def build_general_game(
        self,
        *,
        white_player: User,
        black_player: User,
        time_control: TimeControl,
        rated: bool = False,
        private: bool = False,
        invite_token: str | None = None,
        now: datetime | None = None,
    ) -> Game:
        if white_player.id == black_player.id:
            raise GameServiceError("players must be different")

        created_at = now or datetime.now(UTC)
        source_type = (
            GameSourceType.PRIVATE_GENERAL_GAME if private else GameSourceType.GENERAL_MATCHMAKING
        )
        source_id = self.hash_invite_token(invite_token) if private and invite_token else None
        return Game(
            white_player_id=white_player.id,
            black_player_id=black_player.id,
            status=GameStatus.READY,
            current_fen=chess.STARTING_FEN,
            time_control_initial_seconds=time_control.initial_seconds,
            time_control_increment_seconds=time_control.increment_seconds,
            white_time_seconds=time_control.initial_seconds,
            black_time_seconds=time_control.initial_seconds,
            last_clock_started_at=None,
            turn=PlayerColor.WHITE,
            rated=rated,
            result=None,
            result_reason=None,
            winner_id=None,
            source_type=source_type,
            source_id=source_id,
            draw_offered_by=None,
            created_at=created_at,
            started_at=None,
            finished_at=None,
            updated_at=created_at,
            white_player=white_player,
            black_player=black_player,
        )

    def create_private_invite_token(
        self,
        *,
        token_factory: Callable[[int], str] = secrets.token_urlsafe,
    ) -> str:
        return token_factory(32)

    def hash_invite_token(self, invite_token: str) -> str:
        if not invite_token:
            raise PrivateInviteError("invite token is required")
        return sha256(invite_token.encode("utf-8")).hexdigest()

    def validate_private_invite(self, game: Game, *, invite_token: str | None) -> None:
        if game.source_type != GameSourceType.PRIVATE_GENERAL_GAME:
            return
        if game.source_id is None:
            raise PrivateInviteError("private game has no invite token")
        if invite_token is None:
            raise PrivateInviteError("private invite token is required")

        expected = game.source_id
        actual = self.hash_invite_token(invite_token)
        if not hmac.compare_digest(expected, actual):
            raise PrivateInviteError("private invite token is invalid")

    def start_general_game(self, game: Game, *, now: datetime | None = None) -> None:
        if game.source_type not in {
            GameSourceType.GENERAL_MATCHMAKING,
            GameSourceType.PRIVATE_GENERAL_GAME,
        }:
            raise GameServiceError("only general games can be started by this service")
        if game.status != GameStatus.READY:
            raise GameServiceError("only ready games can be started")

        started_at = now or datetime.now(UTC)
        game.status = GameStatus.IN_PROGRESS
        game.started_at = started_at
        game.last_clock_started_at = started_at
        game.updated_at = started_at
