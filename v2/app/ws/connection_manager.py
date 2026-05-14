from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from fastapi import WebSocket


class GameConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[UUID, set[WebSocket]] = defaultdict(set)

    async def connect(self, *, game_id: UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[game_id].add(websocket)

    def disconnect(self, *, game_id: UUID, websocket: WebSocket) -> None:
        connections = self._connections.get(game_id)
        if connections is None:
            return
        connections.discard(websocket)
        if not connections:
            self._connections.pop(game_id, None)

    async def broadcast(self, *, game_id: UUID, message: dict[str, object]) -> None:
        for websocket in tuple(self._connections.get(game_id, set())):
            await websocket.send_json(message)
