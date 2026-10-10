"""Varredura das ferramentas de revisão e dos ramos do motor de decisão."""

from __future__ import annotations

import json
import uuid
from dataclasses import replace
from typing import Any

import httpx
import pytest
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.models.enums import AgentRole, ChiefDecision, DecisionSource, MemoryType, TaskStatus
from app.models.memory import CorporateMemory
from app.models.reasoning import ReasoningSession
from app.services import (
    agent_decision_engine,
    agent_service,
    chief_review,
    council_service,
    react_engine,
    reasoning_tools,
    report_analysis,
)
from app.services.nature_manager import NatureManager
from app.services.ollama_client import OllamaClient
from app.services.react_engine import TaskRequest
from app.services.reasoning_tools import ToolContext
from tests.conftest import make_react_ollama, stream_body
from tests.test_chief_review import (
    FULL_EXPLORATION,
    GOOD_REPORT,
    QUOTE,
    ScriptedOllama,
    awaiting_task,
    model_mode,
    verdict,
)

TASK_TOOLS = (
    "avaliar_qualidade_report",
    "comparar_vs_objetivo",
    "estimar_custo_beneficio",
    "proximos_passos",
    "ler_tarefa",
    "ler_report",
    "verificar_entregaveis",
    "checar_criterios",
    "detectar_artefatos",
    "premissas",
    "historico_feedback",
    "capacidade_do_agente",
)

REPORT_TOOLS = (
    "avaliar_qualidade_report",
    "comparar_vs_objetivo",
    "checar_riscos",
    "estimar_custo_beneficio",
    "proximos_passos",
    "ler_report",
    "verificar_entregaveis",
    "checar_criterios",
    "detectar_artefatos",
    "premissas",
)


@pytest.fixture
def booted(db_session: Session) -> Session:
    agent_service.init_chiefs(db_session)
    council_service.init_profiles(db_session)
    db_session.flush()
    return db_session


def ctx_for(session: Session, task_id: uuid.UUID | None, **extra: Any) -> ToolContext:
    return ToolContext(db=session, task_id=task_id, **extra)


class TestVarredura:
    @pytest.mark.parametrize("name", TASK_TOOLS)
    def test_sem_tarefa(self, db_session: Session, name: str) -> None:
        result = reasoning_tools.TOOLS[name].run(ctx_for(db_session, None), "")

        assert result.error == "no_task_in_context"

    @pytest.mark.parametrize("name", REPORT_TOOLS)
    def test_sem_report(self, booted: Session, nature: NatureManager, name: str) -> None:
        task = awaiting_task(booted, nature, "   ")

        result = reasoning_tools.TOOLS[name].run(ctx_for(booted, task.id), "ignorado")

        assert result.error == "report_ausente"

    @pytest.mark.parametrize("name", sorted(set(TASK_TOOLS) | set(REPORT_TOOLS)))
    def test_com_report(self, booted: Session, nature: NatureManager, name: str) -> None:
        task = awaiting_task(booted, nature)

        result = reasoning_tools.TOOLS[name].run(ctx_for(booted, task.id), "")

        assert result.error is None
        assert result.output

    def test_checar_riscos_sem_tarefa_usa_a_entrada(self, db_session: Session) -> None:
        result = reasoning_tools.TOOLS["checar_riscos"].run(
            ctx_for(db_session, None), "há risco de vazamento de senha"
        )

        assert result.payload["risk_level"] == "HIGH"


class TestLeitura:
    def test_ler_tarefa_por_uuid_com_instrucao_de_ajuste(
        self, booted: Session, nature: NatureManager
    ) -> None:
        task = awaiting_task(booted, nature)
        task.context = {**task.context, "instrucao_de_ajuste": "Mostrar o cálculo."}
        booted.flush()

        result = reasoning_tools.TOOLS["ler_tarefa"].run(
            ctx_for(booted, None), f"tarefa {task.id}"
        )

        assert "Instrução de ajuste" in result.output
        assert result.payload["instrucao_de_ajuste"] == "Mostrar o cálculo."

    def test_uuid_invalido_cai_na_tarefa_em_revisao(
        self, booted: Session, nature: NatureManager
    ) -> None:
        task = awaiting_task(booted, nature)

        result = reasoning_tools.TOOLS["ler_tarefa"].run(ctx_for(booted, task.id), "-" * 36)

        assert result.payload["task_id"] == str(task.id)

    def test_uuid_desconhecido_cai_na_tarefa_em_revisao(
        self, booted: Session, nature: NatureManager
    ) -> None:
        task = awaiting_task(booted, nature)

        result = reasoning_tools.TOOLS["ler_report"].run(
            ctx_for(booted, task.id), str(uuid.uuid4())
        )

        assert result.payload["task_id"] == str(task.id)

    def test_report_longo_e_truncado(self, booted: Session, nature: NatureManager) -> None:
        task = awaiting_task(booted, nature, "a" * (reasoning_tools.REPORT_VIEW_CHARS + 10))

        result = reasoning_tools.TOOLS["ler_report"].run(ctx_for(booted, task.id), "")

        assert result.payload["truncated"] is True
        assert "[...]" in result.output

    def test_sem_criterios_nem_entregaveis(
        self, booted: Session, nature: NatureManager
    ) -> None:
        task = awaiting_task(booted, nature)
        task.context = {}
        booted.flush()
        ctx = ctx_for(booted, task.id)

        criteria = reasoning_tools.TOOLS["checar_criterios"].run(ctx, "")
        deliverables = reasoning_tools.TOOLS["verificar_entregaveis"].run(ctx, "")

        assert "não declara critérios" in criteria.output
        assert "não declara entregáveis" in deliverables.output

    def test_premissas_com_origem(self, booted: Session, nature: NatureManager) -> None:
        booted.add(
            CorporateMemory(
                memory_type=MemoryType.REPORT,
                title="Pesquisa",
                content="Foram ouvidos 30 clientes.",
                author_role="SUBAGENT",
                importance=5,
                tags={},
            )
        )
        task = awaiting_task(booted, nature)

        result = reasoning_tools.TOOLS["premissas"].run(ctx_for(booted, task.id), "")

        origins = {item["value"]: item["origin"] for item in result.payload["premises"]}
        assert origins["30"] == "memória"
        assert origins["500"] == "cálculo"

    def test_report_sem_numeros(self, booted: Session, nature: NatureManager) -> None:
        task = awaiting_task(booted, nature, "Resultado sem dados quantitativos.")

        result = reasoning_tools.TOOLS["premissas"].run(ctx_for(booted, task.id), "")

        assert "não apresenta números" in result.output


def judge_client(text: str | None) -> OllamaClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if text is None:
            return httpx.Response(500)
        return httpx.Response(200, content=stream_body(text))

    return OllamaClient(transport=httpx.MockTransport(handler))


class TestJuiz:
    @pytest.mark.parametrize(
        "text", [None, "não é json", json.dumps(["lista"]), json.dumps({"atendido": "sim"})]
    )
    def test_saida_ruim_do_juiz_cai_no_lexico(
        self,
        booted: Session,
        nature: NatureManager,
        settings: Settings,
        text: str | None,
    ) -> None:
        task = awaiting_task(booted, nature)
        ctx = ctx_for(booted, task.id, ollama=judge_client(text), settings=settings)

        result = reasoning_tools.TOOLS["checar_criterios"].run(ctx, "")

        assert result.payload["criteria"][0]["metodo"] == "lexico"

    def test_citacao_do_juiz_inexistente_nao_atende(
        self, booted: Session, nature: NatureManager, settings: Settings
    ) -> None:
        task = awaiting_task(booted, nature)
        fake = json.dumps({"atendido": True, "citacao": "lucro de um milhão", "motivo": "ok"})
        ctx = ctx_for(booted, task.id, ollama=judge_client(fake), settings=settings)

        item = reasoning_tools.TOOLS["checar_criterios"].run(ctx, "").payload["criteria"][0]

        assert item["atendido"] is False
        assert item["motivo"] == "citação não encontrada no report"


class TestMotor:
    def test_consult_peers_do_modelo(self, booted: Session, nature: NatureManager) -> None:
        task = awaiting_task(booted, nature)
        fake = ScriptedOllama(FULL_EXPLORATION, [verdict("CONSULT_PEERS")])

        result = agent_decision_engine.review_and_decide(
            booted, task, nature=nature, ollama=fake.client(), settings=model_mode()
        )

        assert result.decision is ChiefDecision.CONSULT_PEERS
        assert result.consulted_roles
        assert task.status is TaskStatus.AWAITING_REVIEW

    def test_report_sem_modelo_veta_aprovacao(
        self, booted: Session, nature: NatureManager
    ) -> None:
        task = awaiting_task(booted, nature)
        report_session = react_engine.run_task(
            booted, agent=None, request=TaskRequest(task="redigir", strict=True), ollama=None
        )
        task.report_reasoning_session_id = report_session.id
        booted.flush()
        fake = ScriptedOllama(FULL_EXPLORATION, [verdict()])

        result = agent_decision_engine.review_and_decide(
            booted, task, nature=nature, ollama=fake.client(), settings=model_mode()
        )

        assert result.decision is ChiefDecision.MODIFY
        assert any("report sem modelo" in item for item in task.review_evidence["vetoes"])

    def test_ceo_no_modo_model_aplica_o_veredito(
        self, booted: Session, nature: NatureManager
    ) -> None:
        task = awaiting_task(booted, nature)
        agent_decision_engine.review_and_decide(
            booted,
            task,
            nature=nature,
            ollama=ScriptedOllama(FULL_EXPLORATION, ["{}", "{}"]).client(),
            settings=model_mode(),
        )
        assert task.decision is ChiefDecision.ESCALATE

        final = agent_decision_engine.ceo_final_decision(
            booted,
            task,
            nature=nature,
            ollama=ScriptedOllama(FULL_EXPLORATION, [verdict()]).client(),
            settings=model_mode(),
        )

        assert final.decision is ChiefDecision.APPROVE
        assert final.decision_source is DecisionSource.MODEL
        assert task.review_evidence["escalated_from"]["decision_source"] == "INVALID_OUTPUT"

    def test_ceo_inexistente(self, booted: Session, nature: NatureManager) -> None:
        task = awaiting_task(booted, nature)
        ceo = agent_service.get_chief(booted, AgentRole.CEO)
        assert ceo is not None
        booted.delete(ceo)
        booted.flush()

        with pytest.raises(agent_decision_engine.HierarchyError):
            agent_decision_engine.ceo_final_decision(booted, task, nature=nature)

    @pytest.mark.parametrize(
        ("score", "available", "expected"),
        [
            (90, True, ChiefDecision.APPROVE),
            (90, False, ChiefDecision.MODIFY),
            (70, True, ChiefDecision.MODIFY),
            (40, True, ChiefDecision.REJECT),
        ],
    )
    def test_desempate_conservador(
        self,
        booted: Session,
        nature: NatureManager,
        score: int,
        available: bool,
        expected: ChiefDecision,
    ) -> None:
        task = awaiting_task(booted, nature)
        base = report_analysis.assess(booted, task, GOOD_REPORT)
        assessment = replace(
            base,
            quality=replace(base.quality, score=score),
            comparison=replace(base.comparison, gaps=()),
        )

        assert (
            agent_decision_engine._tiebreak(assessment, model_available=available) is expected
        )


class TestPipelineBordas:
    def test_ollama_cai_durante_o_veredito(
        self, booted: Session, nature: NatureManager, settings: Settings
    ) -> None:
        task = awaiting_task(booted, nature)
        turns = list(FULL_EXPLORATION)

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            schema = body.get("format")
            if isinstance(schema, dict) and "veredito" in schema.get("properties", {}):
                return httpx.Response(500)
            if isinstance(schema, dict):
                text = json.dumps({"atendido": True, "citacao": QUOTE, "motivo": "ok"})
            else:
                text = turns.pop(0)
            return httpx.Response(200, content=stream_body(text))

        chief = agent_service.get_chief(booted, AgentRole.CFO)
        assert chief is not None
        outcome = chief_review.review(
            booted,
            task,
            chief,
            allowed=tuple(ChiefDecision),
            instruction="Revisar",
            context={},
            settings=settings,
            nature=nature,
            ollama=OllamaClient(transport=httpx.MockTransport(handler)),
        )

        assert outcome.source is DecisionSource.UNAVAILABLE
        assert outcome.errors[0].startswith(react_engine.CAUSE_OLLAMA_UNAVAILABLE)

    def test_approve_sem_julgar_todos_os_criterios(
        self, booted: Session, nature: NatureManager, settings: Settings
    ) -> None:
        task = awaiting_task(booted, nature)
        task.context = {**task.context, "acceptance_criteria": ["A", "B"]}
        observed = [react_engine.Observed("O1", "ler_report", "", "ok")]

        _, problems = chief_review.validate(verdict(), task, observed, tuple(ChiefDecision))

        assert "approve_sem_julgar_todos_os_criterios" in problems

    def test_motor_que_falha_vira_causa(self) -> None:
        broken = ReasoningSession(task="x", error="boom", conclusion=None)

        assert chief_review._unavailable_cause(broken) == "motor_falhou: boom"

    def test_feedback_sem_veredito_usa_criterios_observados(self) -> None:
        observed = [
            react_engine.Observed(
                "O1",
                "checar_criterios",
                "",
                "",
                {"criteria": [{"criterio": "C", "atendido": False, "citacao": ""}]},
            )
        ]
        outcome = chief_review.ReviewOutcome(
            reasoning=ReasoningSession(task="x"),
            observations=observed,
            source=DecisionSource.UNAVAILABLE,
        )

        assert outcome.feedback()[0].criterio == "C"
        assert outcome.decision is None


class TestReactEstrito:
    def test_formato_invalido_e_sem_acao_recebem_cutucada(
        self, db_session: Session
    ) -> None:
        ollama = make_react_ollama(
            [
                "texto sem rótulo nenhum",
                "Pensamento: penso mas não ajo",
                "Pensamento: pronto\nConclusão: feito",
            ]
        )

        session = react_engine.run_task(
            db_session,
            agent=None,
            request=TaskRequest(task="revisar", strict=True, max_steps=5),
            ollama=ollama,
        )

        assert session.conclusion == "feito"
        assert session.step_count >= 5
