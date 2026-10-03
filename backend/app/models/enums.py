"""Enumerações de domínio compartilhadas entre ORM, serviços e API."""

from __future__ import annotations

from enum import StrEnum


class AgentType(StrEnum):
    """Natureza do agente dentro da empresa."""

    CHIEF = "CHIEF"
    SUBAGENT = "SUBAGENT"


class AgentRole(StrEnum):
    """Cargos fixos (C-Level + RA) e o cargo genérico dos efêmeros."""

    CEO = "CEO"
    CTO = "CTO"
    CMO = "CMO"
    CFO = "CFO"
    RA = "RA"
    SUBAGENT = "SUBAGENT"


class AgentStatus(StrEnum):
    """Estado operacional do agente."""

    IDLE = "IDLE"
    WORKING = "WORKING"
    BLOCKED = "BLOCKED"
    TERMINATED = "TERMINATED"


class TaskComplexity(StrEnum):
    """Peso cognitivo da tarefa, usado na seleção de modelo."""

    TRIVIAL = "TRIVIAL"
    SIMPLE = "SIMPLE"
    MODERATE = "MODERATE"
    COMPLEX = "COMPLEX"
    CRITICAL = "CRITICAL"


class ResourceStatus(StrEnum):
    """Veredito da Natureza sobre a saúde da infraestrutura."""

    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class NatureDecision(StrEnum):
    """Decisão da Natureza sobre uma requisição de contratação."""

    ALLOWED = "ALLOWED"
    DOWNGRADED = "DOWNGRADED"
    QUEUED = "QUEUED"
    BLOCKED = "BLOCKED"


class AuditEventType(StrEnum):
    """Categorias de evento registradas na trilha de auditoria."""

    NATURE_DECISION = "NATURE_DECISION"
    NATURE_ALERT = "NATURE_ALERT"
    AGENT_CREATED = "AGENT_CREATED"
    AGENT_TERMINATED = "AGENT_TERMINATED"
    AGENT_STATUS_CHANGED = "AGENT_STATUS_CHANGED"
    MODEL_SELECTED = "MODEL_SELECTED"
    SYSTEM = "SYSTEM"


class MemoryType(StrEnum):
    """Tipos de registro da memória corporativa de longo prazo."""

    DECISION = "DECISION"
    REPORT = "REPORT"
    MEETING = "MEETING"
    DIALOGUE = "DIALOGUE"
    KNOWLEDGE = "KNOWLEDGE"


CHIEF_ROLES: tuple[AgentRole, ...] = (
    AgentRole.CEO,
    AgentRole.CTO,
    AgentRole.CMO,
    AgentRole.CFO,
    AgentRole.RA,
)
