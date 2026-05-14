from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.game.state import (
    GameResult,
    GameSourceType,
    GameStatus,
    PlayerColor,
    ResultReason,
    TimeControl,
)
from app.models import Game, Move, SecurityEventSeverity
from app.services.game_service import (
    GameService,
    GameServiceError,
    PrivateInviteError,
    UserNotFoundError,
)
from app.services.persistent_gameplay_service import (
    GameNotFoundError,
    GameplayServiceError,
    ParticipantAuthorizationError,
    PersistentGameplayService,
)
from app.services.security_service import SecurityService

router = APIRouter(prefix="/api/games", tags=["games"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


class TimeControlRequest(BaseModel):
    initial_seconds: int = Field(gt=0)
    increment_seconds: int = Field(default=0, ge=0)

    def to_domain(self) -> TimeControl:
        return TimeControl(
            initial_seconds=self.initial_seconds,
            increment_seconds=self.increment_seconds,
        )


class GameResponse(BaseModel):
    id: UUID
    white_player_id: UUID
    black_player_id: UUID
    status: GameStatus
    current_fen: str
    time_control_initial_seconds: int
    time_control_increment_seconds: int
    white_time_seconds: int
    black_time_seconds: int
    last_clock_started_at: datetime | None
    turn: PlayerColor
    rated: bool
    result: GameResult | None
    result_reason: ResultReason | None
    winner_id: UUID | None
    source_type: GameSourceType
    draw_offered_by: UUID | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    updated_at: datetime


class MoveResponse(BaseModel):
    id: UUID
    game_id: UUID
    move_number: int
    player_id: UUID
    color: PlayerColor
    uci: str
    san: str
    fen_after: str
    played_at: datetime
    white_time_seconds: int
    black_time_seconds: int


class CreateGameRequest(BaseModel):
    white_player_id: UUID
    black_player_id: UUID
    time_control: TimeControlRequest
    rated: bool = False
    private: bool = False


class CreateGameResponse(BaseModel):
    game: GameResponse
    invite_token: str | None = None


class StartGameRequest(BaseModel):
    player_id: UUID


class SubmitMoveRequest(BaseModel):
    player_id: UUID
    uci: str = Field(min_length=4, max_length=8)


class PlayerActionRequest(BaseModel):
    player_id: UUID


class SubmitMoveResponse(BaseModel):
    game: GameResponse
    move: MoveResponse


def get_game_service() -> GameService:
    return GameService()


def get_gameplay_service() -> PersistentGameplayService:
    return PersistentGameplayService()


def get_security_service() -> SecurityService:
    return SecurityService()


GameServiceDependency = Annotated[GameService, Depends(get_game_service)]
GameplayServiceDependency = Annotated[PersistentGameplayService, Depends(get_gameplay_service)]
SecurityServiceDependency = Annotated[SecurityService, Depends(get_security_service)]


def serialize_game(game: Game) -> GameResponse:
    return GameResponse(
        id=game.id,
        white_player_id=game.white_player_id,
        black_player_id=game.black_player_id,
        status=game.status,
        current_fen=game.current_fen,
        time_control_initial_seconds=game.time_control_initial_seconds,
        time_control_increment_seconds=game.time_control_increment_seconds,
        white_time_seconds=game.white_time_seconds,
        black_time_seconds=game.black_time_seconds,
        last_clock_started_at=game.last_clock_started_at,
        turn=game.turn,
        rated=game.rated,
        result=game.result,
        result_reason=game.result_reason,
        winner_id=game.winner_id,
        source_type=game.source_type,
        draw_offered_by=game.draw_offered_by,
        created_at=game.created_at,
        started_at=game.started_at,
        finished_at=game.finished_at,
        updated_at=game.updated_at,
    )


def serialize_move(move: Move) -> MoveResponse:
    return MoveResponse(
        id=move.id,
        game_id=move.game_id,
        move_number=move.move_number,
        player_id=move.player_id,
        color=move.color,
        uci=move.uci,
        san=move.san,
        fen_after=move.fen_after,
        played_at=move.played_at,
        white_time_seconds=move.white_time_seconds,
        black_time_seconds=move.black_time_seconds,
    )


def gameplay_error_to_http(exc: Exception) -> HTTPException:
    if isinstance(exc, GameNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ParticipantAuthorizationError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


async def validate_private_game_access(
    *,
    session: AsyncSession,
    game_id: UUID,
    game_service: GameService,
    gameplay_service: PersistentGameplayService,
    invite_token: str | None,
) -> None:
    try:
        game = await gameplay_service.get_game(session, game_id=game_id)
        game_service.validate_private_invite(game, invite_token=invite_token)
    except PrivateInviteError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except GameNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("", response_model=CreateGameResponse, status_code=status.HTTP_201_CREATED)
async def create_game(
    http_request: Request,
    request: CreateGameRequest,
    session: SessionDependency,
    game_service: GameServiceDependency,
    security_service: SecurityServiceDependency,
) -> CreateGameResponse:
    invite_token = game_service.create_private_invite_token() if request.private else None
    try:
        game = await game_service.create_general_game(
            session,
            white_player_id=request.white_player_id,
            black_player_id=request.black_player_id,
            time_control=request.time_control.to_domain(),
            rated=request.rated,
            private=request.private,
            invite_token=invite_token,
        )
        await session.commit()
        await session.refresh(game)
        if request.private:
            await security_service.log_request_event(
                session,
                http_request,
                event_type="private_game_created",
                user_id=request.white_player_id,
                resource_type="game",
                resource_id=str(game.id),
                metadata={"black_player_id": str(request.black_player_id)},
            )
            await session.commit()
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except GameServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return CreateGameResponse(game=serialize_game(game), invite_token=invite_token)


@router.get("/{game_id}", response_model=GameResponse)
async def get_game(
    game_id: UUID,
    session: SessionDependency,
    game_service: GameServiceDependency,
    invite_token: str | None = Query(default=None),
) -> GameResponse:
    game = await session.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="game not found")

    try:
        game_service.validate_private_invite(game, invite_token=invite_token)
    except PrivateInviteError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return serialize_game(game)


@router.post("/{game_id}/start", response_model=GameResponse)
async def start_game(
    http_request: Request,
    game_id: UUID,
    request: StartGameRequest,
    session: SessionDependency,
    game_service: GameServiceDependency,
    gameplay_service: GameplayServiceDependency,
    security_service: SecurityServiceDependency,
    invite_token: str | None = Query(default=None),
) -> GameResponse:
    game = await session.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="game not found")

    try:
        game_service.validate_private_invite(game, invite_token=invite_token)
        gameplay_service.ensure_participant(game, player_id=request.player_id)
        game_service.start_general_game(game)
        await session.commit()
        await session.refresh(game)
    except PrivateInviteError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ParticipantAuthorizationError as exc:
        await security_service.log_request_event(
            session,
            http_request,
            event_type="game_action_forbidden",
            severity=SecurityEventSeverity.WARNING,
            user_id=request.player_id,
            resource_type="game",
            resource_id=str(game_id),
            metadata={"action": "start"},
        )
        await session.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except GameServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return serialize_game(game)


@router.post("/{game_id}/moves", response_model=SubmitMoveResponse)
async def submit_move(
    http_request: Request,
    game_id: UUID,
    request: SubmitMoveRequest,
    session: SessionDependency,
    game_service: GameServiceDependency,
    gameplay_service: GameplayServiceDependency,
    security_service: SecurityServiceDependency,
    invite_token: str | None = Query(default=None),
) -> SubmitMoveResponse:
    try:
        await validate_private_game_access(
            session=session,
            game_id=game_id,
            game_service=game_service,
            gameplay_service=gameplay_service,
            invite_token=invite_token,
        )
        result = await gameplay_service.submit_move(
            session,
            game_id=game_id,
            player_id=request.player_id,
            uci=request.uci,
        )
        await session.commit()
        await session.refresh(result.game)
        await session.refresh(result.move)
    except GameplayServiceError as exc:
        if isinstance(exc, ParticipantAuthorizationError):
            await security_service.log_request_event(
                session,
                http_request,
                event_type="game_action_forbidden",
                severity=SecurityEventSeverity.WARNING,
                user_id=request.player_id,
                resource_type="game",
                resource_id=str(game_id),
                metadata={"action": "move"},
            )
            await session.commit()
        raise gameplay_error_to_http(exc) from exc

    return SubmitMoveResponse(game=serialize_game(result.game), move=serialize_move(result.move))


@router.post("/{game_id}/resign", response_model=GameResponse)
async def resign_game(
    game_id: UUID,
    request: PlayerActionRequest,
    session: SessionDependency,
    game_service: GameServiceDependency,
    gameplay_service: GameplayServiceDependency,
    invite_token: str | None = Query(default=None),
) -> GameResponse:
    try:
        await validate_private_game_access(
            session=session,
            game_id=game_id,
            game_service=game_service,
            gameplay_service=gameplay_service,
            invite_token=invite_token,
        )
        game = await gameplay_service.resign(
            session,
            game_id=game_id,
            player_id=request.player_id,
        )
        await session.commit()
        await session.refresh(game)
    except GameplayServiceError as exc:
        raise gameplay_error_to_http(exc) from exc

    return serialize_game(game)


@router.post("/{game_id}/draw-offer", response_model=GameResponse)
async def offer_draw(
    game_id: UUID,
    request: PlayerActionRequest,
    session: SessionDependency,
    game_service: GameServiceDependency,
    gameplay_service: GameplayServiceDependency,
    invite_token: str | None = Query(default=None),
) -> GameResponse:
    try:
        await validate_private_game_access(
            session=session,
            game_id=game_id,
            game_service=game_service,
            gameplay_service=gameplay_service,
            invite_token=invite_token,
        )
        game = await gameplay_service.offer_draw(
            session,
            game_id=game_id,
            player_id=request.player_id,
        )
        await session.commit()
        await session.refresh(game)
    except GameplayServiceError as exc:
        raise gameplay_error_to_http(exc) from exc

    return serialize_game(game)


@router.post("/{game_id}/draw-accept", response_model=GameResponse)
async def accept_draw(
    game_id: UUID,
    request: PlayerActionRequest,
    session: SessionDependency,
    game_service: GameServiceDependency,
    gameplay_service: GameplayServiceDependency,
    invite_token: str | None = Query(default=None),
) -> GameResponse:
    try:
        await validate_private_game_access(
            session=session,
            game_id=game_id,
            game_service=game_service,
            gameplay_service=gameplay_service,
            invite_token=invite_token,
        )
        game = await gameplay_service.accept_draw(
            session,
            game_id=game_id,
            player_id=request.player_id,
        )
        await session.commit()
        await session.refresh(game)
    except GameplayServiceError as exc:
        raise gameplay_error_to_http(exc) from exc

    return serialize_game(game)


@router.post("/{game_id}/timeout-claim", response_model=GameResponse)
async def claim_timeout(
    game_id: UUID,
    request: PlayerActionRequest,
    session: SessionDependency,
    game_service: GameServiceDependency,
    gameplay_service: GameplayServiceDependency,
    invite_token: str | None = Query(default=None),
) -> GameResponse:
    try:
        await validate_private_game_access(
            session=session,
            game_id=game_id,
            game_service=game_service,
            gameplay_service=gameplay_service,
            invite_token=invite_token,
        )
        game = await gameplay_service.claim_timeout(
            session,
            game_id=game_id,
            player_id=request.player_id,
        )
        await session.commit()
        await session.refresh(game)
    except GameplayServiceError as exc:
        raise gameplay_error_to_http(exc) from exc

    return serialize_game(game)
