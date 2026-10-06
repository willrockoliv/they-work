"""Reconvocação não deve empilhar prefixos no título da tarefa."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.models.enums import AgentRole, ChiefDecision, TaskStatus
from app.services import (
    agent_decision_engine,
    agent_service,
    communication_service,
    council_service,
)
from app.services.communication_service import DelegationIntake, RequestIntake
from app.services.nature_manager import NatureManager
from app.services.ra_service import HiringIntake


@pytest.fixture
def booted(db_session: Session) -> Session:
    agent_service.init_chiefs(db_session)
    council_service.init_profiles(db_session)
    db_session.flush()
    return db_session


def test_titulo_nao_empilha_prefixo_de_reconvocacao(
    booted: Session, nature: NatureManager
) -> None:
    request = communication_service.submit_request(
        booted, RequestIntake(topic="Fundar", description="Produto para advogados.")
    )
    cmo = agent_service.get_chief(booted, AgentRole.CMO)
    assert cmo is not None
    agent = communication_service.request_agent(
        booted,
        nature,
        request,
        cmo,
        HiringIntake(
            requested_by=AgentRole.CMO,
            job_title="Analista de Mercado",
            objective="Mapear personas e concorrentes do segmento juridico de medio porte",
            deliverables=("Mapa de personas",),
        ),
    ).agent
    assert agent is not None

    task = communication_service.delegate_task(
        booted,
        request,
        cmo,
        agent,
        DelegationIntake(title="Frente de mercado", task_description="Mapear personas"),
    )

    for _ in range(3):
        task.status = TaskStatus.AWAITING_REVIEW
        task.reviewed_at = None
        task.report_summary = "Nao deu."
        booted.flush()
        result = agent_decision_engine.review_and_decide(booted, task, nature=nature)
        if result.follow_up is None:
            break
        assert result.decision in (ChiefDecision.REJECT, ChiefDecision.MODIFY)
        task = result.follow_up

    tasks = communication_service.list_tasks(booted, request_id=request.id)
    for title in (item.title for item in tasks):
        assert title.count("[Refazer]") <= 1
        assert title.count("[Ajuste]") <= 1
        assert "[Refazer] [Refazer]" not in title
