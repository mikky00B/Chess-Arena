from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.games import GameResponse, TimeControlRequest, serialize_game
from app.core.database import get_session
from app.game.state import TimeControl
from app.models import User
from app.services.matchmaking_service import (
    MatchmakingService,
    MatchmakingTicket,
    PlayerAlreadyQueuedError,
)

router = APIRouter(prefix="/api/matchmaking", tags=["matchmaking"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]

matchmaking_service = MatchmakingService()


class QueueRequest(BaseModel):
    player_id: UUID
    time_control: TimeControlRequest
    rated: bool = False


class QueueStatusResponse(BaseModel):
    queued: bool
    player_id: UUID
    time_control_initial_seconds: int | None = None
    time_control_increment_seconds: int | None = None
    rated: bool | None = None
    queued_at: datetime | None = None


class QueueResponse(BaseModel):
    matched: bool
    ticket: QueueStatusResponse | None = None
    game: GameResponse | None = None


def get_matchmaking_service() -> MatchmakingService:
    return matchmaking_service


MatchmakingServiceDependency = Annotated[
    MatchmakingService,
    Depends(get_matchmaking_service),
]


def ticket_response(player_id: UUID, ticket: MatchmakingTicket | None) -> QueueStatusResponse:
    if ticket is None:
        return QueueStatusResponse(queued=False, player_id=player_id)
    return QueueStatusResponse(
        queued=True,
        player_id=player_id,
        time_control_initial_seconds=ticket.time_control.initial_seconds,
        time_control_increment_seconds=ticket.time_control.increment_seconds,
        rated=ticket.rated,
        queued_at=ticket.queued_at,
    )


@router.post("/queue", response_model=QueueResponse, status_code=status.HTTP_201_CREATED)
async def queue_player(
    request: QueueRequest,
    session: SessionDependency,
    service: MatchmakingServiceDependency,
) -> QueueResponse:
    player = await session.get(User, request.player_id)
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")

    try:
        result = service.queue_player(
            player=player,
            time_control=TimeControl(
                initial_seconds=request.time_control.initial_seconds,
                increment_seconds=request.time_control.increment_seconds,
            ),
            rated=request.rated,
        )
    except PlayerAlreadyQueuedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if result.game is not None:
        session.add(result.game)
        await session.commit()
        await session.refresh(result.game)
        return QueueResponse(matched=True, game=serialize_game(result.game))

    return QueueResponse(
        matched=False,
        ticket=ticket_response(request.player_id, result.ticket),
    )


@router.delete("/queue", response_model=QueueStatusResponse)
async def cancel_queue(
    request: QueueRequest,
    service: MatchmakingServiceDependency,
) -> QueueStatusResponse:
    ticket = service.cancel_queue(player_id=request.player_id)
    return ticket_response(request.player_id, ticket)


@router.get("/status", response_model=QueueStatusResponse)
async def matchmaking_status(
    player_id: UUID,
    service: MatchmakingServiceDependency,
) -> QueueStatusResponse:
    ticket = service.get_ticket(player_id=player_id)
    return ticket_response(player_id, ticket)
