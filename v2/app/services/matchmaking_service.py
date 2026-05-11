from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.game.state import TimeControl
from app.models import Game, User
from app.services.game_service import GameService, GameServiceError


class MatchmakingError(ValueError):
    pass


class PlayerAlreadyQueuedError(MatchmakingError):
    pass


@dataclass(frozen=True, slots=True)
class MatchmakingTicket:
    player: User
    time_control: TimeControl
    rated: bool
    queued_at: datetime


@dataclass(frozen=True, slots=True)
class MatchmakingResult:
    ticket: MatchmakingTicket | None
    game: Game | None

    @property
    def matched(self) -> bool:
        return self.game is not None


class MatchmakingService:
    def __init__(self, *, game_service: GameService | None = None) -> None:
        self.game_service = game_service or GameService()
        self._tickets_by_player: dict[UUID, MatchmakingTicket] = {}
        self._queue: list[MatchmakingTicket] = []

    def queue_player(
        self,
        *,
        player: User,
        time_control: TimeControl,
        rated: bool = False,
        now: datetime | None = None,
    ) -> MatchmakingResult:
        if player.id in self._tickets_by_player:
            raise PlayerAlreadyQueuedError("player is already queued")

        ticket = MatchmakingTicket(
            player=player,
            time_control=time_control,
            rated=rated,
            queued_at=now or datetime.now(UTC),
        )
        opponent_ticket = self._pop_compatible_ticket(ticket)
        if opponent_ticket is None:
            self._queue.append(ticket)
            self._tickets_by_player[player.id] = ticket
            return MatchmakingResult(ticket=ticket, game=None)

        game = self.game_service.build_general_game(
            white_player=opponent_ticket.player,
            black_player=ticket.player,
            time_control=ticket.time_control,
            rated=ticket.rated,
            now=ticket.queued_at,
        )
        return MatchmakingResult(ticket=None, game=game)

    def cancel_queue(self, *, player_id: UUID) -> MatchmakingTicket | None:
        ticket = self._tickets_by_player.pop(player_id, None)
        if ticket is None:
            return None
        self._queue = [
            queued_ticket for queued_ticket in self._queue if queued_ticket is not ticket
        ]
        return ticket

    def get_ticket(self, *, player_id: UUID) -> MatchmakingTicket | None:
        return self._tickets_by_player.get(player_id)

    def _pop_compatible_ticket(self, ticket: MatchmakingTicket) -> MatchmakingTicket | None:
        for index, queued_ticket in enumerate(self._queue):
            if queued_ticket.player.id == ticket.player.id:
                raise GameServiceError("players must be different")
            if not self._is_compatible(queued_ticket, ticket):
                continue

            self._queue.pop(index)
            self._tickets_by_player.pop(queued_ticket.player.id, None)
            return queued_ticket
        return None

    def _is_compatible(
        self,
        queued_ticket: MatchmakingTicket,
        ticket: MatchmakingTicket,
    ) -> bool:
        return (
            queued_ticket.rated == ticket.rated
            and queued_ticket.time_control.initial_seconds == ticket.time_control.initial_seconds
            and queued_ticket.time_control.increment_seconds
            == ticket.time_control.increment_seconds
        )
