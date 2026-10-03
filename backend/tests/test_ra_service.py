"""Pipeline do RA: triagem, Natureza, Banco de Talentos, contratação e demissão."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy.orm import Session

from app.models import (
    AgentRole,
    AgentStatus,
    AuditEventType,
    CorporateMemory,
    NatureDecision,
    RequestStatus,
    TaskComplexity,
)
from app.services import agent_service, audit_service, ra_service, talent_bank
from app.services.nature_manager import HiringRequest, NatureManager
from app.services.ra_service import HiringIntake
from tests.conftest import make_nature

PEDIDO_COMPLETO = HiringIntake(
    requested_by=AgentRole.CTO,
    job_title="Analista de Dados",
    objective="Analisar as metricas de uso do produto e apontar gargalos de retencao.",
    specialization="métricas de produto",
    deliverables=("Relatório de retenção", "Lista de gargalos"),
    tools=("planilha",),
)


@pytest.fixture
def chiefs(db_session: Session) -> None:
    agent_service.init_chiefs(db_session)


class TestTriagem:
    def test_pedido_vago_volta_com_perguntas(
        self, db_session: Session, nature: NatureManager
    ) -> None:
        resultado = ra_service.submit_request(
            db_session,
            nature,
            HiringIntake(requested_by=AgentRole.CMO, job_title="ajudante"),
        )

        assert resultado.agent is None
        assert resultado.request.status is RequestStatus.NEEDS_CLARIFICATION
        assert len(resultado.questions) == 3

    def test_modelo_inexistente_vira_pergunta(self) -> None:
        perguntas = ra_service.screen(
            HiringIntake(
                requested_by=AgentRole.CTO,
                job_title="Analista de Dados",
                objective="Analisar as metricas de uso do produto e apontar gargalos.",
                deliverables=("Relatório",),
                requested_model="gpt-5:999b",
            )
        )

        assert any("não existe no repositório local" in pergunta for pergunta in perguntas)

    def test_pedido_completo_nao_gera_perguntas(self) -> None:
        assert ra_service.screen(PEDIDO_COMPLETO) == ()

    def test_triagem_e_auditada(self, db_session: Session, nature: NatureManager) -> None:
        ra_service.submit_request(
            db_session, nature, HiringIntake(requested_by=AgentRole.CMO, job_title="ajudante")
        )

        eventos = audit_service.list_events(
            db_session, event_type=AuditEventType.SUBAGENT_CLARIFICATION
        )
        assert len(eventos) == 1


class TestEsclarecimento:
    def test_respostas_completam_a_requisicao_e_contratam(
        self, db_session: Session, nature: NatureManager, chiefs: None
    ) -> None:
        pendente = ra_service.submit_request(
            db_session,
            nature,
            HiringIntake(requested_by=AgentRole.CMO, job_title="ajudante"),
        )

        resultado = ra_service.clarify_request(
            db_session,
            nature,
            pendente.request,
            job_title="Redator de Conteúdo",
            objective="Produzir artigos semanais sobre produtividade para o blog da empresa.",
            specialization="conteúdo de blog",
            deliverables=("4 artigos por mês",),
        )

        assert resultado.agent is not None
        assert resultado.request.status is RequestStatus.FULFILLED
        assert resultado.request.clarifications["answers"]

    def test_resposta_insuficiente_gera_novas_perguntas(
        self, db_session: Session, nature: NatureManager
    ) -> None:
        pendente = ra_service.submit_request(
            db_session,
            nature,
            HiringIntake(requested_by=AgentRole.CMO, job_title="ajudante"),
        )

        resultado = ra_service.clarify_request(
            db_session, nature, pendente.request, objective="fazer coisas"
        )

        assert resultado.request.status is RequestStatus.NEEDS_CLARIFICATION
        assert resultado.questions


class TestContratacao:
    def test_contrata_subagente_com_metaprompt_novo(
        self, db_session: Session, nature: NatureManager, chiefs: None
    ) -> None:
        resultado = ra_service.submit_request(db_session, nature, PEDIDO_COMPLETO)

        assert resultado.agent is not None
        assert resultado.reused_profile is False
        assert resultado.request.status is RequestStatus.FULFILLED
        assert resultado.agent.system_prompt.startswith("# Cargo: Analista de Dados")
        assert "## Limitações e restrições" in resultado.agent.system_prompt

    def test_subagente_reporta_ao_chief_solicitante(
        self, db_session: Session, nature: NatureManager, chiefs: None
    ) -> None:
        cto = agent_service.get_chief(db_session, AgentRole.CTO)
        resultado = ra_service.submit_request(db_session, nature, PEDIDO_COMPLETO)

        assert cto is not None
        assert resultado.agent is not None
        assert resultado.agent.reports_to_id == cto.id

    def test_segunda_vaga_reaproveita_o_banco_de_talentos(
        self, db_session: Session, nature: NatureManager, chiefs: None
    ) -> None:
        primeira = ra_service.submit_request(db_session, nature, PEDIDO_COMPLETO)
        segunda = ra_service.submit_request(db_session, nature, PEDIDO_COMPLETO)

        assert primeira.reused_profile is False
        assert segunda.reused_profile is True
        assert segunda.request.talent_profile_id == primeira.request.talent_profile_id
        assert len(talent_bank.list_profiles(db_session)) == 1

    def test_reaproveitamento_e_auditado(
        self, db_session: Session, nature: NatureManager, chiefs: None
    ) -> None:
        ra_service.submit_request(db_session, nature, PEDIDO_COMPLETO)
        ra_service.submit_request(db_session, nature, PEDIDO_COMPLETO)

        reaproveitados = audit_service.list_events(
            db_session, event_type=AuditEventType.TALENT_PROFILE_REUSED
        )
        criados = audit_service.list_events(
            db_session, event_type=AuditEventType.TALENT_PROFILE_CREATED
        )
        assert len(reaproveitados) == 1
        assert len(criados) == 1

    def test_complexidade_e_inferida_quando_nao_informada(
        self, db_session: Session, nature: NatureManager, chiefs: None
    ) -> None:
        resultado = ra_service.submit_request(
            db_session,
            nature,
            HiringIntake(
                requested_by=AgentRole.CTO,
                job_title="Engenheiro de Backend",
                objective=(
                    "Implementar a arquitetura do modulo de integracao com foco em seguranca."
                ),
                deliverables=("Módulo entregue",),
            ),
        )

        assert resultado.request.complexity is TaskComplexity.CRITICAL
        assert resultado.request.granted_model == "deepseek-r1:8b"

    def test_complexidade_explicita_prevalece(
        self, db_session: Session, nature: NatureManager, chiefs: None
    ) -> None:
        resultado = ra_service.submit_request(
            db_session,
            nature,
            HiringIntake(
                requested_by=AgentRole.CTO,
                job_title="Revisor de Atas",
                objective="Revisar as atas das reunioes semanais do conselho.",
                deliverables=("Atas revisadas",),
                complexity=TaskComplexity.TRIVIAL,
            ),
        )

        assert resultado.request.complexity is TaskComplexity.TRIVIAL
        assert resultado.request.granted_model == "llama3.2:3b"


class TestLimitesDaNatureza:
    def test_orcamento_apertado_forca_downgrade(self, db_session: Session, chiefs: None) -> None:
        # Sobram ~2,1 GB alocáveis: só o modelo mais leve cabe.
        apertada = make_nature(ram_total=16_384, ram_used=12_236)

        resultado = ra_service.submit_request(db_session, apertada, PEDIDO_COMPLETO)

        assert resultado.request.nature_decision is NatureDecision.DOWNGRADED
        assert resultado.request.granted_model == "llama3.2:3b"
        assert resultado.agent is not None

    def test_sem_orcamento_a_vaga_e_enfileirada(self, db_session: Session, chiefs: None) -> None:
        esgotada = make_nature(ram_total=16_384, ram_used=16_300)

        resultado = ra_service.submit_request(db_session, esgotada, PEDIDO_COMPLETO)

        assert resultado.agent is None
        assert resultado.request.status is RequestStatus.QUEUED
        assert resultado.request.queue_position == 1

    def test_decisao_da_natureza_e_auditada(
        self, db_session: Session, nature: NatureManager, chiefs: None
    ) -> None:
        ra_service.submit_request(db_session, nature, PEDIDO_COMPLETO)

        eventos = audit_service.list_events(
            db_session, event_type=AuditEventType.NATURE_DECISION
        )
        assert len(eventos) == 1
        assert "classification" in eventos[0].payload


class TestDemissao:
    def test_demissao_libera_recursos_e_arquiva_relatorio(
        self, db_session: Session, nature: NatureManager, chiefs: None
    ) -> None:
        resultado = ra_service.submit_request(db_session, nature, PEDIDO_COMPLETO)
        assert resultado.agent is not None

        ra_service.dismiss_subagent(
            db_session,
            resultado.agent,
            reason="sprint concluída",
            final_report="Retenção caiu 8% no onboarding.",
            rating=5,
        )

        assert resultado.agent.status is AgentStatus.TERMINATED
        assert resultado.agent.estimated_ram_mb == 0
        assert resultado.agent.system_prompt == ""
        assert db_session.query(CorporateMemory).count() == 1
        assert agent_service.count_active_subagents(db_session) == 0

    def test_demissao_avalia_o_perfil_usado(
        self, db_session: Session, nature: NatureManager, chiefs: None
    ) -> None:
        resultado = ra_service.submit_request(db_session, nature, PEDIDO_COMPLETO)
        assert resultado.agent is not None

        ra_service.dismiss_subagent(
            db_session, resultado.agent, reason="fim do projeto", rating=4
        )

        perfis = talent_bank.list_profiles(db_session)
        assert perfis[0].average_rating == 4.0

    def test_chief_nao_pode_ser_demitido(self, db_session: Session, chiefs: None) -> None:
        ceo = agent_service.get_chief(db_session, AgentRole.CEO)
        assert ceo is not None

        with pytest.raises(ValueError, match="Apenas subagentes"):
            ra_service.dismiss_subagent(db_session, ceo, reason="teste")


class TestConsultas:
    def test_lista_requisicoes_por_status(
        self, db_session: Session, nature: NatureManager, chiefs: None
    ) -> None:
        ra_service.submit_request(db_session, nature, PEDIDO_COMPLETO)
        ra_service.submit_request(
            db_session, nature, HiringIntake(requested_by=AgentRole.CMO, job_title="ajudante")
        )

        pendentes = ra_service.list_requests(
            db_session, status=RequestStatus.NEEDS_CLARIFICATION
        )
        concluidas = ra_service.list_requests(db_session, status=RequestStatus.FULFILLED)

        assert len(pendentes) == 1
        assert len(concluidas) == 1

    def test_busca_requisicao_por_id(
        self, db_session: Session, nature: NatureManager, chiefs: None
    ) -> None:
        resultado = ra_service.submit_request(db_session, nature, PEDIDO_COMPLETO)

        assert ra_service.get_request(db_session, resultado.request.id) is resultado.request


class TestCarga:
    def test_chiefs_simultaneos_respeitam_o_teto_de_vagas(
        self, db_session: Session, nature: NatureManager, chiefs: None
    ) -> None:
        teto = nature.settings.nature_max_concurrent_subagents
        solicitantes = (AgentRole.CEO, AgentRole.CTO, AgentRole.CMO, AgentRole.CFO)

        resultados = [
            ra_service.submit_request(
                db_session,
                nature,
                HiringIntake(
                    requested_by=solicitantes[indice % len(solicitantes)],
                    job_title=f"Pesquisador {indice}",
                    objective="Pesquisar referencias de mercado para o novo produto da empresa.",
                    deliverables=("Dossiê de referências",),
                ),
            )
            for indice in range(teto + 2)
        ]

        contratados = [r for r in resultados if r.agent is not None]
        represados = [r for r in resultados if r.request.status is RequestStatus.QUEUED]

        assert len(contratados) == teto
        assert len(represados) == 2
        assert agent_service.count_active_subagents(db_session) == teto
        assert [r.request.queue_position for r in represados] == [1, 2]

    def test_fila_da_natureza_e_thread_safe(self, nature: NatureManager) -> None:
        pedido = HiringRequest(
            requested_by="CTO", job_title="Pesquisador", complexity=TaskComplexity.SIMPLE
        )
        total = nature.settings.nature_max_queue_size

        with ThreadPoolExecutor(max_workers=8) as executor:
            posicoes = list(executor.map(lambda _: nature.enqueue(pedido), range(total)))

        assert sorted(posicao for posicao in posicoes if posicao is not None) == list(
            range(1, total + 1)
        )
        assert nature.enqueue(pedido) is None

    def test_chiefs_concorrentes_nao_corrompem_a_fila(self, nature: NatureManager) -> None:
        """Disputa real pela Natureza: a `Session` do SQLAlchemy não é thread-safe,
        então a concorrência é exercitada onde o estado mutável de fato é compartilhado.
        """
        teto = nature.settings.nature_max_concurrent_subagents
        solicitantes = (AgentRole.CEO, AgentRole.CTO, AgentRole.CMO, AgentRole.CFO)
        pedidos = [
            HiringRequest(
                requested_by=solicitantes[indice % len(solicitantes)].value,
                job_title=f"Pesquisador {indice}",
                complexity=TaskComplexity.SIMPLE,
            )
            for indice in range(len(solicitantes) * 2)
        ]

        with ThreadPoolExecutor(max_workers=8) as executor:
            vereditos = list(
                executor.map(
                    lambda pedido: nature.evaluate_hiring(pedido, active_subagents=teto), pedidos
                )
            )

        assert all(veredito.decision is NatureDecision.QUEUED for veredito in vereditos)
        # Nenhuma posição duplicada ou perdida sob concorrência.
        assert sorted(v.queue_position or 0 for v in vereditos) == list(
            range(1, len(pedidos) + 1)
        )
