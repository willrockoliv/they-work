"""Dependências compartilhadas pelas rotas."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.config.database import get_db_session
from app.config.settings import Settings, get_settings
from app.services.nature_manager import NatureManager, get_nature_manager
from app.services.ollama_client import OllamaClient

DbSession = Annotated[Session, Depends(get_db_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]
Nature = Annotated[NatureManager, Depends(get_nature_manager)]


def get_ollama_client() -> OllamaClient:
    """Cliente Ollama por requisição."""
    return OllamaClient()


Ollama = Annotated[OllamaClient, Depends(get_ollama_client)]
