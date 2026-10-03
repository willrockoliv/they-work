"""Rotas HTTP do backend TheyWork."""

from fastapi import APIRouter

from app.routes import agents, health, models, resources

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(resources.router)
api_router.include_router(agents.router)
api_router.include_router(models.router)

__all__ = ["api_router"]
