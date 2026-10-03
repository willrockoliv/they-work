"""Health check do backend e de suas dependências."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.models.base import utcnow
from app.routes.deps import AppSettings, DbSession, Ollama
from app.schemas.health import ComponentHealth, HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Saúde do backend")
async def health(settings: AppSettings, session: DbSession, ollama: Ollama) -> HealthResponse:
    """Verifica backend, PostgreSQL e Ollama."""
    components = [_check_database(session), await _check_ollama(ollama)]

    down = any(component.status == "down" for component in components)
    overall = "degraded" if down else "ok"

    return HealthResponse(
        status=overall,
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env,
        timestamp=utcnow(),
        components=components,
    )


@router.get("/health/live", summary="Liveness probe")
async def liveness() -> dict[str, str]:
    """Responde enquanto o processo estiver de pé."""
    return {"status": "ok"}


def _check_database(session: DbSession) -> ComponentHealth:
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        return ComponentHealth(name="postgres", status="down", detail=str(exc)[:200])
    return ComponentHealth(name="postgres", status="ok")


async def _check_ollama(ollama: Ollama) -> ComponentHealth:
    version = await ollama.version()
    if version is None:
        return ComponentHealth(name="ollama", status="down", detail="servidor inacessível")
    return ComponentHealth(name="ollama", status="ok", detail=f"versão {version}")
