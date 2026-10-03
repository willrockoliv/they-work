"""Persistência: schema do banco corporativo e serviços de domínio."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Agent,
    AgentRole,
    AgentStatus,
    AgentType,
    AuditEventType,
    AuditLog,
    CorporateMemory,
    MemoryType,
    TalentProfile,
    TaskComplexity,
)
from app.services import agent_service, audit_service


class TestAgents:
    def test_init_chiefs_cria_os_cinco_fundadores(self, db_session: Session) -> None:
        chiefs = agent_service.init_chiefs(db_session)

        assert len(chiefs) == 5
        assert {chief.role for chief in chiefs} == {
            AgentRole.CEO,
            AgentRole.CTO,
            AgentRole.CMO,
            AgentRole.CFO,
            AgentRole.RA,
        }
        assert all(chief.agent_type is AgentType.CHIEF for chief in chiefs)
        assert all(chief.status is AgentStatus.IDLE for chief in chiefs)
        assert all(chief.system_prompt for chief in chiefs)

    def test_init_chiefs_e_idempotente(self, db_session: Session) -> None:
        first = agent_service.init_chiefs(db_session)
        second = agent_service.init_chiefs(db_session)

        assert {chief.id for chief in first} == {chief.id for chief in second}
        assert len(agent_service.list_agents(db_session)) == 5

    def test_hierarquia_reporta_ao_ceo(self, db_session: Session) -> None:
        chiefs = agent_service.init_chiefs(db_session)
        ceo = next(chief for chief in chiefs if chief.role is AgentRole.CEO)

        assert ceo.reports_to_id is None
        assert all(
            chief.reports_to_id == ceo.id for chief in chiefs if chief.role is not AgentRole.CEO
        )

    def test_init_chiefs_registra_auditoria(self, db_session: Session) -> None:
        agent_service.init_chiefs(db_session)
        events = audit_service.list_events(db_session, event_type=AuditEventType.AGENT_CREATED)

        assert len(events) == 5

    def test_contagem_de_subagentes_ativos_ignora_demitidos(self, db_session: Session) -> None:
        db_session.add_all(
            [
                Agent(
                    name="Analista",
                    role=AgentRole.SUBAGENT,
                    agent_type=AgentType.SUBAGENT,
                    status=AgentStatus.WORKING,
                ),
                Agent(
                    name="Pesquisador",
                    role=AgentRole.SUBAGENT,
                    agent_type=AgentType.SUBAGENT,
                    status=AgentStatus.TERMINATED,
                ),
            ]
        )
        db_session.commit()

        assert agent_service.count_active_subagents(db_session) == 1


class TestTalentBank:
    def test_persiste_perfil_reutilizavel(self, db_session: Session) -> None:
        profile = TalentProfile(
            slug="analista-de-dados",
            role_title="Analista de Dados",
            specialization="Análise exploratória de mercado",
            system_prompt="Você é um analista de dados...",
            tools={"allowed": ["sql", "pandas"]},
            complexity=TaskComplexity.MODERATE,
            recommended_model="phi4-mini:3.8b",
        )
        db_session.add(profile)
        db_session.commit()

        stored = db_session.get(TalentProfile, profile.id)
        assert stored is not None
        assert stored.tools == {"allowed": ["sql", "pandas"]}
        assert stored.usage_count == 0

    def test_slug_e_unico(self, db_session: Session) -> None:
        for _ in range(2):
            db_session.add(
                TalentProfile(slug="duplicado", role_title="X", system_prompt="prompt")
            )
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestAuditAndMemory:
    def test_registra_decisao_da_natureza(self, db_session: Session) -> None:
        audit_service.record_event(
            db_session,
            event_type=AuditEventType.NATURE_DECISION,
            actor="NATURE",
            decision="BLOCKED",
            summary="Contratação bloqueada",
            narrative="A infraestrutura atingiu a capacidade máxima.",
            resource_snapshot={"ram_usage_ratio": 0.95},
        )
        db_session.commit()

        events = audit_service.list_events(db_session)
        assert len(events) == 1
        assert events[0].resource_snapshot == {"ram_usage_ratio": 0.95}

    def test_trunca_resumo_longo(self, db_session: Session) -> None:
        entry = audit_service.record_event(
            db_session,
            event_type=AuditEventType.SYSTEM,
            summary="x" * 400,
        )
        db_session.commit()
        assert len(entry.summary) == 255

    def test_memoria_corporativa(self, db_session: Session) -> None:
        memory = CorporateMemory(
            memory_type=MemoryType.DECISION,
            title="Definição do nicho de atuação",
            content="O conselho decidiu atuar em automação para pequenas clínicas.",
            author_role="CEO",
            importance=9,
            tags={"tags": ["estratégia", "fundação"]},
        )
        db_session.add(memory)
        db_session.commit()

        stored = db_session.get(CorporateMemory, memory.id)
        assert stored is not None
        assert stored.importance == 9

    def test_audit_log_usa_id_autoincremental(self, db_session: Session) -> None:
        for index in range(3):
            audit_service.record_event(
                db_session, event_type=AuditEventType.SYSTEM, summary=f"evento {index}"
            )
        db_session.commit()

        ids = [row.id for row in db_session.query(AuditLog).all()]
        assert ids == [1, 2, 3]
