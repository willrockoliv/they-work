"""Conselho administrativo: raciocínio de cada Chief e resolução de impasses."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.models import AgentRole, AuditEventType, CouncilOutcome, CouncilStance
from app.services import agent_service, audit_service, council_service
from app.services.council_service import Proposal

PROPOSTA_COMPLETA = Proposal(
    topic="SaaS de atas automáticas",
    description=(
        "Lançar um produto para o mercado de pequenas empresas, com persona definida de "
        "gestores de equipe, receita por assinatura mensal e custo de execução estimado. "
        "A estratégia de longo prazo é dominar o nicho via canal de conteúdo."
    ),
)


class TestPersonas:
    def test_cada_cargo_tem_persona(self) -> None:
        for role in (AgentRole.CEO, AgentRole.CTO, AgentRole.CMO, AgentRole.CFO, AgentRole.RA):
            chief = council_service.get_chief_agent(role)
            assert chief is not None
            assert chief.mission
            assert chief.objectives
            assert chief.decision_criteria

    def test_cto_veta_proposta_inviavel(self) -> None:
        cto = council_service.get_chief_agent(AgentRole.CTO)
        assert cto is not None

        parecer = cto.analyze(
            Proposal(
                topic="Plataforma global",
                description="Precisamos treinar modelo proprio em cluster na nuvem.",
            )
        )

        assert parecer.stance is CouncilStance.REJECT
        assert parecer.confidence >= 8

    def test_cto_levanta_ressalva_de_seguranca(self) -> None:
        cto = council_service.get_chief_agent(AgentRole.CTO)
        assert cto is not None

        parecer = cto.analyze(
            Proposal(topic="App", description="Guardar dados sensiveis dos clientes.")
        )

        assert parecer.stance is CouncilStance.APPROVE
        assert parecer.concerns

    def test_cmo_rejeita_sem_publico(self) -> None:
        cmo = council_service.get_chief_agent(AgentRole.CMO)
        assert cmo is not None

        parecer = cmo.analyze(Proposal(topic="Ideia", description="Construir uma ferramenta."))

        assert parecer.stance is CouncilStance.REJECT
        assert "Persona do cliente indefinida." in parecer.concerns

    def test_cfo_rejeita_sem_monetizacao(self) -> None:
        cfo = council_service.get_chief_agent(AgentRole.CFO)
        assert cfo is not None

        parecer = cfo.analyze(
            Proposal(topic="Ideia", description="Atender o mercado de gestores.")
        )

        assert parecer.stance is CouncilStance.REJECT

    def test_ra_nao_delibera_sobre_produto(self) -> None:
        ra = council_service.get_chief_agent(AgentRole.RA)
        assert ra is not None

        assert ra.analyze(PROPOSTA_COMPLETA).stance is CouncilStance.ABSTAIN


class TestPerfisPersistidos:
    def test_init_profiles_e_idempotente(self, db_session: Session) -> None:
        agent_service.init_chiefs(db_session)

        primeiros = council_service.init_profiles(db_session)
        segundos = council_service.init_profiles(db_session)

        assert len(primeiros) == 5
        assert {p.id for p in primeiros} == {p.id for p in segundos}

    def test_perfis_sao_vinculados_aos_agentes(self, db_session: Session) -> None:
        agent_service.init_chiefs(db_session)
        perfis = council_service.init_profiles(db_session)

        assert all(perfil.agent_id is not None for perfil in perfis)

    def test_memoria_de_contexto_acumula_fatos(self, db_session: Session) -> None:
        agent_service.init_chiefs(db_session)
        council_service.init_profiles(db_session)

        perfil = council_service.remember(db_session, AgentRole.CEO, "Caixa inicial simulado.")

        assert perfil.context_memory["facts"][-1]["fact"] == "Caixa inicial simulado."

    def test_memoria_exige_perfil_inicializado(self, db_session: Session) -> None:
        with pytest.raises(ValueError, match="não inicializado"):
            council_service.remember(db_session, AgentRole.CEO, "fato")


class TestDeliberacao:
    def test_proposta_completa_e_aprovada(self, db_session: Session) -> None:
        decisao = council_service.deliberate(db_session, PROPOSTA_COMPLETA)

        assert decisao.outcome in (
            CouncilOutcome.APPROVED,
            CouncilOutcome.APPROVED_WITH_CONDITIONS,
        )
        assert len(decisao.opinions) == 4

    def test_veto_tecnico_do_cto_e_bloqueante(self, db_session: Session) -> None:
        decisao = council_service.deliberate(
            db_session,
            Proposal(
                topic="Expansão",
                description=(
                    "Atender milhoes de usuarios com cluster na nuvem, com receita por "
                    "assinatura e persona de cliente corporativo."
                ),
            ),
        )

        assert decisao.outcome is CouncilOutcome.REJECTED
        assert "veto técnico" in decisao.narrative

    def test_maioria_contraria_rejeita(self, db_session: Session) -> None:
        decisao = council_service.deliberate(
            db_session, Proposal(topic="Ideia solta", description="Construir alguma ferramenta.")
        )

        assert decisao.outcome is CouncilOutcome.REJECTED

    def test_desempate_do_ceo_aprova_com_condicoes(self, db_session: Session) -> None:
        decisao = council_service.deliberate(
            db_session,
            Proposal(
                topic="Consultoria",
                description=(
                    "Vender consultoria com receita por licenca para o mercado de gestores, "
                    "sem detalhar canais de aquisicao."
                ),
            ),
        )

        assert decisao.outcome is CouncilOutcome.APPROVED_WITH_CONDITIONS
        assert decisao.conditions

    def test_deliberacao_registra_comunicacoes_e_auditoria(self, db_session: Session) -> None:
        decisao = council_service.deliberate(db_session, PROPOSTA_COMPLETA)

        mensagens = council_service.list_communications(db_session, thread_id=decisao.thread_id)
        eventos = audit_service.list_events(
            db_session, event_type=AuditEventType.COUNCIL_DELIBERATION
        )

        # 1 pauta + 3 pareceres + 1 decisão do CEO.
        assert len(mensagens) == 5
        assert len(eventos) == 1
        assert eventos[0].decision == decisao.outcome.value

    def test_decisao_e_serializavel(self, db_session: Session) -> None:
        dados = council_service.deliberate(db_session, PROPOSTA_COMPLETA).to_dict()

        assert dados["topic"] == PROPOSTA_COMPLETA.topic
        assert len(dados["opinions"]) == 4
