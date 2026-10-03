"""Serviços de domínio do backend TheyWork."""

from app.services import (
    agent_service,
    audit_service,
    complexity_classifier,
    council_service,
    model_catalog,
    prompt_factory,
    ra_service,
    react_engine,
    reasoning_flow,
    reasoning_metrics,
    reasoning_service,
    reasoning_tools,
    reasoning_tracer,
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
from app.services.ollama_client import (
    InstalledModel,
    OllamaClient,
    OllamaCompletion,
    OllamaUnavailableError,
)
from app.services.reasoning_broker import ReasoningBroker, get_broker
from app.services.reasoning_tracer import ReasoningTracer

__all__ = [
    "HiringRequest",
    "HiringVerdict",
    "InstalledModel",
    "NatureAlert",
    "NatureManager",
    "OllamaClient",
    "OllamaCompletion",
    "OllamaUnavailableError",
    "ReasoningBroker",
    "ReasoningTracer",
    "ResourceSnapshot",
    "agent_service",
    "audit_service",
    "complexity_classifier",
    "council_service",
    "get_broker",
    "get_nature_manager",
    "model_catalog",
    "prompt_factory",
    "ra_service",
    "react_engine",
    "reasoning_flow",
    "reasoning_metrics",
    "reasoning_service",
    "reasoning_tools",
    "reasoning_tracer",
    "talent_bank",
]
