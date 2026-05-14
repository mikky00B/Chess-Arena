from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.games import TimeControlRequest
from app.core.database import get_session
from app.models import (
    Prize,
    PrizeAssetType,
    PrizeDistribution,
    Tournament,
    TournamentMatch,
    TournamentParticipant,
    TournamentStatus,
)
from app.services.tournament_service import (
    TournamentNotFoundError,
    TournamentService,
    TournamentServiceError,
)

router = APIRouter(prefix="/api/tournaments", tags=["tournaments"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


class CreateTournamentRequest(BaseModel):
    organizer_id: UUID
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    max_players: int = Field(ge=2)
    time_control: TimeControlRequest
    starts_at: datetime | None = None


class RegisterTournamentRequest(BaseModel):
    user_id: UUID


class TournamentResponse(BaseModel):
    id: UUID
    organizer_id: UUID
    name: str
    description: str | None
    status: TournamentStatus
    max_players: int
    time_control_initial_seconds: int
    time_control_increment_seconds: int
    starts_at: datetime | None
    registration_opens_at: datetime | None
    registration_closes_at: datetime | None
    participant_count: int


class ParticipantResponse(BaseModel):
    id: UUID
    tournament_id: UUID
    user_id: UUID
    seed: int | None
    eliminated: bool
    registered_at: datetime


class TournamentMatchResponse(BaseModel):
    id: UUID
    tournament_id: UUID
    round_id: UUID
    game_id: UUID
    white_participant_id: UUID
    black_participant_id: UUID
    winner_participant_id: UUID | None


class PrizeRequest(BaseModel):
    rank: int = Field(ge=1)
    asset_type: PrizeAssetType
    token_address: str | None = None
    token_id: str | None = None
    amount: int | None = None
    metadata_uri: str | None = None
    description: str | None = None


class PrizeResponse(BaseModel):
    id: UUID
    tournament_id: UUID
    rank: int
    asset_type: PrizeAssetType
    token_address: str | None
    token_id: str | None
    amount: int | None
    metadata_uri: str | None
    description: str | None


class PrizeDistributionResponse(BaseModel):
    id: UUID
    prize_id: UUID
    tournament_id: UUID
    user_id: UUID
    status: str
    tx_hash: str | None
    distributed_at: datetime | None


def get_tournament_service() -> TournamentService:
    return TournamentService()


TournamentServiceDependency = Annotated[TournamentService, Depends(get_tournament_service)]


def serialize_tournament(tournament: Tournament) -> TournamentResponse:
    return TournamentResponse(
        id=tournament.id,
        organizer_id=tournament.organizer_id,
        name=tournament.name,
        description=tournament.description,
        status=tournament.status,
        max_players=tournament.max_players,
        time_control_initial_seconds=tournament.time_control_initial_seconds,
        time_control_increment_seconds=tournament.time_control_increment_seconds,
        starts_at=tournament.starts_at,
        registration_opens_at=tournament.registration_opens_at,
        registration_closes_at=tournament.registration_closes_at,
        participant_count=len(tournament.participants),
    )


def serialize_participant(participant: TournamentParticipant) -> ParticipantResponse:
    return ParticipantResponse(
        id=participant.id,
        tournament_id=participant.tournament_id,
        user_id=participant.user_id,
        seed=participant.seed,
        eliminated=participant.eliminated,
        registered_at=participant.registered_at,
    )


def serialize_match(match: TournamentMatch) -> TournamentMatchResponse:
    return TournamentMatchResponse(
        id=match.id,
        tournament_id=match.tournament_id,
        round_id=match.round_id,
        game_id=match.game_id,
        white_participant_id=match.white_participant_id,
        black_participant_id=match.black_participant_id,
        winner_participant_id=match.winner_participant_id,
    )


def serialize_prize(prize: Prize) -> PrizeResponse:
    return PrizeResponse(
        id=prize.id,
        tournament_id=prize.tournament_id,
        rank=prize.rank,
        asset_type=prize.asset_type,
        token_address=prize.token_address,
        token_id=prize.token_id,
        amount=prize.amount,
        metadata_uri=prize.metadata_uri,
        description=prize.description,
    )


def serialize_distribution(distribution: PrizeDistribution) -> PrizeDistributionResponse:
    return PrizeDistributionResponse(
        id=distribution.id,
        prize_id=distribution.prize_id,
        tournament_id=distribution.tournament_id,
        user_id=distribution.user_id,
        status=distribution.status,
        tx_hash=distribution.tx_hash,
        distributed_at=distribution.distributed_at,
    )


def tournament_error_to_http(exc: Exception) -> HTTPException:
    if isinstance(exc, TournamentNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("", response_model=TournamentResponse, status_code=status.HTTP_201_CREATED)
async def create_tournament(
    request: CreateTournamentRequest,
    session: SessionDependency,
    service: TournamentServiceDependency,
) -> TournamentResponse:
    try:
        tournament = await service.create_tournament(
            session,
            organizer_id=request.organizer_id,
            name=request.name,
            description=request.description,
            max_players=request.max_players,
            time_control=request.time_control.to_domain(),
            starts_at=request.starts_at,
        )
        await session.commit()
        await session.refresh(tournament)
    except TournamentServiceError as exc:
        raise tournament_error_to_http(exc) from exc
    return serialize_tournament(tournament)


@router.get("", response_model=list[TournamentResponse])
async def list_tournaments(session: SessionDependency) -> list[TournamentResponse]:
    tournaments = (await session.scalars(select(Tournament))).all()
    return [serialize_tournament(tournament) for tournament in tournaments]


@router.get("/{tournament_id}", response_model=TournamentResponse)
async def get_tournament(
    tournament_id: UUID,
    session: SessionDependency,
    service: TournamentServiceDependency,
) -> TournamentResponse:
    try:
        tournament = await service.get_tournament(session, tournament_id=tournament_id)
    except TournamentServiceError as exc:
        raise tournament_error_to_http(exc) from exc
    return serialize_tournament(tournament)


@router.post("/{tournament_id}/open-registration", response_model=TournamentResponse)
async def open_registration(
    tournament_id: UUID,
    session: SessionDependency,
    service: TournamentServiceDependency,
) -> TournamentResponse:
    try:
        tournament = await service.open_registration(session, tournament_id=tournament_id)
        await session.commit()
        await session.refresh(tournament)
    except TournamentServiceError as exc:
        raise tournament_error_to_http(exc) from exc
    return serialize_tournament(tournament)


@router.post("/{tournament_id}/register", response_model=ParticipantResponse)
async def register_player(
    tournament_id: UUID,
    request: RegisterTournamentRequest,
    session: SessionDependency,
    service: TournamentServiceDependency,
) -> ParticipantResponse:
    try:
        participant = await service.register_player(
            session,
            tournament_id=tournament_id,
            user_id=request.user_id,
        )
        await session.commit()
        await session.refresh(participant)
    except TournamentServiceError as exc:
        raise tournament_error_to_http(exc) from exc
    return serialize_participant(participant)


@router.post("/{tournament_id}/close-registration", response_model=TournamentResponse)
async def close_registration(
    tournament_id: UUID,
    session: SessionDependency,
    service: TournamentServiceDependency,
) -> TournamentResponse:
    try:
        tournament = await service.close_registration(session, tournament_id=tournament_id)
        await session.commit()
        await session.refresh(tournament)
    except TournamentServiceError as exc:
        raise tournament_error_to_http(exc) from exc
    return serialize_tournament(tournament)


@router.post("/{tournament_id}/generate-bracket", response_model=list[TournamentMatchResponse])
async def generate_bracket(
    tournament_id: UUID,
    session: SessionDependency,
    service: TournamentServiceDependency,
) -> list[TournamentMatchResponse]:
    try:
        round_ = await service.generate_bracket(session, tournament_id=tournament_id)
        await session.commit()
    except TournamentServiceError as exc:
        raise tournament_error_to_http(exc) from exc
    return [serialize_match(match) for match in round_.matches]


@router.get("/{tournament_id}/standings", response_model=list[ParticipantResponse])
async def standings(
    tournament_id: UUID,
    session: SessionDependency,
    service: TournamentServiceDependency,
) -> list[ParticipantResponse]:
    try:
        tournament = await service.get_tournament(session, tournament_id=tournament_id)
    except TournamentServiceError as exc:
        raise tournament_error_to_http(exc) from exc
    participants = sorted(tournament.participants, key=lambda participant: participant.seed or 0)
    return [serialize_participant(participant) for participant in participants]


@router.get("/{tournament_id}/matches", response_model=list[TournamentMatchResponse])
async def matches(
    tournament_id: UUID,
    session: SessionDependency,
    service: TournamentServiceDependency,
) -> list[TournamentMatchResponse]:
    try:
        tournament = await service.get_tournament(session, tournament_id=tournament_id)
    except TournamentServiceError as exc:
        raise tournament_error_to_http(exc) from exc
    return [serialize_match(match) for round_ in tournament.rounds for match in round_.matches]


@router.post("/{tournament_id}/prizes", response_model=PrizeResponse)
async def add_prize(
    tournament_id: UUID,
    request: PrizeRequest,
    session: SessionDependency,
    service: TournamentServiceDependency,
) -> PrizeResponse:
    try:
        prize = await service.add_prize(
            session,
            tournament_id=tournament_id,
            rank=request.rank,
            asset_type=request.asset_type,
            token_address=request.token_address,
            token_id=request.token_id,
            amount=request.amount,
            metadata_uri=request.metadata_uri,
            description=request.description,
        )
        await session.commit()
        await session.refresh(prize)
    except TournamentServiceError as exc:
        raise tournament_error_to_http(exc) from exc
    return serialize_prize(prize)


@router.post(
    "/{tournament_id}/distribute-prizes",
    response_model=list[PrizeDistributionResponse],
)
async def distribute_prizes(
    tournament_id: UUID,
    session: SessionDependency,
    service: TournamentServiceDependency,
) -> list[PrizeDistributionResponse]:
    try:
        distributions = await service.distribute_prizes(session, tournament_id=tournament_id)
        await session.commit()
    except TournamentServiceError as exc:
        raise tournament_error_to_http(exc) from exc
    return [serialize_distribution(distribution) for distribution in distributions]
