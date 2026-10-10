"""Rede corporativa — grafo de comunicações, hierarquia e motor de decisão."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.base import utcnow
from app.models.enums import (
    AgentRole,
    AgentType,
    ChiefDecision,
    CommunicationType,
    InitialRequestStatus,
    TaskStatus,
)
from app.services import (
    agent_decision_engine,
    agent_service,
    communication_service,
    council_service,
    network_orchestrator,
)
from app.services.communication_service import (
    DelegationIntake,
    HierarchyError,
    RequestIntake,
)
from app.services.nature_manager import NatureManager
from app.services.ra_service import HiringIntake

TOPIC = "Fundar uma startup de triagem documental"
DESCRIPTION = (
    "Queremos lançar um produto de automação de triagem documental para escritórios "
    "de advocacia de médio porte. O mercado é carente, a persona é o sócio operacional "
    "e a receita vem de uma assinatura mensal por usuário, com custo de inferência local."
)


@pytest.fixture
def bootstrapped(db_session: Session) -> Session:
    """Chiefs e perfis do conselho materializados, como no boot real."""
    agent_service.init_chiefs(db_session)
    council_service.init_profiles(db_session)
    db_session.flush()
    return db_session


def _submit(session: Session) -> object:
    return communication_service.submit_request(
        session, RequestIntake(topic=TOPIC, description=DESCRIPTION)
    )


def _hire_for(session: Session, nature: NatureManager, request: object, role: AgentRole) -> Agent:
    chief = agent_service.get_chief(session, role)
    assert chief is not None
    outcome = communication_service.request_agent(
        session,
        nature,
        request,  # type: ignore[arg-type]
        chief,
        HiringIntake(
            requested_by=role,
            job_title="Analista de Mercado",
            objective="Mapear personas e concorrentes do segmento juridico de medio porte",
            deliverables=("Mapa de personas", "Analise de concorrentes"),
            specialization="pesquisa de mercado",
        ),
    )
    assert outcome.agent is not None
    return outcome.agent


# --- Pedidos e grafo ---------------------------------------------------------


def test_pedido_abre_o_grafo_com_aresta_do_observador(bootstrapped: Session) -> None:
    request = _submit(bootstrapped)
    edges = communication_service.list_edges(bootstrapped, request.id)

    assert request.status is InitialRequestStatus.PROPOSED
    assert len(edges) == 1
    assert edges[0].communication_type is CommunicationType.REQUEST
    assert edges[0].sender_agent_id is None  # observador não é um agente
    ceo = agent_service.get_chief(bootstrapped, AgentRole.CEO)
    assert ceo is not None
    assert edges[0].recipient_agent_id == ceo.id


def test_deliberacao_registra_opinioes_e_coordenacao(bootstrapped: Session) -> None:
    request = _submit(bootstrapped)
    decision = communication_service.deliberate(bootstrapped, request)

    kinds = [edge.communication_type for edge in communication_service.list_edges(
        bootstrapped, request.id
    )]
    assert kinds.count(CommunicationType.OPINION) == 3
    assert kinds.count(CommunicationType.COORDINATION) == 3
    assert request.thread_id == decision.thread_id
    assert request.status is InitialRequestStatus.DELIBERATING


def test_grafo_tem_no_sintetico_do_observador(bootstrapped: Session) -> None:
    request = _submit(bootstrapped)
    communication_service.deliberate(bootstrapped, request)
    graph = communication_service.build_graph(bootstrapped, request)

    assert graph["nodes"][0]["id"] == "observer"
    assert graph["edges"][0]["sender_agent_id"] == "observer"


# --- Hierarquia: o RA cria, mas nunca supervisiona ---------------------------


def test_agente_criado_pelo_ra_reporta_ao_chief_solicitante(
    bootstrapped: Session, nature: NatureManager
) -> None:
    request = _submit(bootstrapped)
    agent = _hire_for(bootstrapped, nature, request, AgentRole.CMO)

    cmo = agent_service.get_chief(bootstrapped, AgentRole.CMO)
    ra = agent_service.get_chief(bootstrapped, AgentRole.RA)
    assert cmo is not None and ra is not None
    assert agent.reports_to_id == cmo.id
    assert agent.reports_to_id != ra.id

    types = [
        edge.communication_type
        for edge in communication_service.list_edges(bootstrapped, request.id)
    ]
    assert CommunicationType.AGENT_REQUEST in types
    assert CommunicationType.AGENT_CREATED in types


def test_ra_nao_pode_delegar(bootstrapped: Session, nature: NatureManager) -> None:
    request = _submit(bootstrapped)
    agent = _hire_for(bootstrapped, nature, request, AgentRole.CMO)
    ra = agent_service.get_chief(bootstrapped, AgentRole.RA)
    assert ra is not None

    with pytest.raises(HierarchyError, match="Chief supervisor"):
        communication_service.delegate_task(
            bootstrapped,
            request,
            ra,
            agent,
            DelegationIntake(title="Qualquer", task_description="Fazer algo."),
        )


def test_chief_nao_delega_para_time_alheio(
    bootstrapped: Session, nature: NatureManager
) -> None:
    request = _submit(bootstrapped)
    agent = _hire_for(bootstrapped, nature, request, AgentRole.CMO)
    cto = agent_service.get_chief(bootstrapped, AgentRole.CTO)
    assert cto is not None

    with pytest.raises(HierarchyError, match="não reporta"):
        communication_service.delegate_task(
            bootstrapped,
            request,
            cto,
            agent,
            DelegationIntake(title="Qualquer", task_description="Fazer algo."),
        )


def test_ra_nao_pode_pedir_agente_a_si_mesmo(bootstrapped: Session, nature: NatureManager) -> None:
    request = _submit(bootstrapped)
    ra = agent_service.get_chief(bootstrapped, AgentRole.RA)
    assert ra is not None

    with pytest.raises(HierarchyError):
        communication_service.request_agent(
            bootstrapped,
            nature,
            request,
            ra,
            HiringIntake(requested_by=AgentRole.RA, job_title="Dev"),
        )


# --- Delegação, report e revisão ---------------------------------------------


def test_ciclo_delegar_executar_reportar(
    bootstrapped: Session, nature: NatureManager
) -> None:
    request = _submit(bootstrapped)
    agent = _hire_for(bootstrapped, nature, request, AgentRole.CMO)
    cmo = agent_service.get_chief(bootstrapped, AgentRole.CMO)
    assert cmo is not None

    task = communication_service.delegate_task(
        bootstrapped,
        request,
        cmo,
        agent,
        DelegationIntake(
            title="Frente de mercado",
            task_description="Mapear personas e concorrentes do segmento juridico",
            acceptance_criteria=("Mapa de personas",),
        ),
    )
    assert task.status is TaskStatus.PENDING
    assert request.status is InitialRequestStatus.IN_EXECUTION

    # Sem Ollama o motor cai no planejador determinístico — é o caminho offline.
    communication_service.execute_task(bootstrapped, task, nature=nature)

    assert task.status is TaskStatus.AWAITING_REVIEW
    assert task.report_reasoning_session_id is not None
    assert task.report_summary
    assert communication_service.pending_reviews(bootstrapped, cmo.id) == [task]


def test_revisao_do_chief_fecha_o_ciclo(
    bootstrapped: Session, nature: NatureManager
) -> None:
    request = _submit(bootstrapped)
    agent = _hire_for(bootstrapped, nature, request, AgentRole.CMO)
    cmo = agent_service.get_chief(bootstrapped, AgentRole.CMO)
    assert cmo is not None

    task = communication_service.delegate_task(
        bootstrapped,
        request,
        cmo,
        agent,
        DelegationIntake(title="Frente de mercado", task_description="Mapear personas"),
    )
    communication_service.execute_task(bootstrapped, task, nature=nature)
    result = agent_decision_engine.review_and_decide(bootstrapped, task, nature=nature)

    assert result.decision in set(ChiefDecision)
    assert task.review_reasoning_session_id is not None
    assert task.decision is result.decision
    assert task.quality_score == result.assessment.quality.score

    types = [
        edge.communication_type
        for edge in communication_service.list_edges(bootstrapped, request.id)
    ]
    assert CommunicationType.REPORT in types
    assert CommunicationType.DECISION in types


def test_revisao_exige_tarefa_aguardando_veredito(
    bootstrapped: Session, nature: NatureManager
) -> None:
    request = _submit(bootstrapped)
    agent = _hire_for(bootstrapped, nature, request, AgentRole.CMO)
    cmo = agent_service.get_chief(bootstrapped, AgentRole.CMO)
    assert cmo is not None
    task = communication_service.delegate_task(
        bootstrapped,
        request,
        cmo,
        agent,
        DelegationIntake(title="Frente", task_description="Mapear personas"),
    )

    with pytest.raises(HierarchyError, match="não está aguardando revisão"):
        agent_decision_engine.review_and_decide(bootstrapped, task, nature=nature)


def test_rejeicao_reconvoca_o_mesmo_agente(
    bootstrapped: Session, nature: NatureManager
) -> None:
    request = _submit(bootstrapped)
    agent = _hire_for(bootstrapped, nature, request, AgentRole.CMO)
    cmo = agent_service.get_chief(bootstrapped, AgentRole.CMO)
    assert cmo is not None
    task = communication_service.delegate_task(
        bootstrapped,
        request,
        cmo,
        agent,
        DelegationIntake(title="Frente", task_description="Mapear personas"),
    )
    task.status = TaskStatus.AWAITING_REVIEW
    task.report_summary = "Nao deu."
    bootstrapped.flush()

    result = agent_decision_engine.review_and_decide(bootstrapped, task, nature=nature)

    assert result.decision is ChiefDecision.REJECT
    assert task.status is TaskStatus.REJECTED
    assert result.follow_up is not None
    assert result.follow_up.assigned_to_agent_id == agent.id
    assert result.follow_up.attempt == task.attempt + 1
    assert result.follow_up.parent_task_id == task.id


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Conclusão: APPROVE, a entrega está completa.", ChiefDecision.APPROVE),
        ("Decido rejeitar e reconvocar o agente.", ChiefDecision.REJECT),
        ("Vou modificar o escopo e abrir uma subtarefa.", ChiefDecision.MODIFY),
        ("Preciso consultar os pares antes.", ChiefDecision.CONSULT_PEERS),
        ("Isso precisa escalar ao CEO.", ChiefDecision.ESCALATE),
        ("Texto sem veredito reconhecível.", None),
    ],
)
def test_parser_de_veredito(text: str, expected: ChiefDecision | None) -> None:
    assert agent_decision_engine.parse_decision(text) is expected


def test_desempate_do_ceo_nunca_deixa_a_tarefa_em_aberto(
    bootstrapped: Session, nature: NatureManager
) -> None:
    request = _submit(bootstrapped)
    agent = _hire_for(bootstrapped, nature, request, AgentRole.CTO)
    cto = agent_service.get_chief(bootstrapped, AgentRole.CTO)
    assert cto is not None
    task = communication_service.delegate_task(
        bootstrapped,
        request,
        cto,
        agent,
        DelegationIntake(title="Frente", task_description="Mapear personas"),
    )
    task.status = TaskStatus.AWAITING_REVIEW
    task.report_summary = "A senha do cliente ficou exposta no log."
    bootstrapped.flush()

    result = agent_decision_engine.ceo_final_decision(bootstrapped, task, nature=nature)

    assert result.decision in (
        ChiefDecision.APPROVE,
        ChiefDecision.REJECT,
        ChiefDecision.MODIFY,
    )
    assert task.status is not TaskStatus.AWAITING_REVIEW


# --- Ciclo automático --------------------------------------------------------


def test_ciclo_automatico_monta_o_time_e_fecha_o_turno(
    bootstrapped: Session, nature: NatureManager
) -> None:
    request = _submit(bootstrapped)
    result = network_orchestrator.run_cycle(bootstrapped, request, nature=nature)

    assert result.deliberated
    assert len(result.delegated) == len(network_orchestrator.FRONTS)
    assert len(result.executed) == len(network_orchestrator.FRONTS)
    assert len(result.reviews) == len(network_orchestrator.FRONTS)

    for agent in result.created_agents:
        assert agent.agent_type is AgentType.SUBAGENT
        chief = bootstrapped.get(Agent, agent.reports_to_id)
        assert chief is not None
        assert chief.role in {front.role for front in network_orchestrator.FRONTS}


def test_segundo_ciclo_nao_recontrata_para_a_mesma_frente(
    bootstrapped: Session, nature: NatureManager
) -> None:
    request = _submit(bootstrapped)
    first = network_orchestrator.run_cycle(bootstrapped, request, nature=nature)
    second = network_orchestrator.run_cycle(bootstrapped, request, nature=nature)

    assert first.created_agents
    assert second.created_agents == ()


def test_ciclo_leva_ao_ceo_a_tarefa_escalada_ou_em_consulta(
    bootstrapped: Session, nature: NatureManager
) -> None:
    """Regressão: tarefa revisada com ESCALATE/CONSULT_PEERS ficava parada para sempre."""
    request = _submit(bootstrapped)
    agent = _hire_for(bootstrapped, nature, request, AgentRole.CTO)
    cto = agent_service.get_chief(bootstrapped, AgentRole.CTO)
    assert cto is not None
    task = communication_service.delegate_task(
        bootstrapped,
        request,
        cto,
        agent,
        DelegationIntake(title="Frente", task_description="Mapear personas"),
    )
    task.status = TaskStatus.AWAITING_REVIEW
    task.report_summary = "Entrega parcial com divergência entre diretorias."
    task.decision = ChiefDecision.ESCALATE
    task.reviewed_at = utcnow()
    bootstrapped.flush()

    result = network_orchestrator.run_cycle(bootstrapped, request, nature=nature)

    assert len(result.tiebreaks) == 1
    assert result.tiebreaks[0].task is task
    assert task.decision is not ChiefDecision.ESCALATE
    assert task.status is not TaskStatus.AWAITING_REVIEW
