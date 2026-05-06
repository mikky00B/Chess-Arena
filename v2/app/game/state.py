from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

import chess


class PlayerColor(StrEnum):
    WHITE = "WHITE"
    BLACK = "BLACK"


class GameStatus(StrEnum):
    WAITING_FOR_PLAYERS = "WAITING_FOR_PLAYERS"
    READY = "READY"
    IN_PROGRESS = "IN_PROGRESS"
    PAUSED = "PAUSED"
    FINISHED = "FINISHED"
    ABORTED = "ABORTED"


class GameResult(StrEnum):
    WHITE_WIN = "WHITE_WIN"
    BLACK_WIN = "BLACK_WIN"
    DRAW = "DRAW"
    ABORTED = "ABORTED"


class ResultReason(StrEnum):
    CHECKMATE = "CHECKMATE"
    RESIGNATION = "RESIGNATION"
    TIMEOUT = "TIMEOUT"
    STALEMATE = "STALEMATE"
    INSUFFICIENT_MATERIAL = "INSUFFICIENT_MATERIAL"
    THREEFOLD_REPETITION = "THREEFOLD_REPETITION"
    FIFTY_MOVE_RULE = "FIFTY_MOVE_RULE"
    DRAW_AGREEMENT = "DRAW_AGREEMENT"
    ABANDONMENT = "ABANDONMENT"
    ADMIN_ADJUDICATION = "ADMIN_ADJUDICATION"


class GameSourceType(StrEnum):
    GENERAL_MATCHMAKING = "GENERAL_MATCHMAKING"
    PRIVATE_GENERAL_GAME = "PRIVATE_GENERAL_GAME"
    CHALLENGE = "CHALLENGE"
    TOURNAMENT_ROUND = "TOURNAMENT_ROUND"


@dataclass(slots=True)
class TimeControl:
    initial_seconds: int
    increment_seconds: int = 0

    def __post_init__(self) -> None:
        if self.initial_seconds <= 0:
            raise ValueError("initial_seconds must be positive")
        if self.increment_seconds < 0:
            raise ValueError("increment_seconds cannot be negative")


@dataclass(slots=True)
class MoveRecord:
    move_number: int
    player_id: str
    color: PlayerColor
    uci: str
    san: str
    fen_after: str
    played_at: datetime
    white_time_seconds: int
    black_time_seconds: int


@dataclass(slots=True)
class GameState:
    id: str
    white_player_id: str
    black_player_id: str
    time_control: TimeControl
    rated: bool = False
    status: GameStatus = GameStatus.READY
    current_fen: str = chess.STARTING_FEN
    white_time_seconds: int = 0
    black_time_seconds: int = 0
    last_clock_started_at: datetime | None = None
    turn: PlayerColor = PlayerColor.WHITE
    result: GameResult | None = None
    result_reason: ResultReason | None = None
    winner_id: str | None = None
    source_type: GameSourceType = GameSourceType.GENERAL_MATCHMAKING
    source_id: str | None = None
    draw_offered_by: str | None = None
    move_history: list[MoveRecord] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    finished_at: datetime | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if self.white_player_id == self.black_player_id:
            raise ValueError("players must be different")
        if self.white_time_seconds == 0:
            self.white_time_seconds = self.time_control.initial_seconds
        if self.black_time_seconds == 0:
            self.black_time_seconds = self.time_control.initial_seconds

    def player_for_turn(self) -> str:
        if self.turn == PlayerColor.WHITE:
            return self.white_player_id
        return self.black_player_id

    def color_for_player(self, player_id: str) -> PlayerColor:
        if player_id == self.white_player_id:
            return PlayerColor.WHITE
        if player_id == self.black_player_id:
            return PlayerColor.BLACK
        raise ValueError("player is not a participant in this game")

    def opponent_of(self, player_id: str) -> str:
        if player_id == self.white_player_id:
            return self.black_player_id
        if player_id == self.black_player_id:
            return self.white_player_id
        raise ValueError("player is not a participant in this game")

    def finish(
        self,
        *,
        result: GameResult,
        reason: ResultReason,
        winner_id: str | None,
        now: datetime,
    ) -> None:
        self.status = GameStatus.FINISHED
        self.result = result
        self.result_reason = reason
        self.winner_id = winner_id
        self.finished_at = now
        self.last_clock_started_at = None
        self.updated_at = now
