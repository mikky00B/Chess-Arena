from __future__ import annotations

from datetime import datetime

from app.game.engine import ChessEngine
from app.game.state import GameResult, GameState, GameStatus, MoveRecord, PlayerColor, ResultReason
from app.services.clock_service import ClockService


class MoveServiceError(ValueError):
    pass


class MoveService:
    def __init__(
        self,
        *,
        engine: ChessEngine | None = None,
        clock_service: ClockService | None = None,
    ) -> None:
        self.engine = engine or ChessEngine()
        self.clock_service = clock_service or ClockService()

    def submit_move(
        self,
        game: GameState,
        *,
        player_id: str,
        uci: str,
        now: datetime,
    ) -> MoveRecord:
        if game.status != GameStatus.IN_PROGRESS:
            raise MoveServiceError("moves are only accepted for games in progress")
        if game.player_for_turn() != player_id:
            raise MoveServiceError("it is not this player's turn")

        color = game.turn
        self.clock_service.charge_running_clock(game, now=now)
        if self.clock_service.timed_out_color(game) is not None:
            raise MoveServiceError("player clock has expired")

        applied = self.engine.apply_uci_move(game.current_fen, uci)
        self.clock_service.add_increment(game, color=color)

        game.current_fen = applied.fen
        game.turn = applied.turn
        game.draw_offered_by = None
        game.updated_at = now

        if applied.result is not None and applied.reason is not None:
            winner_id = self._winner_id_for_color(game, applied.winner_color)
            game.finish(result=applied.result, reason=applied.reason, winner_id=winner_id, now=now)
        else:
            game.last_clock_started_at = now

        record = MoveRecord(
            move_number=len(game.move_history) + 1,
            player_id=player_id,
            color=color,
            uci=uci,
            san=applied.san,
            fen_after=game.current_fen,
            played_at=now,
            white_time_seconds=game.white_time_seconds,
            black_time_seconds=game.black_time_seconds,
        )
        game.move_history.append(record)
        return record

    def resign(self, game: GameState, *, player_id: str, now: datetime) -> None:
        if game.status != GameStatus.IN_PROGRESS:
            raise MoveServiceError("only games in progress can be resigned")
        loser_color = game.color_for_player(player_id)
        winner_id = game.opponent_of(player_id)
        result = GameResult.BLACK_WIN if loser_color == PlayerColor.WHITE else GameResult.WHITE_WIN
        game.finish(result=result, reason=ResultReason.RESIGNATION, winner_id=winner_id, now=now)

    def offer_draw(self, game: GameState, *, player_id: str) -> None:
        if game.status != GameStatus.IN_PROGRESS:
            raise MoveServiceError("draws can only be offered in games in progress")
        game.color_for_player(player_id)
        game.draw_offered_by = player_id

    def accept_draw(self, game: GameState, *, player_id: str, now: datetime) -> None:
        if game.status != GameStatus.IN_PROGRESS:
            raise MoveServiceError("draws can only be accepted in games in progress")
        if game.draw_offered_by is None:
            raise MoveServiceError("no draw offer is active")
        if game.draw_offered_by == player_id:
            raise MoveServiceError("player cannot accept their own draw offer")
        game.color_for_player(player_id)
        game.finish(
            result=GameResult.DRAW,
            reason=ResultReason.DRAW_AGREEMENT,
            winner_id=None,
            now=now,
        )

    def _winner_id_for_color(self, game: GameState, color: PlayerColor | None) -> str | None:
        if color is None:
            return None
        if color == PlayerColor.WHITE:
            return game.white_player_id
        return game.black_player_id
