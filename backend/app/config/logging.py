"""Logging estruturado (structlog) compartilhado por toda a aplicação."""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from app.config.settings import Settings, get_settings

_configured = False


def configure_logging(settings: Settings | None = None) -> None:
    """Configura structlog + logging stdlib. Idempotente."""
    global _configured
    if _configured:
        return

    settings = settings or get_settings()
    level = getattr(logging, settings.log_level)

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)
    for noisy in ("uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(max(level, logging.INFO))

    renderer: Any = (
        structlog.processors.JSONRenderer()
        if settings.log_format == "json"
        else structlog.dev.ConsoleRenderer(colors=False)
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Retorna um logger estruturado nomeado."""
    configure_logging()
    return structlog.get_logger(name)  # type: ignore[no-any-return]
