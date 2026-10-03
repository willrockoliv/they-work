"""Rotas HTTP do backend TheyWork."""

from fastapi import APIRouter

from app.routes import (
    agents,
    council,
    game,
    health,
    hiring,
    models,
    nature,
    reasoning,
    resources,
    talent,
    ws,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(resources.router)
api_router.include_router(nature.router)
api_router.include_router(agents.router)
api_router.include_router(council.router)
api_router.include_router(hiring.router)
api_router.include_router(talent.router)
api_router.include_router(models.router)
api_router.include_router(reasoning.router)
api_router.include_router(game.router)
api_router.include_router(ws.router)

__all__ = ["api_router"]
