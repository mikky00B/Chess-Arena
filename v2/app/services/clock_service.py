from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.game.state import GameResult, GameState, GameStatus, PlayerColor, ResultReason


class ClockError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ClockSnapshot:
    white_time_seconds: int
    black_time_seconds: int


class ClockService:
    def start(self, game: GameState, *, now: datetime) -> None:
        if game.status != GameStatus.READY:
            raise ClockError("only ready games can be started")
        game.status = GameStatus.IN_PROGRESS
        game.started_at = now
        game.last_clock_started_at = now
        game.updated_at = now

    def charge_running_clock(self, game: GameState, *, now: datetime) -> None:
        if game.status != GameStatus.IN_PROGRESS or game.last_clock_started_at is None:
            return

        elapsed = max(0, int((now - game.last_clock_started_at).total_seconds()))
        if game.turn == PlayerColor.WHITE:
            game.white_time_seconds = max(0, game.white_time_seconds - elapsed)
        else:
            game.black_time_seconds = max(0, game.black_time_seconds - elapsed)
        game.last_clock_started_at = now
        game.updated_at = now

    def add_increment(self, game: GameState, *, color: PlayerColor) -> None:
        if game.time_control.increment_seconds == 0:
            return
        if color == PlayerColor.WHITE:
            game.white_time_seconds += game.time_control.increment_seconds
        else:
            game.black_time_seconds += game.time_control.increment_seconds

    def snapshot(self, game: GameState, *, now: datetime) -> ClockSnapshot:
        white = game.white_time_seconds
        black = game.black_time_seconds
        if game.status == GameStatus.IN_PROGRESS and game.last_clock_started_at is not None:
            elapsed = max(0, int((now - game.last_clock_started_at).total_seconds()))
            if game.turn == PlayerColor.WHITE:
                white = max(0, white - elapsed)
            else:
                black = max(0, black - elapsed)
        return ClockSnapshot(white_time_seconds=white, black_time_seconds=black)

    def claim_timeout(self, game: GameState, *, claimant_id: str, now: datetime) -> None:
        if game.status != GameStatus.IN_PROGRESS:
            raise ClockError("timeouts can only be claimed for games in progress")
        if claimant_id not in {game.white_player_id, game.black_player_id}:
            raise ClockError("claimant is not a participant")

        self.charge_running_clock(game, now=now)
        timed_out_color = self.timed_out_color(game)
        if timed_out_color is None:
            raise ClockError("no player has timed out")

        winner_id = (
            game.black_player_id if timed_out_color == PlayerColor.WHITE else game.white_player_id
        )
        result = (
            GameResult.BLACK_WIN
            if timed_out_color == PlayerColor.WHITE
            else GameResult.WHITE_WIN
        )
        game.finish(result=result, reason=ResultReason.TIMEOUT, winner_id=winner_id, now=now)

    def timed_out_color(self, game: GameState) -> PlayerColor | None:
        if game.white_time_seconds <= 0:
            return PlayerColor.WHITE
        if game.black_time_seconds <= 0:
            return PlayerColor.BLACK
        return None
