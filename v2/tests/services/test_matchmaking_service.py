from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.game.state import GameSourceType, TimeControl
from app.models import User
from app.services.matchmaking_service import MatchmakingService, PlayerAlreadyQueuedError


def make_user(username: str) -> User:
    return User(id=uuid4(), username=username, rating=1200, created_at=datetime.now(UTC))


def test_queue_player_waits_when_no_compatible_opponent_exists() -> None:
    player = make_user("player")
    time_control = TimeControl(initial_seconds=300, increment_seconds=2)
    result = MatchmakingService().queue_player(
        player=player,
        time_control=time_control,
        rated=True,
    )

    assert result.matched is False
    assert result.ticket is not None
    assert result.ticket.player is player
    assert result.ticket.time_control == time_control
    assert result.ticket.rated is True


def test_queue_player_matches_compatible_opponent_into_general_game() -> None:
    service = MatchmakingService()
    white = make_user("white")
    black = make_user("black")
    now = datetime(2026, 5, 6, 12, 0, tzinfo=UTC)
    time_control = TimeControl(initial_seconds=300, increment_seconds=2)

    first_result = service.queue_player(
        player=white,
        time_control=time_control,
        rated=True,
        now=now,
    )
    second_result = service.queue_player(
        player=black,
        time_control=time_control,
        rated=True,
        now=now,
    )

    assert first_result.matched is False
    assert second_result.matched is True
    assert second_result.game is not None
    assert second_result.game.white_player is white
    assert second_result.game.black_player is black
    assert second_result.game.source_type == GameSourceType.GENERAL_MATCHMAKING
    assert second_result.game.rated is True
    assert service.get_ticket(player_id=white.id) is None
    assert service.get_ticket(player_id=black.id) is None


def test_queue_player_does_not_match_different_rated_mode() -> None:
    service = MatchmakingService()
    casual = make_user("casual")
    rated = make_user("rated")
    time_control = TimeControl(initial_seconds=300)

    service.queue_player(player=casual, time_control=time_control, rated=False)
    result = service.queue_player(player=rated, time_control=time_control, rated=True)

    assert result.matched is False
    assert service.get_ticket(player_id=casual.id) is not None
    assert service.get_ticket(player_id=rated.id) is not None


def test_queue_player_rejects_duplicate_active_ticket() -> None:
    service = MatchmakingService()
    player = make_user("player")
    time_control = TimeControl(initial_seconds=300)

    service.queue_player(player=player, time_control=time_control)

    with pytest.raises(PlayerAlreadyQueuedError, match="already queued"):
        service.queue_player(player=player, time_control=time_control)


def test_cancel_queue_removes_active_ticket() -> None:
    service = MatchmakingService()
    player = make_user("player")
    time_control = TimeControl(initial_seconds=300)

    queued = service.queue_player(player=player, time_control=time_control)
    canceled = service.cancel_queue(player_id=player.id)

    assert canceled == queued.ticket
    assert service.get_ticket(player_id=player.id) is None
