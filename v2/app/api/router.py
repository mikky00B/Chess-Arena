from fastapi import APIRouter

from app.api import challenges, fair_play, games, health, matchmaking, settlements, tournaments
from app.ws import game_socket

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(games.router)
api_router.include_router(matchmaking.router)
api_router.include_router(challenges.router)
api_router.include_router(settlements.router)
api_router.include_router(tournaments.router)
api_router.include_router(fair_play.router)
api_router.include_router(game_socket.router)
