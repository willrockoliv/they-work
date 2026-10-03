"""Serviços de domínio do backend TheyWork."""

from app.services import (
    agent_service,
    audit_service,
    complexity_classifier,
    council_service,
    model_catalog,
    prompt_factory,
    ra_service,
    talent_bank,
)
from app.services.nature_manager import (
    HiringRequest,
    HiringVerdict,
    NatureAlert,
    NatureManager,
    ResourceSnapshot,
    get_nature_manager,
)
from app.services.ollama_client import InstalledModel, OllamaClient, OllamaUnavailableError

__all__ = [
    "HiringRequest",
    "HiringVerdict",
    "InstalledModel",
    "NatureAlert",
    "NatureManager",
    "OllamaClient",
    "OllamaUnavailableError",
    "ResourceSnapshot",
    "agent_service",
    "audit_service",
    "complexity_classifier",
    "council_service",
    "get_nature_manager",
    "model_catalog",
    "prompt_factory",
    "ra_service",
    "talent_bank",
]
