import pytest

from app.game.engine import ChessEngine, IllegalMoveError
from app.game.state import GameResult, PlayerColor, ResultReason


def test_engine_applies_legal_move_and_updates_turn() -> None:
    result = ChessEngine().apply_uci_move(
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "e2e4",
    )

    assert result.san == "e4"
    assert result.turn == PlayerColor.BLACK
    assert result.result is None


def test_engine_rejects_illegal_move() -> None:
    with pytest.raises(IllegalMoveError):
        ChessEngine().apply_uci_move(
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "e2e5",
        )


def test_engine_detects_checkmate() -> None:
    engine = ChessEngine()
    result = engine.apply_uci_move(
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "f2f3",
    )
    result = engine.apply_uci_move(result.fen, "e7e5")
    result = engine.apply_uci_move(result.fen, "g2g4")
    result = engine.apply_uci_move(result.fen, "d8h4")

    assert result.result == GameResult.BLACK_WIN
    assert result.reason == ResultReason.CHECKMATE
    assert result.winner_color == PlayerColor.BLACK
