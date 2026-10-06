"""Rede corporativa — grafo de comunicações entre o observador, os Chiefs e seus times.

Cada mutação do grafo é uma aresta persistida em `communication_graph` e publicada
no barramento da Fase 3, de modo que o frontend vê a rede crescer em tempo real.

Hierarquia (invariante do domínio):
- só um Chief supervisor (CEO/CTO/CMO/CFO) delega e recebe report;
- o RA cria agentes a pedido de um Chief e sai do fluxo — nunca supervisiona;
- o agente criado reporta ao Chief que o solicitou (`Agent.reports_to_id`).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.logging import get_logger
from app.models.agent import Agent
from app.models.base import utcnow
from app.models.enums import (
    SUPERVISING_ROLES,
    AgentRole,
    AgentStatus,
    AgentType,
    AuditEventType,
    CommunicationStatus,
    CommunicationType,
    InitialRequestStatus,
    TaskStatus,
)
from app.models.network import AgentTask, CommunicationEdge, InitialRequest
from app.models.reasoning import ReasoningSession
from app.services import agent_service, audit_service, council_service, ra_service, react_engine
from app.services.council_service import CouncilDecision, Proposal
from app.services.nature_manager import NatureManager
from app.services.ollama_client import OllamaClient
from app.services.ra_service import HiringIntake, HiringOutcome
from app.services.react_engine import TaskRequest
from app.services.reasoning_broker import get_broker

logger = get_logger(__name__)


class HierarchyError(ValueError):
    """Operação que violaria a cadeia de supervisão da empresa."""


class CompanyNotFoundedError(RuntimeError):
    """Não há conselho para receber o pedido: os Chiefs nunca foram inicializados."""


@dataclass(frozen=True, slots=True)
class RequestIntake:
    """Pedido bruto submetido pelo observador ao conselho."""

    topic: str
    description: str
    submitted_by: str = "OBSERVER"


@dataclass(frozen=True, slots=True)
class DelegationIntake:
    """Tarefa que um Chief quer colocar na fila de um subordinado."""

    title: str
    task_description: str
    acceptance_criteria: tuple[str, ...] = field(default_factory=tuple)
    context: dict[str, Any] = field(default_factory=dict)


# --- Pedidos -----------------------------------------------------------------


def submit_request(session: Session, intake: RequestIntake) -> InitialRequest:
    """Registra o pedido e abre o grafo com a aresta observador → CEO."""
    ceo = agent_service.get_chief(session, AgentRole.CEO)
    if ceo is None:
        # Sem conselho o pedido viraria um grafo só de arestas órfãs, sem ninguém
        # para deliberar — melhor recusar na porta de entrada.
        msg = (
            "A empresa ainda não foi fundada: inicialize o conselho antes de submeter "
            "um pedido."
        )
        raise CompanyNotFoundedError(msg)

    request = InitialRequest(
        topic=intake.topic[:255],
        description=intake.description,
        submitted_by=intake.submitted_by[:120],
        status=InitialRequestStatus.PROPOSED,
        current_state={"milestones": []},
    )
    session.add(request)
    session.flush()

    record_edge(
        session,
        request,
        communication_type=CommunicationType.REQUEST,
        sender=None,
        recipient=ceo,
        summary=intake.topic,
        content={"description": intake.description, "submitted_by": intake.submitted_by},
    )

    audit_service.record_event(
        session,
        event_type=AuditEventType.REQUEST_SUBMITTED,
        actor=intake.submitted_by,
        summary=f"Pedido ao conselho: {intake.topic}",
        narrative=intake.description,
        payload={"request_id": str(request.id)},
    )
    session.flush()
    logger.info("network.request_submitted", request_id=str(request.id), topic=intake.topic)
    return request


def deliberate(session: Session, request: InitialRequest) -> CouncilDecision:
    """CEO consulta as diretorias e coordena a alocação de responsabilidades."""
    decision = council_service.deliberate(
        session,
        Proposal(
            topic=request.topic,
            description=request.description,
            submitted_by=AgentRole.CEO,
            context={"request_id": str(request.id)},
        ),
    )

    ceo = agent_service.get_chief(session, AgentRole.CEO)
    for opinion in decision.opinions:
        if opinion.role is AgentRole.CEO:
            continue
        chief = agent_service.get_chief(session, opinion.role)
        record_edge(
            session,
            request,
            communication_type=CommunicationType.OPINION,
            sender=chief,
            recipient=ceo,
            summary=f"{opinion.role.value}: {opinion.stance.value}",
            content=opinion.to_dict(),
            status=CommunicationStatus.PROCESSED,
        )

    for role in SUPERVISING_ROLES:
        if role is AgentRole.CEO:
            continue
        record_edge(
            session,
            request,
            communication_type=CommunicationType.COORDINATION,
            sender=ceo,
            recipient=agent_service.get_chief(session, role),
            summary=f"Área alocada ao {role.value}",
            content={"outcome": decision.outcome.value, "conditions": list(decision.conditions)},
        )

    request.thread_id = decision.thread_id
    request.outcome = decision.outcome.value
    request.narrative = decision.narrative
    request.status = InitialRequestStatus.DELIBERATING
    _push_milestone(request, "deliberated", {"outcome": decision.outcome.value})
    session.flush()
    return decision


# --- RA: criação de agentes a pedido de um Chief -----------------------------


def request_agent(
    session: Session,
    nature: NatureManager,
    request: InitialRequest,
    chief: Agent,
    intake: HiringIntake,
) -> HiringOutcome:
    """Chief solicita ao RA um agente novo; o criado passa a reportar ao solicitante."""
    _require_supervisor(chief)
    if intake.requested_by is not chief.role:
        msg = "A requisição ao RA precisa ser assinada pelo próprio Chief solicitante."
        raise HierarchyError(msg)

    ra = agent_service.get_chief(session, AgentRole.RA)
    record_edge(
        session,
        request,
        communication_type=CommunicationType.AGENT_REQUEST,
        sender=chief,
        recipient=ra,
        summary=f"{chief.role.value} pede um {intake.job_title}",
        content={"job_title": intake.job_title, "objective": intake.objective},
    )

    outcome = ra_service.submit_request(session, nature, intake)

    if outcome.agent is not None:
        # O RA cria, mas quem supervisiona é o Chief solicitante.
        outcome.agent.reports_to_id = chief.id
        record_edge(
            session,
            request,
            communication_type=CommunicationType.AGENT_CREATED,
            sender=ra,
            recipient=outcome.agent,
            summary=f"{outcome.agent.name} criado e vinculado ao {chief.role.value}",
            content={
                "agent_id": str(outcome.agent.id),
                "reports_to": chief.role.value,
                "reused_profile": outcome.reused_profile,
                "model_name": outcome.agent.model_name,
            },
            status=CommunicationStatus.PROCESSED,
        )

    audit_service.record_event(
        session,
        event_type=AuditEventType.AGENT_REQUESTED,
        actor=chief.role.value,
        decision=outcome.request.status.value,
        summary=f"{chief.role.value} solicitou ao RA: {intake.job_title}",
        narrative=outcome.narrative or "Requisição encaminhada ao RA.",
        agent_id=chief.id,
        payload={
            "request_id": str(request.id),
            "hiring_request_id": str(outcome.request.id),
            "questions": list(outcome.questions),
            "created_agent_id": str(outcome.agent.id) if outcome.agent else None,
        },
    )
    session.flush()
    return outcome


# --- Delegação e execução ----------------------------------------------------


def delegate_task(
    session: Session,
    request: InitialRequest,
    chief: Agent,
    agent: Agent,
    intake: DelegationIntake,
    *,
    parent: AgentTask | None = None,
) -> AgentTask:
    """Cria a tarefa e a aresta DELEGATION do Chief para o seu subordinado."""
    _require_supervisor(chief)
    if agent.reports_to_id != chief.id:
        msg = (
            f"{agent.name} não reporta ao {chief.role.value}: um Chief só delega para o "
            "próprio time."
        )
        raise HierarchyError(msg)

    context = dict(intake.context)
    if intake.acceptance_criteria:
        context["acceptance_criteria"] = list(intake.acceptance_criteria)

    task = AgentTask(
        request_id=request.id,
        parent_task_id=parent.id if parent else None,
        assigned_by_chief_id=chief.id,
        assigned_to_agent_id=agent.id,
        title=intake.title[:160],
        task_description=intake.task_description,
        context=context,
        status=TaskStatus.PENDING,
        attempt=(parent.attempt + 1) if parent else 1,
        delegated_at=utcnow(),
    )
    session.add(task)
    session.flush()

    record_edge(
        session,
        request,
        communication_type=CommunicationType.DELEGATION,
        sender=chief,
        recipient=agent,
        summary=intake.title,
        content={"task_description": intake.task_description, "attempt": task.attempt},
        task=task,
    )

    request.status = InitialRequestStatus.IN_EXECUTION
    _push_milestone(request, "delegated", {"task_id": str(task.id), "title": task.title})

    audit_service.record_event(
        session,
        event_type=AuditEventType.TASK_DELEGATED,
        actor=chief.role.value,
        summary=f"{chief.role.value} delegou '{task.title}' a {agent.name}",
        narrative=intake.task_description,
        agent_id=agent.id,
        payload={"request_id": str(request.id), "task_id": str(task.id), "attempt": task.attempt},
    )
    session.flush()
    publish_task(task)
    return task


def execute_task(
    session: Session,
    task: AgentTask,
    *,
    nature: NatureManager | None = None,
    ollama: OllamaClient | None = None,
) -> ReasoningSession:
    """O agente raciocina sobre a tarefa e reporta ao seu Chief supervisor."""
    agent = session.get(Agent, task.assigned_to_agent_id) if task.assigned_to_agent_id else None
    if agent is None:
        msg = "A tarefa não tem um agente atribuído."
        raise HierarchyError(msg)

    request = session.get(InitialRequest, task.request_id)
    task.status = TaskStatus.IN_PROGRESS
    session.flush()

    criteria = task.context.get("acceptance_criteria", [])
    reasoning = react_engine.run_task(
        session,
        agent=agent,
        request=TaskRequest(
            task=task.task_description,
            thread_id=request.thread_id if request else None,
            context={
                "tarefa": task.title,
                "tentativa": task.attempt,
                "criterios_de_aceitacao": "; ".join(str(item) for item in criteria) or "nenhum",
            },
        ),
        nature=nature,
        ollama=ollama,
        task_id=task.id,
    )
    return report_task(session, task, reasoning)


def report_task(
    session: Session, task: AgentTask, reasoning: ReasoningSession
) -> ReasoningSession:
    """Fecha o ciclo do agente: o report sobe para o Chief supervisor."""
    request = session.get(InitialRequest, task.request_id)
    agent = session.get(Agent, task.assigned_to_agent_id) if task.assigned_to_agent_id else None
    chief = session.get(Agent, task.assigned_by_chief_id) if task.assigned_by_chief_id else None

    task.report_reasoning_session_id = reasoning.id
    task.report_summary = reasoning.conclusion or reasoning.error or ""
    task.reported_at = utcnow()
    task.status = TaskStatus.AWAITING_REVIEW
    session.flush()

    if request is not None:
        record_edge(
            session,
            request,
            communication_type=CommunicationType.REPORT,
            sender=agent,
            recipient=chief,
            summary=f"Report de '{task.title}'",
            content={"conclusion": task.report_summary, "attempt": task.attempt},
            task=task,
            reasoning_session_id=reasoning.id,
        )
        request.status = InitialRequestStatus.AWAITING_FEEDBACK
        _push_milestone(request, "reported", {"task_id": str(task.id)})

    audit_service.record_event(
        session,
        event_type=AuditEventType.TASK_REPORTED,
        actor=agent.name if agent else "SUBAGENT",
        summary=f"Report entregue: {task.title}",
        narrative=task.report_summary,
        agent_id=agent.id if agent else None,
        payload={
            "task_id": str(task.id),
            "request_id": str(task.request_id),
            "reasoning_session_id": str(reasoning.id),
            "reports_to": chief.role.value if chief else None,
        },
    )
    session.flush()
    publish_task(task)
    return reasoning


# --- Arestas e consultas -----------------------------------------------------


def record_edge(
    session: Session,
    request: InitialRequest,
    *,
    communication_type: CommunicationType,
    sender: Agent | None,
    recipient: Agent | None,
    summary: str,
    content: dict[str, Any] | None = None,
    task: AgentTask | None = None,
    reasoning_session_id: uuid.UUID | None = None,
    status: CommunicationStatus = CommunicationStatus.PENDING,
) -> CommunicationEdge:
    """Persiste uma aresta do grafo e a publica no barramento."""
    edge = CommunicationEdge(
        request_id=request.id,
        task_id=task.id if task else None,
        sender_agent_id=sender.id if sender else None,
        recipient_agent_id=recipient.id if recipient else None,
        communication_type=communication_type,
        status=status,
        summary=summary[:255],
        content=content or {},
        reasoning_session_id=reasoning_session_id,
        responded_at=utcnow() if status is CommunicationStatus.PROCESSED else None,
    )
    session.add(edge)
    session.flush()
    _publish("network.edge", edge.to_dict())
    return edge


def list_requests(session: Session, *, limit: int = 50) -> list[InitialRequest]:
    return list(
        session.scalars(
            select(InitialRequest).order_by(InitialRequest.created_at.desc()).limit(limit)
        )
    )


def list_edges(session: Session, request_id: uuid.UUID) -> list[CommunicationEdge]:
    return list(
        session.scalars(
            select(CommunicationEdge)
            .where(CommunicationEdge.request_id == request_id)
            .order_by(CommunicationEdge.created_at, CommunicationEdge.id)
        )
    )


def list_tasks(
    session: Session,
    *,
    request_id: uuid.UUID | None = None,
    agent_id: uuid.UUID | None = None,
    chief_id: uuid.UUID | None = None,
    status: TaskStatus | None = None,
) -> list[AgentTask]:
    stmt = select(AgentTask).order_by(AgentTask.created_at)
    if request_id is not None:
        stmt = stmt.where(AgentTask.request_id == request_id)
    if agent_id is not None:
        stmt = stmt.where(AgentTask.assigned_to_agent_id == agent_id)
    if chief_id is not None:
        stmt = stmt.where(AgentTask.assigned_by_chief_id == chief_id)
    if status is not None:
        stmt = stmt.where(AgentTask.status == status)
    return list(session.scalars(stmt))


def pending_reviews(session: Session, chief_id: uuid.UUID) -> list[AgentTask]:
    """Reports dos subordinados aguardando o veredito do Chief."""
    return list_tasks(session, chief_id=chief_id, status=TaskStatus.AWAITING_REVIEW)


def supervised_agents(session: Session, chief_id: uuid.UUID) -> list[Agent]:
    """Time sob supervisão direta do Chief."""
    return list(
        session.scalars(
            select(Agent)
            .where(Agent.reports_to_id == chief_id, Agent.status != AgentStatus.TERMINATED)
            .order_by(Agent.created_at)
        )
    )


def build_graph(session: Session, request: InitialRequest) -> dict[str, Any]:
    """Nós (agentes + observador) e arestas do pedido, prontos para o frontend."""
    edges = list_edges(session, request.id)
    tasks = list_tasks(session, request_id=request.id)

    agent_ids = {
        agent_id
        for edge in edges
        for agent_id in (edge.sender_agent_id, edge.recipient_agent_id)
        if agent_id is not None
    }
    agents = (
        list(session.scalars(select(Agent).where(Agent.id.in_(agent_ids)))) if agent_ids else []
    )

    nodes: list[dict[str, Any]] = [
        {
            "id": "observer",
            "name": request.submitted_by,
            "role": "OBSERVER",
            "agent_type": "OBSERVER",
            "status": "IDLE",
            "reports_to": None,
        }
    ]
    nodes.extend(
        {
            "id": str(agent.id),
            "name": agent.name,
            "role": agent.role.value,
            "agent_type": agent.agent_type.value,
            "status": agent.status.value,
            "reports_to": str(agent.reports_to_id) if agent.reports_to_id else None,
        }
        for agent in agents
    )

    return {
        "request_id": str(request.id),
        "topic": request.topic,
        "status": request.status.value,
        "nodes": nodes,
        "edges": [_edge_event(edge) for edge in edges],
        "tasks": [task_event(task) for task in tasks],
    }


def close_request(
    session: Session, request: InitialRequest, *, outcome: str, narrative: str
) -> InitialRequest:
    """Encerra o pedido quando não resta tarefa aberta."""
    request.status = (
        InitialRequestStatus.COMPLETED if outcome != "FAILED" else InitialRequestStatus.FAILED
    )
    request.outcome = outcome
    request.narrative = narrative
    request.resolved_at = utcnow()
    _push_milestone(request, "closed", {"outcome": outcome})

    audit_service.record_event(
        session,
        event_type=AuditEventType.REQUEST_RESOLVED,
        actor=AgentRole.CEO.value,
        decision=outcome,
        summary=f"Pedido encerrado: {request.topic}",
        narrative=narrative,
        payload={"request_id": str(request.id)},
    )
    session.flush()
    _publish("network.request", request_event(request))
    return request


def has_open_tasks(session: Session, request_id: uuid.UUID) -> bool:
    return any(task.is_open for task in list_tasks(session, request_id=request_id))


def request_event(request: InitialRequest) -> dict[str, Any]:
    """Projeção do pedido transmitida por WebSocket."""
    return {
        "id": str(request.id),
        "topic": request.topic,
        "status": request.status.value,
        "outcome": request.outcome,
        "narrative": request.narrative,
    }


def publish_task(task: AgentTask) -> None:
    """Empurra o estado corrente da tarefa para os assinantes do barramento."""
    _publish("network.task", task_event(task))


def task_event(task: AgentTask) -> dict[str, Any]:
    """Projeção da tarefa transmitida por WebSocket e pelos endpoints de grafo."""
    return {
        "id": str(task.id),
        "request_id": str(task.request_id),
        "parent_task_id": str(task.parent_task_id) if task.parent_task_id else None,
        "assigned_by_chief_id": (
            str(task.assigned_by_chief_id) if task.assigned_by_chief_id else None
        ),
        "assigned_to_agent_id": (
            str(task.assigned_to_agent_id) if task.assigned_to_agent_id else None
        ),
        "title": task.title,
        "task_description": task.task_description,
        "status": task.status.value,
        "attempt": task.attempt,
        "quality_score": task.quality_score,
        "decision": task.decision.value if task.decision else None,
        "decision_rationale": task.decision_rationale,
        "report_summary": task.report_summary,
        "report_reasoning_session_id": (
            str(task.report_reasoning_session_id) if task.report_reasoning_session_id else None
        ),
        "review_reasoning_session_id": (
            str(task.review_reasoning_session_id) if task.review_reasoning_session_id else None
        ),
    }


# --- Internos ----------------------------------------------------------------


def _require_supervisor(chief: Agent) -> None:
    if chief.agent_type is not AgentType.CHIEF or chief.role not in SUPERVISING_ROLES:
        msg = (
            f"{chief.name} não é um Chief supervisor. O RA cria agentes, mas nunca delega "
            "nem recebe report."
        )
        raise HierarchyError(msg)


def _edge_event(edge: CommunicationEdge) -> dict[str, Any]:
    """Aresta com o emissor nulo convertido no nó sintético do observador."""
    data = edge.to_dict()
    data["sender_agent_id"] = data["sender_agent_id"] or "observer"
    return data


def _push_milestone(request: InitialRequest, kind: str, data: dict[str, Any]) -> None:
    """`current_state` é JSON: só uma reatribuição marca a coluna como suja."""
    state = dict(request.current_state or {})
    milestones = list(state.get("milestones", []))
    milestones.append({"kind": kind, "at": utcnow().isoformat(), **data})
    state["milestones"] = milestones[-50:]
    request.current_state = state


def _publish(event: str, data: dict[str, Any]) -> None:
    get_broker().publish({"event": event, "data": data})
