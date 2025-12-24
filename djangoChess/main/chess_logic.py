import chess


class ChessGame:
    def __init__(self, fen=None):
        self.board = chess.Board(fen) if fen else chess.Board()

    def get_fen(self):
        return self.board.fen()

    def make_move(self, move_str):
        try:
            # 1. Try UCI (e7e8q)
            # chessboard.js sends source+target. If we added 'q', it's 5 chars.
            move = chess.Move.from_uci(move_str)
            if move in self.board.legal_moves:
                self.board.push(move)
                return True

            # 2. Try SAN Fallback (only if UCI fails)
            move = self.board.parse_san(move_str)
            if move in self.board.legal_moves:
                self.board.push(move)
                return True
        except ValueError:
            return False
        return False

    def get_outcome(self):
        if self.board.is_checkmate():
            return "checkmate"
        if self.board.is_stalemate():
            return "stalemate"
        if self.board.is_insufficient_material():
            return "draw_material"
        if self.board.is_game_over():
            return "draw"
        return None

    def is_game_over(self):
        return self.board.is_game_over()
