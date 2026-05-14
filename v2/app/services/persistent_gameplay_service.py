from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.game.engine import IllegalMoveError
from app.game.state import GameState, MoveRecord, TimeControl
from app.models import Game, Move
from app.services.clock_service import ClockError, ClockService
from app.services.move_service import MoveService, MoveServiceError


class GameplayServiceError(ValueError):
    pass


class GameNotFoundError(GameplayServiceError):
    pass


class ParticipantAuthorizationError(GameplayServiceError):
    pass


@dataclass(frozen=True, slots=True)
class GameplayMoveResult:
    game: Game
    move: Move


class PersistentGameplayService:
    def __init__(
        self,
        *,
        move_service: MoveService | None = None,
        clock_service: ClockService | None = None,
    ) -> None:
        self.clock_service = clock_service or ClockService()
        self.move_service = move_service or MoveService(clock_service=self.clock_service)

    async def get_game(self, session: AsyncSession, *, game_id: UUID) -> Game:
        statement = (
            select(Game)
            .where(Game.id == game_id)
            .options(selectinload(Game.moves))
        )
        game = await session.scalar(statement)
        if game is None:
            raise GameNotFoundError("game not found")
        return game

    def ensure_participant(self, game: Game, *, player_id: UUID) -> None:
        if player_id not in {game.white_player_id, game.black_player_id}:
            raise ParticipantAuthorizationError("player is not a participant in this game")

    async def submit_move(
        self,
        session: AsyncSession,
        *,
        game_id: UUID,
        player_id: UUID,
        uci: str,
        now: datetime | None = None,
    ) -> GameplayMoveResult:
        game = await self.get_game(session, game_id=game_id)
        self.ensure_participant(game, player_id=player_id)
        state = self.to_state(game)
        played_at = now or datetime.now(UTC)
        try:
            move_record = self.move_service.submit_move(
                state,
                player_id=str(player_id),
                uci=uci,
                now=played_at,
            )
        except (IllegalMoveError, MoveServiceError) as exc:
            raise GameplayServiceError(str(exc)) from exc

        self.apply_state(game, state)
        move = self.to_move_model(game_id=game.id, record=move_record)
        session.add(move)
        game.moves.append(move)
        await session.flush()
        return GameplayMoveResult(game=game, move=move)

    async def resign(
        self,
        session: AsyncSession,
        *,
        game_id: UUID,
        player_id: UUID,
        now: datetime | None = None,
    ) -> Game:
        game = await self.get_game(session, game_id=game_id)
        self.ensure_participant(game, player_id=player_id)
        state = self.to_state(game)
        try:
            self.move_service.resign(
                state,
                player_id=str(player_id),
                now=now or datetime.now(UTC),
            )
        except MoveServiceError as exc:
            raise GameplayServiceError(str(exc)) from exc
        self.apply_state(game, state)
        await session.flush()
        return game

    async def offer_draw(self, session: AsyncSession, *, game_id: UUID, player_id: UUID) -> Game:
        game = await self.get_game(session, game_id=game_id)
        self.ensure_participant(game, player_id=player_id)
        state = self.to_state(game)
        try:
            self.move_service.offer_draw(state, player_id=str(player_id))
        except MoveServiceError as exc:
            raise GameplayServiceError(str(exc)) from exc
        self.apply_state(game, state)
        await session.flush()
        return game

    async def accept_draw(
        self,
        session: AsyncSession,
        *,
        game_id: UUID,
        player_id: UUID,
        now: datetime | None = None,
    ) -> Game:
        game = await self.get_game(session, game_id=game_id)
        self.ensure_participant(game, player_id=player_id)
        state = self.to_state(game)
        try:
            self.move_service.accept_draw(
                state,
                player_id=str(player_id),
                now=now or datetime.now(UTC),
            )
        except MoveServiceError as exc:
            raise GameplayServiceError(str(exc)) from exc
        self.apply_state(game, state)
        await session.flush()
        return game

    async def claim_timeout(
        self,
        session: AsyncSession,
        *,
        game_id: UUID,
        player_id: UUID,
        now: datetime | None = None,
    ) -> Game:
        game = await self.get_game(session, game_id=game_id)
        self.ensure_participant(game, player_id=player_id)
        state = self.to_state(game)
        try:
            self.clock_service.claim_timeout(
                state,
                claimant_id=str(player_id),
                now=now or datetime.now(UTC),
            )
        except ClockError as exc:
            raise GameplayServiceError(str(exc)) from exc
        self.apply_state(game, state)
        await session.flush()
        return game

    def to_state(self, game: Game) -> GameState:
        state = GameState(
            id=str(game.id),
            white_player_id=str(game.white_player_id),
            black_player_id=str(game.black_player_id),
            time_control=TimeControl(
                initial_seconds=game.time_control_initial_seconds,
                increment_seconds=game.time_control_increment_seconds,
            ),
            rated=game.rated,
            status=game.status,
            current_fen=game.current_fen,
            white_time_seconds=game.white_time_seconds,
            black_time_seconds=game.black_time_seconds,
            last_clock_started_at=game.last_clock_started_at,
            turn=game.turn,
            result=game.result,
            result_reason=game.result_reason,
            winner_id=str(game.winner_id) if game.winner_id else None,
            source_type=game.source_type,
            source_id=game.source_id,
            draw_offered_by=str(game.draw_offered_by) if game.draw_offered_by else None,
            created_at=game.created_at,
            started_at=game.started_at,
            finished_at=game.finished_at,
            updated_at=game.updated_at,
        )
        state.move_history.extend(
            MoveRecord(
                move_number=move.move_number,
                player_id=str(move.player_id),
                color=move.color,
                uci=move.uci,
                san=move.san,
                fen_after=move.fen_after,
                played_at=move.played_at,
                white_time_seconds=move.white_time_seconds,
                black_time_seconds=move.black_time_seconds,
            )
            for move in game.moves
        )
        return state

    def apply_state(self, game: Game, state: GameState) -> None:
        game.status = state.status
        game.current_fen = state.current_fen
        game.white_time_seconds = state.white_time_seconds
        game.black_time_seconds = state.black_time_seconds
        game.last_clock_started_at = state.last_clock_started_at
        game.turn = state.turn
        game.result = state.result
        game.result_reason = state.result_reason
        game.winner_id = UUID(state.winner_id) if state.winner_id else None
        game.draw_offered_by = UUID(state.draw_offered_by) if state.draw_offered_by else None
        game.started_at = state.started_at
        game.finished_at = state.finished_at
        game.updated_at = state.updated_at

    def to_move_model(self, *, game_id: UUID, record: MoveRecord) -> Move:
        return Move(
            game_id=game_id,
            move_number=record.move_number,
            player_id=UUID(record.player_id),
            color=record.color,
            uci=record.uci,
            san=record.san,
            fen_after=record.fen_after,
            played_at=record.played_at,
            white_time_seconds=record.white_time_seconds,
            black_time_seconds=record.black_time_seconds,
        )
