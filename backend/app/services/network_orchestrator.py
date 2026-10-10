"""Orquestrador do ciclo automático da rede corporativa.

Encadeia o que a Fase 5 descreve como um único turno do grafo: deliberação do
conselho → cada Chief pede o agente que lhe falta ao RA → delega ao próprio time →
o agente executa e reporta → o Chief revisa e decide. Chamar de novo avança o
próximo turno (reconvocações, subtarefas, desempate do CEO).
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.config.logging import get_logger
from app.models.agent import Agent
from app.models.enums import (
    AgentRole,
    ChiefDecision,
    InitialRequestStatus,
    TaskComplexity,
    TaskStatus,
)
from app.models.network import AgentTask, InitialRequest
from app.services import agent_decision_engine, agent_service, communication_service
from app.services.agent_decision_engine import ReviewResult
from app.services.communication_service import DelegationIntake
from app.services.nature_manager import NatureManager
from app.services.ollama_client import OllamaClient
from app.services.ra_service import HiringIntake

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class FrontBlueprint:
    """Frente de trabalho padrão de uma diretoria num pedido novo."""

    role: AgentRole
    area: str
    job_title: str
    specialization: str
    deliverables: tuple[str, ...]
    tools: tuple[str, ...]
    complexity: TaskComplexity


FRONTS: tuple[FrontBlueprint, ...] = (
    FrontBlueprint(
        role=AgentRole.CTO,
        area="tecnologia",
        job_title="Engenheiro de Software",
        specialization="backend e arquitetura",
        deliverables=("Desenho da arquitetura", "Plano de testes", "Riscos técnicos"),
        tools=("memoria_corporativa", "infraestrutura"),
        complexity=TaskComplexity.COMPLEX,
    ),
    FrontBlueprint(
        role=AgentRole.CMO,
        area="mercado",
        job_title="Analista de Mercado",
        specialization="pesquisa e go-to-market",
        deliverables=("Mapa de personas", "Análise de concorrentes", "Plano de canais"),
        tools=("memoria_corporativa",),
        complexity=TaskComplexity.MODERATE,
    ),
    FrontBlueprint(
        role=AgentRole.CFO,
        area="finanças",
        job_title="Analista Financeiro",
        specialization="modelagem financeira",
        deliverables=("Projeção de receita", "Estrutura de custos", "Ponto de equilíbrio"),
        tools=("calculadora", "memoria_corporativa"),
        complexity=TaskComplexity.MODERATE,
    ),
)

#: Vereditos que deixam a tarefa em aberto até o desempate do CEO.
_CEO_TIEBREAK_DECISIONS: frozenset[ChiefDecision] = frozenset(
    {ChiefDecision.ESCALATE, ChiefDecision.CONSULT_PEERS}
)


@dataclass(frozen=True, slots=True)
class CycleResult:
    """O que o turno produziu."""

    request: InitialRequest
    deliberated: bool = False
    created_agents: tuple[Agent, ...] = field(default_factory=tuple)
    delegated: tuple[AgentTask, ...] = field(default_factory=tuple)
    executed: tuple[AgentTask, ...] = field(default_factory=tuple)
    reviews: tuple[ReviewResult, ...] = field(default_factory=tuple)
    tiebreaks: tuple[ReviewResult, ...] = field(default_factory=tuple)


#: Turnos em andamento neste processo. Um turno leva minutos com inferência real;
#: sem esta guarda cada clique empilharia outro, duplicando trabalho e esgotando o
#: threadpool do servidor.
_running: set[uuid.UUID] = set()
_running_lock = threading.Lock()


def is_running(request_id: uuid.UUID) -> bool:
    with _running_lock:
        return request_id in _running


@contextmanager
def turn(request_id: uuid.UUID) -> Iterator[bool]:
    """Reserva o turno do pedido. Entrega `False` se já havia um em andamento."""
    with _running_lock:
        acquired = request_id not in _running
        if acquired:
            _running.add(request_id)
    try:
        yield acquired
    finally:
        if acquired:
            with _running_lock:
                _running.discard(request_id)


def run_cycle(
    session: Session,
    request: InitialRequest,
    *,
    nature: NatureManager,
    ollama: OllamaClient | None = None,
    on_step: Callable[[], None] | None = None,
) -> CycleResult:
    """Avança o pedido um turno completo no grafo.

    `on_step` é chamado ao fim de cada etapa. Em execução de fundo a rota passa
    `session.commit`, para que o frontend veja o grafo crescer em vez de receber
    tudo de uma vez no fim do turno.
    """
    deliberated = False
    if request.status is InitialRequestStatus.PROPOSED:
        communication_service.deliberate(session, request)
        deliberated = True
        _notify(on_step)

    created, delegated = _staff_and_delegate(session, request, nature=nature)
    _notify(on_step)

    executed: list[AgentTask] = []
    for task in communication_service.list_tasks(session, request_id=request.id):
        if task.status in (TaskStatus.PENDING, TaskStatus.ACKNOWLEDGED):
            communication_service.execute_task(session, task, nature=nature, ollama=ollama)
            executed.append(task)
            _notify(on_step)

    reviews: list[ReviewResult] = []
    for task in communication_service.list_tasks(
        session, request_id=request.id, status=TaskStatus.AWAITING_REVIEW
    ):
        if task.reviewed_at is not None:
            # Já revisada e à espera de pares ou do CEO: não revisa de novo no mesmo turno.
            continue
        reviews.append(
            agent_decision_engine.review_and_decide(session, task, nature=nature, ollama=ollama)
        )
        _notify(on_step)

    # Sem este passo, uma tarefa escalada ou em consulta ficaria parada para sempre:
    # o Chief já revisou (reviewed_at preenchido) e a revisão não roda de novo.
    tiebreaks: list[ReviewResult] = []
    for task in communication_service.list_tasks(
        session, request_id=request.id, status=TaskStatus.AWAITING_REVIEW
    ):
        if task.decision not in _CEO_TIEBREAK_DECISIONS:
            continue
        tiebreaks.append(
            agent_decision_engine.ceo_final_decision(session, task, nature=nature, ollama=ollama)
        )
        _notify(on_step)

    session.flush()
    logger.info(
        "network.cycle_completed",
        request_id=str(request.id),
        created=len(created),
        delegated=len(delegated),
        executed=len(executed),
        reviews=len(reviews),
        tiebreaks=len(tiebreaks),
    )
    return CycleResult(
        request=request,
        deliberated=deliberated,
        created_agents=tuple(created),
        delegated=tuple(delegated),
        executed=tuple(executed),
        reviews=tuple(reviews),
        tiebreaks=tuple(tiebreaks),
    )


def _staff_and_delegate(
    session: Session, request: InitialRequest, *, nature: NatureManager
) -> tuple[list[Agent], list[AgentTask]]:
    """Cada diretoria sem tarefa aberta pede um agente ao RA e delega sua frente."""
    created: list[Agent] = []
    delegated: list[AgentTask] = []

    for front in FRONTS:
        chief = agent_service.get_chief(session, front.role)
        if chief is None:
            continue
        if any(task.is_open for task in communication_service.list_tasks(
            session, request_id=request.id, chief_id=chief.id
        )):
            continue

        agent, hired = _pick_or_hire(session, request, chief, front, nature=nature)
        if agent is None:
            continue
        if hired:
            created.append(agent)

        delegated.append(
            communication_service.delegate_task(
                session,
                request,
                chief,
                agent,
                DelegationIntake(
                    title=f"Frente de {front.area}: {request.topic}"[:160],
                    task_description=(
                        f"Conduzir a frente de {front.area} do pedido '{request.topic}'. "
                        f"Contexto: {request.description} Entregue: "
                        f"{', '.join(front.deliverables)}."
                    ),
                    acceptance_criteria=front.deliverables,
                    context={"area": front.area, "chief": front.role.value},
                ),
            )
        )

    return created, delegated


def _pick_or_hire(
    session: Session,
    request: InitialRequest,
    chief: Agent,
    front: FrontBlueprint,
    *,
    nature: NatureManager,
) -> tuple[Agent | None, bool]:
    """Reaproveita um subordinado ocioso do Chief ou pede um novo ao RA."""
    team = communication_service.supervised_agents(session, chief.id)
    idle = [agent for agent in team if not _has_open_task(session, agent)]
    if idle:
        return idle[0], False

    outcome = communication_service.request_agent(
        session,
        nature,
        request,
        chief,
        HiringIntake(
            requested_by=front.role,
            job_title=front.job_title,
            objective=(
                f"Conduzir a frente de {front.area} do pedido '{request.topic}' e entregar "
                f"{', '.join(front.deliverables)} dentro das restrições da empresa."
            ),
            raw_request=request.description,
            deliverables=front.deliverables,
            tools=front.tools,
            specialization=front.specialization,
            complexity=front.complexity,
        ),
    )
    return outcome.agent, outcome.agent is not None


def _has_open_task(session: Session, agent: Agent) -> bool:
    return any(
        task.is_open for task in communication_service.list_tasks(session, agent_id=agent.id)
    )


def _notify(on_step: Callable[[], None] | None) -> None:
    if on_step is not None:
        on_step()
