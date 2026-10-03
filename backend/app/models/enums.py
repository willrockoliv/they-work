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


class CommunicationKind(StrEnum):
    """Natureza de uma mensagem trocada no conselho administrativo."""

    DIRECTIVE = "DIRECTIVE"
    ANALYSIS = "ANALYSIS"
    DECISION = "DECISION"
    QUESTION = "QUESTION"
    ANSWER = "ANSWER"
    REPORT = "REPORT"
    ESCALATION = "ESCALATION"


class RequestStatus(StrEnum):
    """Ciclo de vida de uma requisição de subagente aberta por um Chief."""

    DRAFT = "DRAFT"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    CLARIFIED = "CLARIFIED"
    QUEUED = "QUEUED"
    FULFILLED = "FULFILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class CouncilStance(StrEnum):
    """Posição individual de um Chief numa deliberação."""

    APPROVE = "APPROVE"
    REJECT = "REJECT"
    ABSTAIN = "ABSTAIN"


class CouncilOutcome(StrEnum):
    """Veredito consolidado do conselho, dado pelo CEO."""

    APPROVED = "APPROVED"
    APPROVED_WITH_CONDITIONS = "APPROVED_WITH_CONDITIONS"
    REJECTED = "REJECTED"


class AuditEventType(StrEnum):
    """Categorias de evento registradas na trilha de auditoria."""

    NATURE_DECISION = "NATURE_DECISION"
    NATURE_ALERT = "NATURE_ALERT"
    AGENT_CREATED = "AGENT_CREATED"
    AGENT_TERMINATED = "AGENT_TERMINATED"
    AGENT_STATUS_CHANGED = "AGENT_STATUS_CHANGED"
    MODEL_SELECTED = "MODEL_SELECTED"
    SYSTEM = "SYSTEM"
    CHIEF_COMMUNICATION = "CHIEF_COMMUNICATION"
    COUNCIL_DELIBERATION = "COUNCIL_DELIBERATION"
    SUBAGENT_REQUESTED = "SUBAGENT_REQUESTED"
    SUBAGENT_CLARIFICATION = "SUBAGENT_CLARIFICATION"
    TALENT_PROFILE_CREATED = "TALENT_PROFILE_CREATED"
    TALENT_PROFILE_REUSED = "TALENT_PROFILE_REUSED"
    TALENT_PROFILE_RATED = "TALENT_PROFILE_RATED"


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
