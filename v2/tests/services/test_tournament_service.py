from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.game.state import GameSourceType, TimeControl
from app.models import (
    PrizeAssetType,
    Tournament,
    TournamentFormat,
    TournamentParticipant,
    TournamentStatus,
    User,
)
from app.services.tournament_service import TournamentService, TournamentServiceError


class FakeSession:
    def __init__(self) -> None:
        self.users: dict[object, User] = {}
        self.added: list[object] = []

    async def get(self, model: type[object], entity_id: object) -> object | None:
        if model is User:
            return self.users.get(entity_id)
        return None

    def add(self, entity: object) -> None:
        self.added.append(entity)

    async def flush(self) -> None:
        return None


def make_user(username: str) -> User:
    return User(id=uuid4(), username=username, rating=1200, created_at=datetime.now(UTC))


def make_tournament() -> Tournament:
    return Tournament(
        id=uuid4(),
        organizer_id=uuid4(),
        name="Arena",
        description=None,
        format=TournamentFormat.SINGLE_ELIMINATION,
        status=TournamentStatus.REGISTRATION_CLOSED,
        max_players=4,
        time_control_initial_seconds=300,
        time_control_increment_seconds=2,
        starts_at=None,
        registration_opens_at=datetime.now(UTC),
        registration_closes_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


async def test_register_player_requires_open_registration_and_prevents_duplicates() -> None:
    service = TournamentService()
    session = FakeSession()
    user = make_user("player")
    session.users[user.id] = user
    tournament = make_tournament()
    tournament.status = TournamentStatus.REGISTRATION_OPEN

    async def get_tournament(*_args: object, **_kwargs: object) -> Tournament:
        return tournament

    service.get_tournament = get_tournament  # type: ignore[method-assign]

    participant = await service.register_player(
        session,
        tournament_id=tournament.id,
        user_id=user.id,
    )

    assert participant.seed == 1
    with pytest.raises(TournamentServiceError, match="already registered"):
        await service.register_player(session, tournament_id=tournament.id, user_id=user.id)


async def test_generate_bracket_creates_tournament_round_games() -> None:
    service = TournamentService()
    session = FakeSession()
    tournament = make_tournament()
    users = [make_user(f"p{i}") for i in range(4)]
    for user in users:
        session.users[user.id] = user
    tournament.participants.extend(
        [
            TournamentParticipant(
                id=uuid4(),
                tournament_id=tournament.id,
                user_id=user.id,
                seed=index + 1,
                eliminated=False,
                registered_at=datetime.now(UTC),
            )
            for index, user in enumerate(users)
        ]
    )

    async def get_tournament(*_args: object, **_kwargs: object) -> Tournament:
        return tournament

    service.get_tournament = get_tournament  # type: ignore[method-assign]

    round_ = await service.generate_bracket(session, tournament_id=tournament.id)

    assert tournament.status == TournamentStatus.IN_PROGRESS
    assert len(round_.matches) == 2
    games = [entity for entity in session.added if getattr(entity, "source_type", None)]
    assert all(game.source_type == GameSourceType.TOURNAMENT_ROUND for game in games)


async def test_create_tournament_uses_single_elimination() -> None:
    service = TournamentService()
    session = FakeSession()
    organizer = make_user("organizer")
    session.users[organizer.id] = organizer

    tournament = await service.create_tournament(
        session,
        organizer_id=organizer.id,
        name="Arena",
        description=None,
        max_players=8,
        time_control=TimeControl(initial_seconds=600),
    )

    assert tournament.format == TournamentFormat.SINGLE_ELIMINATION
    assert tournament.status == TournamentStatus.DRAFT


async def test_add_and_distribute_rank_one_prize_to_winner() -> None:
    service = TournamentService()
    session = FakeSession()
    tournament = make_tournament()
    tournament.status = TournamentStatus.DRAFT
    winner_user = make_user("winner")
    session.users[winner_user.id] = winner_user
    tournament.participants.append(
        TournamentParticipant(
            id=uuid4(),
            tournament_id=tournament.id,
            user_id=winner_user.id,
            seed=1,
            eliminated=False,
            registered_at=datetime.now(UTC),
        )
    )

    async def get_tournament(*_args: object, **_kwargs: object) -> Tournament:
        return tournament

    service.get_tournament = get_tournament  # type: ignore[method-assign]

    prize = await service.add_prize(
        session,
        tournament_id=tournament.id,
        rank=1,
        asset_type=PrizeAssetType.POINTS,
        amount=100,
    )
    prize.id = uuid4()
    tournament.prizes = [prize]
    tournament.status = TournamentStatus.COMPLETED

    distributions = await service.distribute_prizes(session, tournament_id=tournament.id)

    assert distributions[0].user_id == winner_user.id
    assert distributions[0].prize_id == prize.id
    assert tournament.status == TournamentStatus.PRIZES_DISTRIBUTED
