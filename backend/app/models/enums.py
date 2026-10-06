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


class InitialRequestStatus(StrEnum):
    """Ciclo de vida de um pedido submetido pelo observador ao conselho."""

    PROPOSED = "PROPOSED"
    DELIBERATING = "DELIBERATING"
    IN_EXECUTION = "IN_EXECUTION"
    AWAITING_FEEDBACK = "AWAITING_FEEDBACK"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class CommunicationType(StrEnum):
    """Natureza de uma aresta do grafo de comunicações corporativas."""

    REQUEST = "REQUEST"
    OPINION = "OPINION"
    COORDINATION = "COORDINATION"
    AGENT_REQUEST = "AGENT_REQUEST"
    AGENT_CREATED = "AGENT_CREATED"
    DELEGATION = "DELEGATION"
    REPORT = "REPORT"
    CONSULTATION = "CONSULTATION"
    ESCALATION = "ESCALATION"
    DECISION = "DECISION"


class CommunicationStatus(StrEnum):
    """Estado de entrega de uma aresta do grafo."""

    PENDING = "PENDING"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PROCESSED = "PROCESSED"


class TaskStatus(StrEnum):
    """Ciclo de vida de uma tarefa delegada por um Chief ao seu subordinado."""

    PENDING = "PENDING"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    IN_PROGRESS = "IN_PROGRESS"
    AWAITING_REVIEW = "AWAITING_REVIEW"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class ChiefDecision(StrEnum):
    """Veredito do Chief supervisor sobre o report de um subordinado."""

    APPROVE = "APPROVE"
    REJECT = "REJECT"
    MODIFY = "MODIFY"
    CONSULT_PEERS = "CONSULT_PEERS"
    ESCALATE = "ESCALATE"


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
    REASONING_STARTED = "REASONING_STARTED"
    REASONING_COMPLETED = "REASONING_COMPLETED"
    REASONING_FAILED = "REASONING_FAILED"
    REASONING_PURGED = "REASONING_PURGED"
    REQUEST_SUBMITTED = "REQUEST_SUBMITTED"
    REQUEST_RESOLVED = "REQUEST_RESOLVED"
    AGENT_REQUESTED = "AGENT_REQUESTED"
    TASK_DELEGATED = "TASK_DELEGATED"
    TASK_REPORTED = "TASK_REPORTED"
    TASK_REVIEWED = "TASK_REVIEWED"
    CHIEF_CONSULTATION = "CHIEF_CONSULTATION"
    CEO_TIEBREAK = "CEO_TIEBREAK"


class MemoryType(StrEnum):
    """Tipos de registro da memória corporativa de longo prazo."""

    DECISION = "DECISION"
    REPORT = "REPORT"
    MEETING = "MEETING"
    DIALOGUE = "DIALOGUE"
    KNOWLEDGE = "KNOWLEDGE"


class ReasoningStepType(StrEnum):
    """Nós do ciclo ReAct capturados durante o raciocínio de um agente."""

    THOUGHT = "THOUGHT"
    ACTION = "ACTION"
    OBSERVATION = "OBSERVATION"
    CONCLUSION = "CONCLUSION"


class ReasoningStatus(StrEnum):
    """Estado de uma sessão de raciocínio."""

    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


CHIEF_ROLES: tuple[AgentRole, ...] = (
    AgentRole.CEO,
    AgentRole.CTO,
    AgentRole.CMO,
    AgentRole.CFO,
    AgentRole.RA,
)

#: Chiefs que supervisionam subagentes (o RA cria, mas nunca supervisiona).
SUPERVISING_ROLES: tuple[AgentRole, ...] = (
    AgentRole.CEO,
    AgentRole.CTO,
    AgentRole.CMO,
    AgentRole.CFO,
)
