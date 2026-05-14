from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.game.state import GameSourceType, TimeControl
from app.models import (
    Game,
    Prize,
    PrizeAssetType,
    PrizeDistribution,
    Tournament,
    TournamentFormat,
    TournamentMatch,
    TournamentParticipant,
    TournamentRound,
    TournamentStatus,
    User,
)
from app.services.game_service import GameService


class TournamentServiceError(ValueError):
    pass


class TournamentNotFoundError(TournamentServiceError):
    pass


class TournamentService:
    def __init__(self, *, game_service: GameService | None = None) -> None:
        self.game_service = game_service or GameService()

    async def create_tournament(
        self,
        session: AsyncSession,
        *,
        organizer_id: UUID,
        name: str,
        description: str | None,
        max_players: int,
        time_control: TimeControl,
        starts_at: datetime | None = None,
        registration_opens_at: datetime | None = None,
        registration_closes_at: datetime | None = None,
        now: datetime | None = None,
    ) -> Tournament:
        organizer = await session.get(User, organizer_id)
        if organizer is None:
            raise TournamentServiceError("organizer must exist")
        if max_players < 2:
            raise TournamentServiceError("tournament requires at least two players")
        created_at = now or datetime.now(UTC)
        tournament = Tournament(
            organizer_id=organizer_id,
            name=name,
            description=description,
            format=TournamentFormat.SINGLE_ELIMINATION,
            status=TournamentStatus.DRAFT,
            max_players=max_players,
            time_control_initial_seconds=time_control.initial_seconds,
            time_control_increment_seconds=time_control.increment_seconds,
            starts_at=starts_at,
            registration_opens_at=registration_opens_at,
            registration_closes_at=registration_closes_at,
            created_at=created_at,
            updated_at=created_at,
        )
        session.add(tournament)
        await session.flush()
        return tournament

    async def open_registration(
        self,
        session: AsyncSession,
        *,
        tournament_id: UUID,
        now: datetime | None = None,
    ) -> Tournament:
        tournament = await self.get_tournament(session, tournament_id=tournament_id)
        if tournament.status != TournamentStatus.DRAFT:
            raise TournamentServiceError("only draft tournaments can open registration")
        tournament.status = TournamentStatus.REGISTRATION_OPEN
        tournament.registration_opens_at = now or datetime.now(UTC)
        tournament.updated_at = tournament.registration_opens_at
        await session.flush()
        return tournament

    async def register_player(
        self,
        session: AsyncSession,
        *,
        tournament_id: UUID,
        user_id: UUID,
        now: datetime | None = None,
    ) -> TournamentParticipant:
        tournament = await self.get_tournament(session, tournament_id=tournament_id)
        if tournament.status != TournamentStatus.REGISTRATION_OPEN:
            raise TournamentServiceError("registration is not open")
        if len(tournament.participants) >= tournament.max_players:
            raise TournamentServiceError("tournament is full")
        if any(participant.user_id == user_id for participant in tournament.participants):
            raise TournamentServiceError("player is already registered")
        user = await session.get(User, user_id)
        if user is None:
            raise TournamentServiceError("user must exist")
        participant = TournamentParticipant(
            tournament_id=tournament.id,
            user_id=user_id,
            seed=len(tournament.participants) + 1,
            eliminated=False,
            registered_at=now or datetime.now(UTC),
        )
        session.add(participant)
        tournament.participants.append(participant)
        await session.flush()
        return participant

    async def close_registration(
        self,
        session: AsyncSession,
        *,
        tournament_id: UUID,
        now: datetime | None = None,
    ) -> Tournament:
        tournament = await self.get_tournament(session, tournament_id=tournament_id)
        if tournament.status != TournamentStatus.REGISTRATION_OPEN:
            raise TournamentServiceError("registration is not open")
        if len(tournament.participants) < 2:
            raise TournamentServiceError("at least two participants are required")
        tournament.status = TournamentStatus.REGISTRATION_CLOSED
        tournament.registration_closes_at = now or datetime.now(UTC)
        tournament.updated_at = tournament.registration_closes_at
        await session.flush()
        return tournament

    async def generate_bracket(
        self,
        session: AsyncSession,
        *,
        tournament_id: UUID,
        now: datetime | None = None,
    ) -> TournamentRound:
        tournament = await self.get_tournament(session, tournament_id=tournament_id)
        if tournament.status != TournamentStatus.REGISTRATION_CLOSED:
            raise TournamentServiceError("registration must be closed before bracket generation")
        if tournament.rounds:
            raise TournamentServiceError("bracket has already been generated")
        if tournament.format != TournamentFormat.SINGLE_ELIMINATION:
            raise TournamentServiceError("only single elimination is implemented")
        if len(tournament.participants) % 2 != 0:
            raise TournamentServiceError(
                "single elimination bracket currently requires even players"
            )

        created_at = now or datetime.now(UTC)
        round_ = TournamentRound(
            tournament_id=tournament.id,
            round_number=1,
            created_at=created_at,
        )
        session.add(round_)
        await session.flush()

        participants = sorted(
            tournament.participants,
            key=lambda participant: participant.seed or 0,
        )
        for index in range(0, len(participants), 2):
            white = participants[index]
            black = participants[index + 1]
            game = await self.create_round_game(
                session,
                tournament=tournament,
                white=white,
                black=black,
                now=created_at,
            )
            match = TournamentMatch(
                tournament_id=tournament.id,
                round_id=round_.id,
                game_id=game.id,
                white_participant_id=white.id,
                black_participant_id=black.id,
                winner_participant_id=None,
                created_at=created_at,
            )
            session.add(match)
            round_.matches.append(match)

        tournament.status = TournamentStatus.IN_PROGRESS
        tournament.updated_at = created_at
        await session.flush()
        return round_

    async def add_prize(
        self,
        session: AsyncSession,
        *,
        tournament_id: UUID,
        rank: int,
        asset_type: PrizeAssetType,
        token_address: str | None = None,
        token_id: str | None = None,
        amount: int | None = None,
        metadata_uri: str | None = None,
        description: str | None = None,
    ) -> Prize:
        tournament = await self.get_tournament(session, tournament_id=tournament_id)
        if rank <= 0:
            raise TournamentServiceError("prize rank must be positive")
        if (
            asset_type in {PrizeAssetType.ERC20, PrizeAssetType.NATIVE, PrizeAssetType.POINTS}
            and (amount is None or amount <= 0)
        ):
            raise TournamentServiceError("token and points prizes require a positive amount")
        if asset_type == PrizeAssetType.NFT and token_id is None:
            raise TournamentServiceError("NFT prizes require a token id")

        prize = Prize(
            tournament_id=tournament.id,
            rank=rank,
            asset_type=asset_type,
            token_address=token_address.lower() if token_address else None,
            token_id=token_id,
            amount=amount,
            metadata_uri=metadata_uri,
            description=description,
        )
        session.add(prize)
        tournament.prizes.append(prize)
        await session.flush()
        return prize

    async def distribute_prizes(
        self,
        session: AsyncSession,
        *,
        tournament_id: UUID,
    ) -> list[PrizeDistribution]:
        tournament = await self.get_tournament(session, tournament_id=tournament_id)
        if tournament.status != TournamentStatus.COMPLETED:
            raise TournamentServiceError("tournament must be completed before prize distribution")
        active_participants = [
            participant for participant in tournament.participants if not participant.eliminated
        ]
        if not active_participants:
            raise TournamentServiceError("no tournament winner is available")
        winner = sorted(active_participants, key=lambda participant: participant.seed or 0)[0]
        distributions: list[PrizeDistribution] = []
        for prize in tournament.prizes:
            if prize.rank != 1:
                continue
            distribution = PrizeDistribution(
                prize_id=prize.id,
                tournament_id=tournament.id,
                user_id=winner.user_id,
                status="PENDING",
                tx_hash=None,
                distributed_at=None,
                created_at=datetime.now(UTC),
            )
            session.add(distribution)
            distributions.append(distribution)
        tournament.status = TournamentStatus.PRIZES_DISTRIBUTED
        await session.flush()
        return distributions

    async def create_round_game(
        self,
        session: AsyncSession,
        *,
        tournament: Tournament,
        white: TournamentParticipant,
        black: TournamentParticipant,
        now: datetime,
    ) -> Game:
        white_user = await session.get(User, white.user_id)
        black_user = await session.get(User, black.user_id)
        if white_user is None or black_user is None:
            raise TournamentServiceError("tournament participants must exist")
        game = self.game_service.build_general_game(
            white_player=white_user,
            black_player=black_user,
            time_control=TimeControl(
                initial_seconds=tournament.time_control_initial_seconds,
                increment_seconds=tournament.time_control_increment_seconds,
            ),
            rated=False,
            now=now,
        )
        game.source_type = GameSourceType.TOURNAMENT_ROUND
        game.source_id = str(tournament.id)
        session.add(game)
        await session.flush()
        return game

    async def get_tournament(self, session: AsyncSession, *, tournament_id: UUID) -> Tournament:
        statement = (
            select(Tournament)
            .where(Tournament.id == tournament_id)
            .options(
                selectinload(Tournament.participants),
                selectinload(Tournament.rounds).selectinload(TournamentRound.matches),
                selectinload(Tournament.prizes),
            )
        )
        tournament = await session.scalar(statement)
        if tournament is None:
            raise TournamentNotFoundError("tournament not found")
        return tournament
