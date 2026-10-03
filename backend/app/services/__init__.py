"""Serviços de domínio do backend TheyWork."""

from app.services import agent_service, audit_service, model_catalog
from app.services.nature_manager import (
    HiringRequest,
    HiringVerdict,
    NatureManager,
    ResourceSnapshot,
    get_nature_manager,
)
from app.services.ollama_client import InstalledModel, OllamaClient, OllamaUnavailableError

__all__ = [
    "HiringRequest",
    "HiringVerdict",
    "InstalledModel",
    "NatureManager",
    "OllamaClient",
    "OllamaUnavailableError",
    "ResourceSnapshot",
    "agent_service",
    "audit_service",
    "get_nature_manager",
    "model_catalog",
]
