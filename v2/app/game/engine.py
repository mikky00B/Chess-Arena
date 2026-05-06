from __future__ import annotations

from dataclasses import dataclass

import chess

from app.game.state import GameResult, PlayerColor, ResultReason


class IllegalMoveError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class EngineResult:
    fen: str
    san: str
    turn: PlayerColor
    result: GameResult | None = None
    reason: ResultReason | None = None
    winner_color: PlayerColor | None = None


class ChessEngine:
    def apply_uci_move(self, fen: str, uci: str) -> EngineResult:
        board = chess.Board(fen)

        try:
            move = chess.Move.from_uci(uci)
        except ValueError as exc:
            raise IllegalMoveError(f"invalid UCI move: {uci}") from exc

        if move not in board.legal_moves:
            raise IllegalMoveError(f"illegal move: {uci}")

        mover = PlayerColor.WHITE if board.turn == chess.WHITE else PlayerColor.BLACK
        san = board.san(move)
        board.push(move)

        result: GameResult | None = None
        reason: ResultReason | None = None
        winner_color: PlayerColor | None = None

        if board.is_checkmate():
            winner_color = mover
            result = GameResult.WHITE_WIN if mover == PlayerColor.WHITE else GameResult.BLACK_WIN
            reason = ResultReason.CHECKMATE
        elif board.is_stalemate():
            result = GameResult.DRAW
            reason = ResultReason.STALEMATE
        elif board.is_insufficient_material():
            result = GameResult.DRAW
            reason = ResultReason.INSUFFICIENT_MATERIAL
        elif board.can_claim_threefold_repetition():
            result = GameResult.DRAW
            reason = ResultReason.THREEFOLD_REPETITION
        elif board.can_claim_fifty_moves():
            result = GameResult.DRAW
            reason = ResultReason.FIFTY_MOVE_RULE

        next_turn = PlayerColor.WHITE if board.turn == chess.WHITE else PlayerColor.BLACK
        return EngineResult(
            fen=board.fen(),
            san=san,
            turn=next_turn,
            result=result,
            reason=reason,
            winner_color=winner_color,
        )
