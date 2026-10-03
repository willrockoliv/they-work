"""API da Fase 3: execução observável, fluxograma, status ao vivo, métricas e WebSocket."""

from __future__ import annotations

import time
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config.database import get_db_session
from app.config.settings import Settings
from app.main import create_app
from app.models.base import utcnow
from app.routes.deps import get_ollama_client
from app.services.nature_manager import NatureManager, get_nature_manager
from app.services.reasoning_tracer import ReasoningTracer
from tests.conftest import make_nature, make_react_ollama
from tests.test_reasoning_tracer import make_agent

TAREFA = {"task": "Avaliar se devemos investir em retenção de clientes neste trimestre"}


@pytest.fixture
def agent_id(db_session: Session) -> str:
    return str(make_agent(db_session).id)


def app_com_roteiro(db_session: Session, nature: NatureManager, turns: list[str]) -> FastAPI:
    """App em que o Ollama devolve respostas ReAct previsíveis."""
    application = create_app()
    application.dependency_overrides[get_db_session] = lambda: db_session
    application.dependency_overrides[get_nature_manager] = lambda: nature
    application.dependency_overrides[get_ollama_client] = lambda: make_react_ollama(turns)
    return application


class TestExecucao:
    def test_run_devolve_sessao_com_todos_os_passos(
        self, db_session: Session, agent_id: str
    ) -> None:
        application = app_com_roteiro(
            db_session,
            make_nature(),
            [
                "Pensamento: preciso de contexto\nAção: auditoria\nEntrada da Ação: retenção",
                "Pensamento: pronto\nConclusão: investir com meta de 5% ao mês",
            ],
        )
        with TestClient(application) as client:
            resposta = client.post(f"/agents/{agent_id}/reasoning/run", json=TAREFA)

        corpo = resposta.json()
        assert resposta.status_code == 201
        assert corpo["status"] == "COMPLETED"
        assert corpo["conclusion"] == "investir com meta de 5% ao mês"
        assert [step["step_type"] for step in corpo["steps"]] == [
            "THOUGHT",
            "ACTION",
            "OBSERVATION",
            "THOUGHT",
            "CONCLUSION",
        ]

    def test_run_em_agente_inexistente_retorna_404(self, client: TestClient) -> None:
        resposta = client.post(
            "/agents/00000000-0000-0000-0000-000000000000/reasoning/run", json=TAREFA
        )

        assert resposta.status_code == 404

    def test_tarefa_vazia_e_rejeitada(self, client: TestClient, agent_id: str) -> None:
        resposta = client.post(f"/agents/{agent_id}/reasoning/run", json={"task": "a"})

        assert resposta.status_code == 422

    def test_agentes_simultaneos_mantem_sessoes_isoladas(
        self, client: TestClient, db_session: Session
    ) -> None:
        primeiro = str(make_agent(db_session).id)
        segundo = str(make_agent(db_session).id)

        client.post(f"/agents/{primeiro}/reasoning/run", json=TAREFA)
        client.post(f"/agents/{segundo}/reasoning/run", json=TAREFA)

        sessoes = client.get("/reasoning/sessions").json()
        agentes = {sessao["agent_id"] for sessao in sessoes["sessions"]}
        assert sessoes["total"] == 2
        assert agentes == {primeiro, segundo}


class TestFluxogramaEStatus:
    def test_fluxograma_do_agente(self, client: TestClient, agent_id: str) -> None:
        client.post(f"/agents/{agent_id}/reasoning/run", json=TAREFA)

        corpo = client.get(f"/agents/{agent_id}/reasoning-flow").json()

        assert corpo["nodes"][0]["type"] == "TASK"
        assert corpo["meta"]["status"] == "COMPLETED"
        assert len(corpo["edges"]) == len(corpo["nodes"]) - 1

    def test_fluxograma_sem_raciocinio_retorna_404(
        self, client: TestClient, agent_id: str
    ) -> None:
        assert client.get(f"/agents/{agent_id}/reasoning-flow").status_code == 404

    def test_live_status_antes_de_qualquer_execucao(
        self, client: TestClient, agent_id: str
    ) -> None:
        corpo = client.get(f"/agents/{agent_id}/live-status").json()

        assert corpo["session_id"] is None
        assert corpo["progress"] == 0.0

    def test_live_status_apos_execucao(self, client: TestClient, agent_id: str) -> None:
        client.post(f"/agents/{agent_id}/reasoning/run", json=TAREFA)

        corpo = client.get(f"/agents/{agent_id}/live-status").json()

        assert corpo["reasoning_status"] == "COMPLETED"
        assert corpo["progress"] == 1.0
        assert corpo["last_step_type"] == "CONCLUSION"
        assert corpo["agent_status"] == "IDLE"

    def test_fluxograma_de_sessao_especifica(self, client: TestClient, agent_id: str) -> None:
        sessao = client.post(f"/agents/{agent_id}/reasoning/run", json=TAREFA).json()

        corpo = client.get(f"/reasoning/sessions/{sessao['id']}/flow").json()

        assert corpo["meta"]["session_id"] == sessao["id"]

    def test_sessao_inexistente_retorna_404(self, client: TestClient) -> None:
        vazio = "00000000-0000-0000-0000-000000000000"
        assert client.get(f"/reasoning/sessions/{vazio}").status_code == 404
        assert client.get(f"/reasoning/sessions/{vazio}/flow").status_code == 404


class TestHistorico:
    def test_replay_completo_da_sessao(self, client: TestClient, agent_id: str) -> None:
        sessao = client.post(f"/agents/{agent_id}/reasoning/run", json=TAREFA).json()

        corpo = client.get(f"/reasoning/sessions/{sessao['id']}").json()

        assert corpo["id"] == sessao["id"]
        assert len(corpo["steps"]) == sessao["step_count"]

    def test_lista_filtra_por_status(self, client: TestClient, agent_id: str) -> None:
        client.post(f"/agents/{agent_id}/reasoning/run", json=TAREFA)

        completas = client.get("/reasoning/sessions?reasoning_status=COMPLETED").json()
        falhas = client.get("/reasoning/sessions?reasoning_status=FAILED").json()

        assert completas["total"] == 1
        assert falhas["total"] == 0


class TestMetricasERetencao:
    def test_metricas_consolidadas(self, client: TestClient, agent_id: str) -> None:
        client.post(f"/agents/{agent_id}/reasoning/run", json=TAREFA)

        corpo = client.get("/reasoning/metrics").json()

        assert corpo["total_sessions"] == 1
        assert corpo["completed"] == 1
        assert corpo["success_rate"] == 1.0
        assert corpo["by_agent"][0]["agent_id"] == agent_id

    def test_export_das_sessoes(self, client: TestClient, agent_id: str) -> None:
        client.post(f"/agents/{agent_id}/reasoning/run", json=TAREFA)

        corpo = client.get("/reasoning/export").json()

        assert corpo["total"] == 1
        assert corpo["sessions"][0]["steps"]

    def test_purge_respeita_o_corte(
        self, client: TestClient, db_session: Session, agent_id: str
    ) -> None:
        client.post(f"/agents/{agent_id}/reasoning/run", json=TAREFA)
        corte = (utcnow() + timedelta(days=1)).isoformat()

        corpo = client.post("/reasoning/retention/purge", json={"before": corte}).json()

        assert corpo["removed"] == 1
        assert client.get("/reasoning/sessions").json()["total"] == 0


class TestWebSocket:
    def test_replay_entrega_passos_ja_capturados(
        self, client: TestClient, agent_id: str
    ) -> None:
        client.post(f"/agents/{agent_id}/reasoning/run", json=TAREFA)

        with client.websocket_connect(f"/ws/agents/{agent_id}/reasoning") as ws:
            mensagem = ws.receive_json()

        assert mensagem["event"] == "replay"
        assert mensagem["data"]["status"] == "COMPLETED"
        assert mensagem["data"]["steps"]

    def test_replay_vazio_quando_agente_nunca_raciocinou(
        self, client: TestClient, agent_id: str
    ) -> None:
        with client.websocket_connect(f"/ws/agents/{agent_id}/reasoning") as ws:
            mensagem = ws.receive_json()

        assert mensagem["data"] is None

    def test_canal_global_recebe_passos_ao_vivo(
        self, client: TestClient, agent_id: str
    ) -> None:
        with client.websocket_connect("/ws/reasoning") as ws:
            client.post(f"/agents/{agent_id}/reasoning/run", json=TAREFA)
            eventos = [ws.receive_json() for _ in range(3)]

        assert eventos[0]["event"] == "session.started"
        assert eventos[1]["event"] == "step"
        assert eventos[1]["data"]["step_type"] == "THOUGHT"


class TestOverhead:
    def test_captura_nao_domina_o_tempo_de_execucao(
        self, db_session: Session, settings: Settings, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A persistência dos passos deve pesar pouco diante do próprio raciocínio."""
        agent = make_agent(db_session)

        def executar() -> float:
            inicio = time.perf_counter()
            for _ in range(20):
                tracer = ReasoningTracer(db_session, task="Tarefa", agent=agent)
                tracer.start()
                tracer.on_thought("pensando")
                tracer.on_action("auditoria", "tudo")
                tracer.on_observation("nada")
                tracer.on_conclusion("fim")
                tracer.complete("fim")
            return time.perf_counter() - inicio

        com_captura = executar()
        monkeypatch.setattr(settings, "reasoning_capture_enabled", False)
        sem_captura = executar()

        # O custo extra da captura fica na mesma ordem de grandeza da execução sem ela.
        assert com_captura < sem_captura * 10 + 1.0
