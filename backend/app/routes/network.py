"""Endpoints da rede corporativa — pedidos, grafo, delegação e vereditos dos Chiefs."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import Connection, Engine, select
from sqlalchemy.orm import Session

from app.config.logging import get_logger
from app.models.agent import Agent
from app.models.enums import AgentRole, AgentType, TaskStatus
from app.models.network import AgentTask, InitialRequest
from app.routes.deps import DbSession, Nature, Ollama
from app.schemas.agents import AgentRead
from app.schemas.network import (
    AgentTaskRead,
    AgentTasksResponse,
    BootstrapResponse,
    CreateAgentRequest,
    CreateAgentResponse,
    CreatedAgentsResponse,
    DelegateTaskRequest,
    InitialRequestRead,
    InitialRequestsResponse,
    RequestActionCreate,
    RequestDetailResponse,
    RequestGraphResponse,
    ReviewDecisionResponse,
    RunCycleResponse,
    StartCycleResponse,
    SupervisedAgentsResponse,
)
from app.services import (
    agent_decision_engine,
    agent_service,
    communication_service,
    council_service,
    network_orchestrator,
)
from app.services.agent_decision_engine import ReviewResult
from app.services.communication_service import (
    CompanyNotFoundedError,
    DelegationIntake,
    HierarchyError,
    RequestIntake,
)
from app.services.nature_manager import NatureManager
from app.services.ollama_client import OllamaClient
from app.services.ra_service import HiringIntake

logger = get_logger(__name__)

router = APIRouter(tags=["rede corporativa"])


def _request_or_404(session: Session, request_id: uuid.UUID) -> InitialRequest:
    request = session.get(InitialRequest, request_id)
    if request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Pedido {request_id} não encontrado."
        )
    return request


def _task_or_404(session: Session, task_id: uuid.UUID) -> AgentTask:
    task = session.get(AgentTask, task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Tarefa {task_id} não encontrada."
        )
    return task


def _chief_or_404(session: Session, chief_id: uuid.UUID) -> Agent:
    chief = session.get(Agent, chief_id)
    if chief is None or chief.agent_type is not AgentType.CHIEF:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Chief {chief_id} não encontrado."
        )
    return chief


def _graph(session: Session, request: InitialRequest) -> RequestGraphResponse:
    return RequestGraphResponse.model_validate(communication_service.build_graph(session, request))


def _review_response(result: ReviewResult) -> ReviewDecisionResponse:
    return ReviewDecisionResponse(
        task=AgentTaskRead.model_validate(result.task),
        decision=result.decision,
        rationale=result.rationale,
        quality_score=result.assessment.quality.score,
        achievement_ratio=round(result.assessment.comparison.achievement_ratio, 3),
        risk_level=result.assessment.risk_level,
        assessment=result.assessment.to_dict(),
        review_reasoning_session_id=result.reasoning.id if result.reasoning else None,
        follow_up_task=(
            AgentTaskRead.model_validate(result.follow_up) if result.follow_up else None
        ),
        consulted_roles=list(result.consulted_roles),
        escalated_to_ceo=result.escalated_to_ceo,
    )


# --- Fundação da empresa -----------------------------------------------------


@router.post(
    "/company/bootstrap",
    response_model=BootstrapResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Funda a empresa: cria os Chiefs e materializa as personas do conselho",
)
def bootstrap(session: DbSession) -> BootstrapResponse:
    """Idempotente. Faz os dois passos juntos: só `chiefs/init` deixa o conselho sem persona."""
    before = len(agent_service.list_agents(session, agent_type=AgentType.CHIEF))
    chiefs = agent_service.init_chiefs(session)
    profiles = council_service.init_profiles(session)
    session.commit()
    return BootstrapResponse(
        created=len(chiefs) - before,
        total=len(chiefs),
        profiles=len(profiles),
        chiefs=[AgentRead.model_validate(agent) for agent in chiefs],
    )


@router.get(
    "/company/status",
    response_model=BootstrapResponse,
    summary="Diz se a empresa já foi fundada",
)
def company_status(session: DbSession) -> BootstrapResponse:
    chiefs = agent_service.list_agents(session, agent_type=AgentType.CHIEF)
    return BootstrapResponse(
        created=0,
        total=len(chiefs),
        profiles=len(council_service.list_profiles(session)),
        chiefs=[AgentRead.model_validate(agent) for agent in chiefs],
    )


# --- Pedidos -----------------------------------------------------------------


@router.post(
    "/council/request-action",
    response_model=RequestDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submete um pedido estratégico ao conselho",
)
def request_action(payload: RequestActionCreate, session: DbSession) -> RequestDetailResponse:
    """Abre o grafo com a aresta observador → CEO e, por padrão, já delibera."""
    try:
        request = communication_service.submit_request(
            session,
            RequestIntake(
                topic=payload.topic,
                description=payload.description,
                submitted_by=payload.submitted_by,
            ),
        )
    except CompanyNotFoundedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if payload.auto_deliberate:
        communication_service.deliberate(session, request)
    session.commit()
    return RequestDetailResponse(
        request=InitialRequestRead.model_validate(request), graph=_graph(session, request)
    )


@router.get(
    "/council/requests",
    response_model=InitialRequestsResponse,
    summary="Pedidos submetidos ao conselho",
)
def list_requests(session: DbSession, limit: int = 50) -> InitialRequestsResponse:
    requests = communication_service.list_requests(session, limit=limit)
    return InitialRequestsResponse(
        total=len(requests),
        requests=[InitialRequestRead.model_validate(item) for item in requests],
    )


@router.get(
    "/council/requests/{request_id}",
    response_model=RequestDetailResponse,
    summary="Pedido com o grafo de comunicações que ele gerou",
)
def get_request(request_id: uuid.UUID, session: DbSession) -> RequestDetailResponse:
    request = _request_or_404(session, request_id)
    return RequestDetailResponse(
        request=InitialRequestRead.model_validate(request), graph=_graph(session, request)
    )


@router.get(
    "/council/requests/{request_id}/graph",
    response_model=RequestGraphResponse,
    summary="DAG de comunicações do pedido",
)
def get_request_graph(request_id: uuid.UUID, session: DbSession) -> RequestGraphResponse:
    return _graph(session, _request_or_404(session, request_id))


@router.post(
    "/council/requests/{request_id}/run-cycle",
    response_model=RunCycleResponse,
    summary="Avança o pedido um turno completo (staffing, execução e revisão)",
)
def run_cycle(
    request_id: uuid.UUID, session: DbSession, nature: Nature, ollama: Ollama
) -> RunCycleResponse:
    """Modo automático: Chiefs contratam, delegam, recebem reports e decidem."""
    request = _request_or_404(session, request_id)
    try:
        result = network_orchestrator.run_cycle(session, request, nature=nature, ollama=ollama)
    except HierarchyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.commit()
    return RunCycleResponse(
        request=InitialRequestRead.model_validate(request),
        executed_tasks=len(result.executed),
        reviews=[_review_response(review) for review in result.reviews],
        graph=_graph(session, request),
    )


@router.post(
    "/council/requests/{request_id}/start",
    response_model=StartCycleResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Põe os agentes para trabalhar em segundo plano",
)
def start_cycle(
    request_id: uuid.UUID, session: DbSession, nature: Nature, tasks: BackgroundTasks
) -> StartCycleResponse:
    """Devolve na hora e trabalha depois.

    Um turno com inferência real encadeia várias sessões ReAct e leva minutos; segurar
    a conexão até o fim deixaria a interface travada. O progresso chega pelos eventos
    `network.*` do `WS /ws/game-state`.
    """
    request = _request_or_404(session, request_id)
    already = network_orchestrator.is_running(request_id)
    if not already:
        # O engine sai da própria sessão da requisição: a tarefa fala com o mesmo banco,
        # inclusive quando os testes substituem a dependência por um SQLite em memória.
        tasks.add_task(_run_cycle_detached, request_id, nature, session.get_bind())
    return StartCycleResponse(
        request=InitialRequestRead.model_validate(request), started=not already
    )


def _run_cycle_detached(
    request_id: uuid.UUID, nature: NatureManager, bind: Engine | Connection
) -> None:
    """Turno fora do ciclo de vida da requisição HTTP, com sessão própria.

    Commita a cada etapa: é isso que faz o grafo aparecer aos poucos no frontend em
    vez de surgir inteiro no fim.
    """
    with network_orchestrator.turn(request_id) as acquired:
        if not acquired:  # pragma: no cover - corrida entre dois cliques
            return
        session = Session(bind=bind, autoflush=False, expire_on_commit=False)
        try:
            request = session.get(InitialRequest, request_id)
            if request is None:  # pragma: no cover - removido antes de executar
                return
            logger.info("network.cycle_started", request_id=str(request_id))
            result = network_orchestrator.run_cycle(
                session,
                request,
                nature=nature,
                ollama=OllamaClient(),
                on_step=session.commit,
            )
            session.commit()
            logger.info(
                "network.cycle_finished",
                request_id=str(request_id),
                executed=len(result.executed),
                reviews=len(result.reviews),
            )
        except Exception:
            session.rollback()
            logger.exception("network.cycle_failed", request_id=str(request_id))
        finally:
            session.close()


# --- RA: criação de agentes --------------------------------------------------


@router.post(
    "/ra/create-agent",
    response_model=CreateAgentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Chief solicita ao RA a criação de um agente especializado",
)
def create_agent(
    payload: CreateAgentRequest, session: DbSession, nature: Nature
) -> CreateAgentResponse:
    """Só Chiefs supervisores pedem; o agente criado já nasce reportando ao solicitante."""
    request = _request_or_404(session, payload.request_id)
    chief = agent_service.get_chief(session, payload.requesting_chief)
    if chief is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chief {payload.requesting_chief.value} não inicializado.",
        )

    try:
        outcome = communication_service.request_agent(
            session,
            nature,
            request,
            chief,
            HiringIntake(
                requested_by=payload.requesting_chief,
                job_title=payload.job_title,
                objective=payload.objective,
                raw_request=payload.objective,
                deliverables=tuple(payload.deliverables),
                tools=tuple(payload.tools),
                constraints=tuple(payload.constraints),
                specialization=payload.specialization,
                complexity=payload.complexity,
            ),
        )
    except HierarchyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    session.commit()
    return CreateAgentResponse(
        hiring_request_id=outcome.request.id,
        agent=AgentRead.model_validate(outcome.agent) if outcome.agent else None,
        reporting_chief=payload.requesting_chief,
        reused_profile=outcome.reused_profile,
        questions=list(outcome.questions),
        narrative=outcome.narrative,
    )


@router.get(
    "/ra/created-agents",
    response_model=CreatedAgentsResponse,
    summary="Histórico dos agentes instanciados pelo RA",
)
def created_agents(session: DbSession, limit: int = 50) -> CreatedAgentsResponse:
    agents = list(
        session.scalars(
            select(Agent)
            .where(Agent.agent_type == AgentType.SUBAGENT)
            .order_by(Agent.created_at.desc())
            .limit(limit)
        )
    )
    return CreatedAgentsResponse(
        total=len(agents), agents=[AgentRead.model_validate(agent) for agent in agents]
    )


# --- Tarefas -----------------------------------------------------------------


@router.get(
    "/agents/{agent_id}/tasks",
    response_model=AgentTasksResponse,
    summary="Tarefas atribuídas a um agente",
)
def agent_tasks(
    agent_id: uuid.UUID, session: DbSession, task_status: TaskStatus | None = None
) -> AgentTasksResponse:
    tasks = communication_service.list_tasks(session, agent_id=agent_id, status=task_status)
    return AgentTasksResponse(
        total=len(tasks), tasks=[AgentTaskRead.model_validate(task) for task in tasks]
    )


@router.post(
    "/agents/{agent_id}/tasks/{task_id}/report",
    response_model=AgentTaskRead,
    summary="Agente executa a tarefa e reporta ao seu Chief supervisor",
)
def report_task(
    agent_id: uuid.UUID,
    task_id: uuid.UUID,
    session: DbSession,
    nature: Nature,
    ollama: Ollama,
) -> AgentTaskRead:
    task = _task_or_404(session, task_id)
    if task.assigned_to_agent_id != agent_id:
        raise HTTPException(status_code=409, detail="A tarefa não pertence a este agente.")
    try:
        communication_service.execute_task(session, task, nature=nature, ollama=ollama)
    except HierarchyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.commit()
    return AgentTaskRead.model_validate(task)


# --- Chiefs ------------------------------------------------------------------


@router.get(
    "/chiefs/{chief_id}/supervised-agents",
    response_model=SupervisedAgentsResponse,
    summary="Time sob supervisão direta do Chief",
)
def supervised_agents(chief_id: uuid.UUID, session: DbSession) -> SupervisedAgentsResponse:
    chief = _chief_or_404(session, chief_id)
    agents = communication_service.supervised_agents(session, chief.id)
    return SupervisedAgentsResponse(
        total=len(agents),
        chief=chief.role,
        agents=[AgentRead.model_validate(agent) for agent in agents],
    )


@router.get(
    "/chiefs/{chief_id}/pending-reviews",
    response_model=AgentTasksResponse,
    summary="Reports dos subordinados aguardando o veredito do Chief",
)
def pending_reviews(chief_id: uuid.UUID, session: DbSession) -> AgentTasksResponse:
    chief = _chief_or_404(session, chief_id)
    tasks = communication_service.pending_reviews(session, chief.id)
    return AgentTasksResponse(
        total=len(tasks), tasks=[AgentTaskRead.model_validate(task) for task in tasks]
    )


@router.post(
    "/chiefs/{chief_id}/delegate",
    response_model=AgentTaskRead,
    status_code=status.HTTP_201_CREATED,
    summary="Chief delega uma tarefa a um agente do próprio time",
)
def delegate(
    chief_id: uuid.UUID, payload: DelegateTaskRequest, session: DbSession
) -> AgentTaskRead:
    chief = _chief_or_404(session, chief_id)
    request = _request_or_404(session, payload.request_id)
    agent = session.get(Agent, payload.agent_id)
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agente {payload.agent_id} não encontrado.",
        )
    try:
        task = communication_service.delegate_task(
            session,
            request,
            chief,
            agent,
            DelegationIntake(
                title=payload.title,
                task_description=payload.task_description,
                acceptance_criteria=tuple(payload.acceptance_criteria),
                context=payload.context,
            ),
        )
    except HierarchyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.commit()
    return AgentTaskRead.model_validate(task)


@router.post(
    "/chiefs/{chief_id}/tasks/{task_id}/review-and-decide",
    response_model=ReviewDecisionResponse,
    summary="Chief supervisor analisa o report e aplica o veredito",
)
def review_and_decide(
    chief_id: uuid.UUID,
    task_id: uuid.UUID,
    session: DbSession,
    nature: Nature,
    ollama: Ollama,
) -> ReviewDecisionResponse:
    """Decide entre APPROVE, REJECT, MODIFY, CONSULT_PEERS e ESCALATE."""
    chief = _chief_or_404(session, chief_id)
    task = _task_or_404(session, task_id)
    if task.assigned_by_chief_id != chief.id:
        raise HTTPException(
            status_code=409, detail="Só o Chief que delegou a tarefa pode revisá-la."
        )
    try:
        result = agent_decision_engine.review_and_decide(
            session, task, nature=nature, ollama=ollama
        )
    except HierarchyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.commit()
    return _review_response(result)


@router.post(
    "/ceo/final-decision/{task_id}",
    response_model=ReviewDecisionResponse,
    summary="CEO dá a palavra final sobre uma tarefa escalada",
)
def ceo_final_decision(
    task_id: uuid.UUID, session: DbSession, nature: Nature, ollama: Ollama
) -> ReviewDecisionResponse:
    task = _task_or_404(session, task_id)
    if agent_service.get_chief(session, AgentRole.CEO) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="O CEO não foi inicializado."
        )
    try:
        result = agent_decision_engine.ceo_final_decision(
            session, task, nature=nature, ollama=ollama
        )
    except HierarchyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.commit()
    return _review_response(result)
