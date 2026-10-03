"""Métricas cognitivas, política de retenção e export."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.enums import AuditEventType, ReasoningStatus
from app.services import audit_service, reasoning_metrics
from app.services.reasoning_tracer import ReasoningTracer
from tests.test_reasoning_tracer import make_agent


def seed(db: Session, agent, *, status: ReasoningStatus, tokens: int = 30) -> ReasoningTracer:
    tracer = ReasoningTracer(db, task="Tarefa", agent=agent, model_name="llama3.2:3b")
    tracer.start()
    tracer.on_thought("pensando", tokens=tokens, duration_ms=50)
    tracer.account_usage(tokens, tokens)
    if status is ReasoningStatus.COMPLETED:
        tracer.complete("ok")
    elif status is ReasoningStatus.FAILED:
        tracer.fail("erro")
    return tracer


class TestMetricas:
    def test_consolida_totais_e_taxa_de_sucesso(self, db_session: Session) -> None:
        agent = make_agent(db_session)
        seed(db_session, agent, status=ReasoningStatus.COMPLETED)
        seed(db_session, agent, status=ReasoningStatus.COMPLETED)
        seed(db_session, agent, status=ReasoningStatus.FAILED)
        seed(db_session, agent, status=ReasoningStatus.RUNNING)

        metrics = reasoning_metrics.collect(db_session)

        assert metrics.total_sessions == 4
        assert metrics.completed == 2
        assert metrics.failed == 1
        assert metrics.running == 1
        assert metrics.success_rate == round(2 / 3, 4)
        assert metrics.total_tokens == 4 * 60

    def test_agrupa_por_modelo(self, db_session: Session) -> None:
        agent = make_agent(db_session)
        seed(db_session, agent, status=ReasoningStatus.COMPLETED)

        metrics = reasoning_metrics.collect(db_session)

        assert metrics.by_model[0]["model"] == "llama3.2:3b"
        assert metrics.by_model[0]["sessions"] == 1

    def test_agrupa_por_agente_com_custo_e_roi(self, db_session: Session) -> None:
        agent = make_agent(db_session)
        tracer = seed(db_session, agent, status=ReasoningStatus.COMPLETED)
        tracer.session.duration_ms = 2_000
        db_session.flush()

        linha = reasoning_metrics.collect(db_session).by_agent[0]

        assert linha["agent_id"] == str(agent.id)
        assert linha["completed"] == 1
        assert linha["cost_mb_s"] == 6_000.0
        assert linha["roi"] > 0

    def test_agrupa_por_tipo_de_passo_incluindo_zeros(self, db_session: Session) -> None:
        seed(db_session, make_agent(db_session), status=ReasoningStatus.COMPLETED)

        por_tipo = {
            linha["step_type"]: linha
            for linha in reasoning_metrics.collect(db_session).by_step_type
        }

        assert por_tipo["THOUGHT"]["count"] == 1
        assert por_tipo["ACTION"]["count"] == 0

    def test_banco_vazio_nao_divide_por_zero(self, db_session: Session) -> None:
        metrics = reasoning_metrics.collect(db_session)

        assert metrics.total_sessions == 0
        assert metrics.success_rate == 0.0
        assert metrics.avg_steps == 0.0

    def test_filtra_por_data(self, db_session: Session) -> None:
        agent = make_agent(db_session)
        antigo = seed(db_session, agent, status=ReasoningStatus.COMPLETED)
        antigo.session.started_at = utcnow() - timedelta(days=10)
        db_session.flush()

        metrics = reasoning_metrics.collect(db_session, since=utcnow() - timedelta(days=1))

        assert metrics.total_sessions == 0


class TestRetencao:
    def test_remove_sessoes_antigas_e_seus_passos(self, db_session: Session) -> None:
        agent = make_agent(db_session)
        antigo = seed(db_session, agent, status=ReasoningStatus.COMPLETED)
        antigo.session.started_at = utcnow() - timedelta(days=90)
        recente = seed(db_session, agent, status=ReasoningStatus.COMPLETED)
        db_session.flush()

        removidos = reasoning_metrics.purge_sessions(db_session)

        assert removidos == 1
        restantes = reasoning_metrics.export_sessions(db_session)
        assert [linha["id"] for linha in restantes] == [str(recente.session.id)]

    def test_nao_remove_sessao_em_execucao(self, db_session: Session) -> None:
        agent = make_agent(db_session)
        rodando = seed(db_session, agent, status=ReasoningStatus.RUNNING)
        rodando.session.started_at = utcnow() - timedelta(days=90)
        db_session.flush()

        assert reasoning_metrics.purge_sessions(db_session) == 0

    def test_registra_evento_de_auditoria(self, db_session: Session) -> None:
        reasoning_metrics.purge_sessions(db_session)

        eventos = audit_service.list_events(
            db_session, event_type=AuditEventType.REASONING_PURGED, limit=5
        )
        assert len(eventos) == 1


class TestExport:
    def test_export_traz_sessao_com_passos(self, db_session: Session) -> None:
        agent = make_agent(db_session)
        seed(db_session, agent, status=ReasoningStatus.COMPLETED)

        linhas = reasoning_metrics.export_sessions(db_session)

        assert len(linhas) == 1
        assert linhas[0]["steps"][0]["step_type"] == "THOUGHT"
        assert "cost_mb_s" in linhas[0]

    def test_export_filtra_por_agente(self, db_session: Session) -> None:
        agent = make_agent(db_session)
        seed(db_session, agent, status=ReasoningStatus.COMPLETED)
        seed(db_session, None, status=ReasoningStatus.COMPLETED)

        linhas = reasoning_metrics.export_sessions(db_session, agent_id=agent.id)

        assert len(linhas) == 1
        assert linhas[0]["agent_id"] == str(agent.id)
