"""Interceptação do raciocínio: captura, ordem, totais e transmissão."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.models.agent import Agent
from app.models.enums import (
    AgentRole,
    AgentStatus,
    AgentType,
    AuditEventType,
    ReasoningStatus,
    ReasoningStepType,
)
from app.services import audit_service, reasoning_service
from app.services.reasoning_broker import ReasoningBroker
from app.services.reasoning_tracer import ReasoningTracer


def make_agent(db: Session) -> Agent:
    agent = Agent(
        name="Analista de Dados #1",
        role=AgentRole.SUBAGENT,
        agent_type=AgentType.SUBAGENT,
        status=AgentStatus.IDLE,
        job_title="Analista de Dados",
        system_prompt="Você analisa métricas.",
        model_name="llama3.2:3b",
        estimated_ram_mb=3_000,
        attributes={},
    )
    db.add(agent)
    db.flush()
    return agent


class TestCaptura:
    def test_cada_tipo_de_passo_e_persistido_em_ordem(self, db_session: Session) -> None:
        tracer = ReasoningTracer(db_session, task="Analisar retenção", agent=make_agent(db_session))
        tracer.start()

        tracer.on_thought("Preciso dos dados de churn.")
        tracer.on_action("memoria_corporativa", "churn")
        tracer.on_observation("Nenhum registro.", tool="memoria_corporativa")
        tracer.on_conclusion("Sem base histórica, recomendo instrumentar o produto.")
        session = tracer.complete("Sem base histórica, recomendo instrumentar o produto.")

        tipos = [step.step_type for step in sorted(session.steps, key=lambda s: s.sequence)]
        assert tipos == [
            ReasoningStepType.THOUGHT,
            ReasoningStepType.ACTION,
            ReasoningStepType.OBSERVATION,
            ReasoningStepType.CONCLUSION,
        ]
        assert [step.sequence for step in session.steps] == [1, 2, 3, 4]
        assert session.step_count == 4
        assert session.status is ReasoningStatus.COMPLETED
        assert session.finished_at is not None

    def test_acao_guarda_ferramenta_e_entrada_bruta(self, db_session: Session) -> None:
        tracer = ReasoningTracer(db_session, task="Contratar analista")
        tracer.start()

        step = tracer.on_action("banco_de_talentos", "Analista de Dados")

        assert step.payload["tool"] == "banco_de_talentos"
        assert step.payload["tool_input"] == "Analista de Dados"
        assert step.content == "banco_de_talentos(Analista de Dados)"

    def test_observacao_preserva_erro_da_ferramenta(self, db_session: Session) -> None:
        tracer = ReasoningTracer(db_session, task="Calcular margem")
        tracer.start()

        step = tracer.on_observation("falhou", tool="calculadora", error="divisão por zero")

        assert step.payload["error"] == "divisão por zero"

    def test_tokens_sao_acumulados_na_sessao(self, db_session: Session) -> None:
        tracer = ReasoningTracer(db_session, task="Tarefa longa")
        tracer.start()

        tracer.account_usage(10, 20)
        tracer.account_usage(5, 7)
        session = tracer.complete("pronto")

        assert session.prompt_tokens == 15
        assert session.completion_tokens == 27
        assert session.total_tokens == 42

    def test_conteudo_longo_e_truncado(self, db_session: Session, settings: Settings) -> None:
        tracer = ReasoningTracer(db_session, task="Tarefa")
        tracer.start()

        step = tracer.on_thought("x" * (settings.reasoning_max_content_chars + 500))

        assert len(step.content) <= settings.reasoning_max_content_chars + 20
        assert step.content.endswith("[truncado]")

    def test_falha_preserva_passos_e_marca_sessao(self, db_session: Session) -> None:
        tracer = ReasoningTracer(db_session, task="Tarefa impossível")
        tracer.start()
        tracer.on_thought("Tentando.")

        session = tracer.fail("ferramenta indisponível")

        assert session.status is ReasoningStatus.FAILED
        assert session.error == "ferramenta indisponível"
        assert session.step_count == 1

    def test_cancelamento_marca_a_sessao(self, db_session: Session) -> None:
        tracer = ReasoningTracer(db_session, task="Tarefa abortada")
        tracer.start()

        session = tracer.cancel("o Chief retirou a pauta")

        assert session.status is ReasoningStatus.CANCELLED
        assert session.error == "o Chief retirou a pauta"

    def test_captura_desligada_nao_persiste_passos(
        self, db_session: Session, settings: Settings, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "reasoning_capture_enabled", False)
        tracer = ReasoningTracer(db_session, task="Tarefa", settings=settings)
        tracer.start()

        tracer.on_thought("pensando")
        session = tracer.complete("fim")

        assert session.step_count == 1
        assert list(session.steps) == []


class TestConsultas:
    def test_sessao_em_execucao_tem_precedencia_sobre_a_ultima(
        self, db_session: Session
    ) -> None:
        agent = make_agent(db_session)
        encerrada = ReasoningTracer(db_session, task="Antiga", agent=agent)
        encerrada.start()
        encerrada.complete("fim")
        rodando = ReasoningTracer(db_session, task="Atual", agent=agent)
        rodando.start()

        assert reasoning_service.latest_for_agent(db_session, agent.id) is rodando.session

    def test_lista_filtra_por_agente_e_status(self, db_session: Session) -> None:
        agent = make_agent(db_session)
        minha = ReasoningTracer(db_session, task="Minha", agent=agent)
        minha.start()
        minha.complete("fim")
        alheia = ReasoningTracer(db_session, task="Alheia")
        alheia.start()

        do_agente = reasoning_service.list_sessions(db_session, agent_id=agent.id)
        completas = reasoning_service.list_sessions(
            db_session, status=ReasoningStatus.COMPLETED
        )

        assert [s.id for s in do_agente] == [minha.session.id]
        assert [s.id for s in completas] == [minha.session.id]

    def test_sessao_inexistente_devolve_none(self, db_session: Session) -> None:
        assert reasoning_service.get_session(db_session, uuid.uuid4()) is None


class TestAuditoria:
    def test_inicio_e_fim_deixam_rastro(self, db_session: Session) -> None:
        tracer = ReasoningTracer(db_session, task="Avaliar proposta", agent=make_agent(db_session))
        tracer.start()
        tracer.complete("aprovado")

        tipos = {event.event_type for event in audit_service.list_events(db_session, limit=20)}
        assert AuditEventType.REASONING_STARTED in tipos
        assert AuditEventType.REASONING_COMPLETED in tipos

    def test_falha_registra_evento_proprio(self, db_session: Session) -> None:
        tracer = ReasoningTracer(db_session, task="Avaliar proposta")
        tracer.start()
        tracer.fail("erro")

        tipos = {event.event_type for event in audit_service.list_events(db_session, limit=20)}
        assert AuditEventType.REASONING_FAILED in tipos


class TestBroker:
    @pytest.mark.asyncio
    async def test_assinante_do_agente_recebe_apenas_seus_passos(
        self, db_session: Session
    ) -> None:
        broker = ReasoningBroker(buffer_size=16)
        agent = make_agent(db_session)
        subscription = broker.subscribe(agent.id)

        tracer = ReasoningTracer(db_session, task="Tarefa", agent=agent, broker=broker)
        tracer.start()
        tracer.on_thought("pensando")
        outro = ReasoningTracer(db_session, task="Outra", broker=broker)
        outro.start()
        outro.on_thought("ruído de outro agente")

        await asyncio.sleep(0)
        eventos = []
        while not subscription.queue.empty():
            eventos.append(subscription.queue.get_nowait())

        assert [evento["event"] for evento in eventos] == ["session.started", "step"]
        assert eventos[1]["data"]["content"] == "pensando"

    @pytest.mark.asyncio
    async def test_canal_global_recebe_todos(self, db_session: Session) -> None:
        broker = ReasoningBroker(buffer_size=16)
        subscription = broker.subscribe(None)

        tracer = ReasoningTracer(
            db_session, task="Tarefa", agent=make_agent(db_session), broker=broker
        )
        tracer.start()
        tracer.on_thought("a")
        tracer.complete("fim")

        await asyncio.sleep(0)
        eventos = []
        while not subscription.queue.empty():
            eventos.append(subscription.queue.get_nowait())

        assert [evento["event"] for evento in eventos] == [
            "session.started",
            "step",
            "session.finished",
        ]

    @pytest.mark.asyncio
    async def test_fila_cheia_descarta_o_evento_mais_antigo(self) -> None:
        broker = ReasoningBroker(buffer_size=2)
        subscription = broker.subscribe(None)

        for indice in range(4):
            broker.publish({"event": "step", "data": {"i": indice}})
        await asyncio.sleep(0)

        restantes = [subscription.queue.get_nowait()["data"]["i"] for _ in range(2)]
        assert restantes == [2, 3]
        assert subscription.dropped == 2

    @pytest.mark.asyncio
    async def test_unsubscribe_para_de_entregar(self) -> None:
        broker = ReasoningBroker(buffer_size=4)
        subscription = broker.subscribe(None)
        broker.unsubscribe(subscription)

        alcancados = broker.publish({"event": "step"})

        assert alcancados == 0
        assert broker.subscriber_count == 0
