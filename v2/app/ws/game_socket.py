from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.games import get_game_service, serialize_game, serialize_move
from app.core.database import get_session
from app.services.game_service import GameService, PrivateInviteError
from app.services.persistent_gameplay_service import (
    GameplayServiceError,
    ParticipantAuthorizationError,
    PersistentGameplayService,
)
from app.ws.connection_manager import GameConnectionManager

router = APIRouter()
manager = GameConnectionManager()

SessionDependency = Annotated[AsyncSession, Depends(get_session)]
GameServiceDependency = Annotated[GameService, Depends(get_game_service)]


def get_gameplay_service() -> PersistentGameplayService:
    return PersistentGameplayService()


GameplayServiceDependency = Annotated[PersistentGameplayService, Depends(get_gameplay_service)]


@router.websocket("/ws/games/{game_id}")
async def game_websocket(
    websocket: WebSocket,
    game_id: UUID,
    player_id: UUID,
    session: SessionDependency,
    game_service: GameServiceDependency,
    gameplay_service: GameplayServiceDependency,
    invite_token: str | None = Query(default=None),
) -> None:
    try:
        game = await gameplay_service.get_game(session, game_id=game_id)
        game_service.validate_private_invite(game, invite_token=invite_token)
        gameplay_service.ensure_participant(game, player_id=player_id)
    except PrivateInviteError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    except (GameplayServiceError, ParticipantAuthorizationError):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(game_id=game_id, websocket=websocket)
    await websocket.send_json(
        {
            "type": "game_state",
            "game": serialize_game(game).model_dump(mode="json"),
        }
    )

    try:
        while True:
            payload = await websocket.receive_json()
            event = await handle_game_event(
                payload=payload,
                game_id=game_id,
                player_id=player_id,
                session=session,
                gameplay_service=gameplay_service,
            )
            await session.commit()
            await manager.broadcast(game_id=game_id, message=event)
    except WebSocketDisconnect:
        manager.disconnect(game_id=game_id, websocket=websocket)
    except GameplayServiceError as exc:
        await websocket.send_json({"type": "error", "detail": str(exc)})


async def handle_game_event(
    *,
    payload: dict[str, object],
    game_id: UUID,
    player_id: UUID,
    session: AsyncSession,
    gameplay_service: PersistentGameplayService,
) -> dict[str, object]:
    event_type = payload.get("type")
    if event_type == "move":
        uci = payload.get("uci")
        if not isinstance(uci, str):
            raise GameplayServiceError("move event requires a UCI string")
        result = await gameplay_service.submit_move(
            session,
            game_id=game_id,
            player_id=player_id,
            uci=uci,
        )
        return {
            "type": "move",
            "game": serialize_game(result.game).model_dump(mode="json"),
            "move": serialize_move(result.move).model_dump(mode="json"),
        }
    if event_type == "resign":
        game = await gameplay_service.resign(session, game_id=game_id, player_id=player_id)
        return {"type": "game_finished", "game": serialize_game(game).model_dump(mode="json")}
    if event_type == "draw_offer":
        game = await gameplay_service.offer_draw(session, game_id=game_id, player_id=player_id)
        return {"type": "draw_offer", "game": serialize_game(game).model_dump(mode="json")}
    if event_type == "draw_accept":
        game = await gameplay_service.accept_draw(session, game_id=game_id, player_id=player_id)
        return {"type": "game_finished", "game": serialize_game(game).model_dump(mode="json")}
    if event_type == "timeout_claim":
        game = await gameplay_service.claim_timeout(session, game_id=game_id, player_id=player_id)
        return {"type": "game_finished", "game": serialize_game(game).model_dump(mode="json")}
    raise GameplayServiceError("unsupported websocket event type")
