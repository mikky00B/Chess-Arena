from __future__ import annotations

from dataclasses import dataclass

from app.game.state import GameResult


@dataclass(frozen=True, slots=True)
class RatingChange:
    white_before: int
    black_before: int
    white_after: int
    black_after: int
    white_delta: int
    black_delta: int


class RatingService:
    def __init__(self, *, k_factor: int = 32) -> None:
        self.k_factor = k_factor

    def calculate(
        self,
        *,
        white_rating: int,
        black_rating: int,
        result: GameResult,
    ) -> RatingChange:
        white_score, black_score = self._scores_for_result(result)
        white_expected = self._expected_score(white_rating, black_rating)
        black_expected = self._expected_score(black_rating, white_rating)

        white_after = round(white_rating + self.k_factor * (white_score - white_expected))
        black_after = round(black_rating + self.k_factor * (black_score - black_expected))

        return RatingChange(
            white_before=white_rating,
            black_before=black_rating,
            white_after=white_after,
            black_after=black_after,
            white_delta=white_after - white_rating,
            black_delta=black_after - black_rating,
        )

    def _expected_score(self, player_rating: int, opponent_rating: int) -> float:
        return 1 / (1 + 10 ** ((opponent_rating - player_rating) / 400))

    def _scores_for_result(self, result: GameResult) -> tuple[float, float]:
        match result:
            case GameResult.WHITE_WIN:
                return 1.0, 0.0
            case GameResult.BLACK_WIN:
                return 0.0, 1.0
            case GameResult.DRAW:
                return 0.5, 0.5
            case GameResult.ABORTED:
                raise ValueError("aborted games do not change ratings")
