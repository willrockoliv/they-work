"""Ponto de entrada da API FastAPI do TheyWork."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.logging import configure_logging, get_logger
from app.config.settings import get_settings
from app.routes import api_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Inicializa e encerra recursos do processo."""
    settings = get_settings()
    configure_logging(settings)
    logger.info(
        "app.startup",
        app=settings.app_name,
        version=settings.app_version,
        env=settings.app_env,
        ram_limit_mb=settings.nature_ram_limit_mb,
        vram_limit_mb=settings.nature_vram_limit_mb,
    )
    yield
    logger.info("app.shutdown")


def create_app() -> FastAPI:
    """Factory da aplicação."""
    settings = get_settings()
    configure_logging(settings)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Backend da simulação corporativa TheyWork: agentes de IA autônomos operando "
            "uma empresa virtual sob os limites físicos impostos pela Natureza."
        ),
        lifespan=lifespan,
    )

    # Frontend 2D (Fase 4) consome esta API a partir do host.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
