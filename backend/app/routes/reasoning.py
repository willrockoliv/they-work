"""Endpoints de observabilidade cognitiva — raio-X do raciocínio dos agentes."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.enums import ReasoningStatus
from app.routes.deps import AppSettings, DbSession, Nature, Ollama
from app.schemas.reasoning import (
    LiveStatusResponse,
    ReasoningExportResponse,
    ReasoningFlowResponse,
    ReasoningMetricsResponse,
    ReasoningRunRequest,
    ReasoningSessionDetail,
    ReasoningSessionRead,
    ReasoningSessionsResponse,
    ReasoningStepRead,
    RetentionPurgeRequest,
    RetentionPurgeResponse,
)
from app.services import react_engine, reasoning_flow, reasoning_metrics, reasoning_service
from app.services.react_engine import TaskRequest

router = APIRouter(tags=["observabilidade"])


def _agent_or_404(session: Session, agent_id: uuid.UUID) -> Agent:
    agent = session.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Agente {agent_id} não encontrado."
        )
    return agent


@router.post(
    "/agents/{agent_id}/reasoning/run",
    response_model=ReasoningSessionDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Executa uma tarefa capturando todo o ciclo ReAct",
)
def run_reasoning(
    agent_id: uuid.UUID,
    payload: ReasoningRunRequest,
    session: DbSession,
    nature: Nature,
    ollama: Ollama,
) -> ReasoningSessionDetail:
    """Cada pensamento, ação e observação é persistido e transmitido ao vivo."""
    agent = _agent_or_404(session, agent_id)
    reasoning = react_engine.run_task(
        session,
        agent=agent,
        request=TaskRequest(
            task=payload.task,
            complexity=payload.complexity,
            thread_id=payload.thread_id,
            max_steps=payload.max_steps,
            context=payload.context,
        ),
        nature=nature,
        ollama=ollama,
    )
    session.commit()
    return _detail(session, reasoning.id)


@router.get(
    "/agents/{agent_id}/reasoning-flow",
    response_model=ReasoningFlowResponse,
    summary="Fluxograma do raciocínio corrente (ou do mais recente) de um agente",
)
def agent_reasoning_flow(agent_id: uuid.UUID, session: DbSession) -> ReasoningFlowResponse:
    _agent_or_404(session, agent_id)
    reasoning = reasoning_service.latest_for_agent(session, agent_id)
    if reasoning is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Este agente ainda não produziu nenhum raciocínio.",
        )
    steps = reasoning_service.list_steps(session, reasoning.id)
    return ReasoningFlowResponse.model_validate(reasoning_flow.build_flow(reasoning, steps))


@router.get(
    "/agents/{agent_id}/live-status",
    response_model=LiveStatusResponse,
    summary="Status ao vivo do agente, com progresso e última ação",
)
def agent_live_status(
    agent_id: uuid.UUID, session: DbSession, settings: AppSettings
) -> LiveStatusResponse:
    agent = _agent_or_404(session, agent_id)
    reasoning = reasoning_service.latest_for_agent(session, agent_id)
    steps = reasoning_service.list_steps(session, reasoning.id) if reasoning else []
    return LiveStatusResponse.model_validate(
        reasoning_flow.build_live_status(
            agent, reasoning, steps, max_steps=settings.reasoning_max_steps
        )
    )


@router.get(
    "/reasoning/sessions",
    response_model=ReasoningSessionsResponse,
    summary="Histórico de sessões de raciocínio",
)
def list_sessions(
    session: DbSession,
    agent_id: uuid.UUID | None = None,
    reasoning_status: ReasoningStatus | None = None,
    limit: int = 50,
) -> ReasoningSessionsResponse:
    sessions = reasoning_service.list_sessions(
        session, agent_id=agent_id, status=reasoning_status, limit=limit
    )
    return ReasoningSessionsResponse(
        total=len(sessions),
        sessions=[ReasoningSessionRead.model_validate(item) for item in sessions],
    )


@router.get(
    "/reasoning/metrics",
    response_model=ReasoningMetricsResponse,
    summary="Painel de métricas cognitivas (tokens, tempo, custo e ROI)",
)
def metrics(session: DbSession, since: datetime | None = None) -> ReasoningMetricsResponse:
    return ReasoningMetricsResponse.model_validate(
        reasoning_metrics.collect(session, since=since).to_dict()
    )


@router.get(
    "/reasoning/export",
    response_model=ReasoningExportResponse,
    summary="Export JSON das sessões para análise externa",
)
def export(
    session: DbSession,
    agent_id: uuid.UUID | None = None,
    since: datetime | None = None,
    limit: int = 100,
) -> ReasoningExportResponse:
    rows = reasoning_metrics.export_sessions(
        session, agent_id=agent_id, since=since, limit=limit
    )
    return ReasoningExportResponse(total=len(rows), sessions=rows)


@router.post(
    "/reasoning/retention/purge",
    response_model=RetentionPurgeResponse,
    summary="Aplica a política de retenção, arquivando raciocínios antigos",
)
def purge(
    payload: RetentionPurgeRequest, session: DbSession, settings: AppSettings
) -> RetentionPurgeResponse:
    removed = reasoning_metrics.purge_sessions(session, before=payload.before, settings=settings)
    session.commit()
    return RetentionPurgeResponse(
        removed=removed, retention_days=settings.reasoning_retention_days
    )


@router.get(
    "/reasoning/sessions/{session_id}",
    response_model=ReasoningSessionDetail,
    summary="Replay completo de uma sessão de raciocínio",
)
def get_session(session_id: uuid.UUID, session: DbSession) -> ReasoningSessionDetail:
    return _detail(session, session_id)


@router.get(
    "/reasoning/sessions/{session_id}/flow",
    response_model=ReasoningFlowResponse,
    summary="Fluxograma de uma sessão específica",
)
def session_flow(session_id: uuid.UUID, session: DbSession) -> ReasoningFlowResponse:
    reasoning = reasoning_service.get_session(session, session_id)
    if reasoning is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Sessão {session_id} não encontrada."
        )
    steps = reasoning_service.list_steps(session, session_id)
    return ReasoningFlowResponse.model_validate(reasoning_flow.build_flow(reasoning, steps))


def _detail(session: Session, session_id: uuid.UUID) -> ReasoningSessionDetail:
    reasoning = reasoning_service.get_session(session, session_id)
    if reasoning is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Sessão {session_id} não encontrada."
        )
    steps = reasoning_service.list_steps(session, session_id)
    detail = ReasoningSessionDetail.model_validate(reasoning)
    detail.steps = [ReasoningStepRead.model_validate(step) for step in steps]
    return detail
