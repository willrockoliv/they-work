"""API da Fase 2: conselho, RA, Banco de Talentos e auditoria da Natureza."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config.database import get_db_session
from app.main import create_app
from app.routes.deps import get_ollama_client
from app.services.nature_manager import get_nature_manager
from tests.conftest import make_nature, make_ollama

PEDIDO_COMPLETO = {
    "requested_by": "CTO",
    "job_title": "Analista de Dados",
    "objective": "Analisar as metricas de uso do produto e apontar gargalos de retencao.",
    "specialization": "métricas de produto",
    "deliverables": ["Relatório de retenção"],
    "tools": ["planilha"],
}


@pytest.fixture
def client_com_chiefs(client: TestClient) -> TestClient:
    client.post("/agents/chiefs/init")
    return client


class TestConselho:
    def test_init_profiles_e_idempotente(self, client_com_chiefs: TestClient) -> None:
        primeiro = client_com_chiefs.post("/council/profiles/init")
        segundo = client_com_chiefs.post("/council/profiles/init")

        assert primeiro.status_code == 201
        assert primeiro.json()["total"] == 5
        assert segundo.json()["total"] == 5

    def test_lista_perfis_ordenados_por_prioridade(self, client_com_chiefs: TestClient) -> None:
        client_com_chiefs.post("/council/profiles/init")

        corpo = client_com_chiefs.get("/council/profiles").json()

        assert corpo["profiles"][0]["role"] == "CEO"
        assert corpo["profiles"][0]["mission"]

    def test_deliberacao_retorna_pareceres_e_veredito(self, client: TestClient) -> None:
        resposta = client.post(
            "/council/deliberate",
            json={
                "topic": "SaaS de atas",
                "description": (
                    "Produto para o mercado de pequenas empresas, com persona de gestores, "
                    "receita por assinatura, custo estimado e estrategia de canal."
                ),
            },
        )

        corpo = resposta.json()
        assert resposta.status_code == 200
        assert corpo["outcome"] in {"APPROVED", "APPROVED_WITH_CONDITIONS"}
        assert len(corpo["opinions"]) == 4

    def test_comunicacoes_filtram_por_thread(self, client: TestClient) -> None:
        thread_id = client.post(
            "/council/deliberate",
            json={"topic": "Pauta", "description": "Avaliar o mercado de gestores."},
        ).json()["thread_id"]

        corpo = client.get("/council/communications", params={"thread_id": thread_id}).json()

        assert corpo["total"] == 5
        assert all(item["thread_id"] == thread_id for item in corpo["communications"])

    def test_memoria_do_chief(self, client_com_chiefs: TestClient) -> None:
        client_com_chiefs.post("/council/profiles/init")

        resposta = client_com_chiefs.post(
            "/council/profiles/CEO/memory",
            json={"fact": "Caixa inicial de 10 mil.", "importance": 9},
        )

        assert resposta.status_code == 200
        assert resposta.json()["context_memory"]["facts"][-1]["importance"] == 9

    def test_memoria_sem_perfil_retorna_404(self, client: TestClient) -> None:
        resposta = client.post("/council/profiles/CEO/memory", json={"fact": "qualquer"})

        assert resposta.status_code == 404


class TestContratacao:
    def test_pedido_vago_devolve_perguntas(self, client_com_chiefs: TestClient) -> None:
        resposta = client_com_chiefs.post(
            "/hiring/requests", json={"requested_by": "CMO", "job_title": "ajudante"}
        )

        corpo = resposta.json()
        assert resposta.status_code == 201
        assert corpo["request"]["status"] == "NEEDS_CLARIFICATION"
        assert corpo["questions"]
        assert corpo["agent"] is None

    def test_pedido_completo_contrata(self, client_com_chiefs: TestClient) -> None:
        corpo = client_com_chiefs.post("/hiring/requests", json=PEDIDO_COMPLETO).json()

        assert corpo["request"]["status"] == "FULFILLED"
        assert corpo["agent"]["job_title"] == "Analista de Dados"
        assert corpo["resources"]["active_subagents"] == 1

    def test_esclarecimento_retoma_o_fluxo(self, client_com_chiefs: TestClient) -> None:
        pendente = client_com_chiefs.post(
            "/hiring/requests", json={"requested_by": "CMO", "job_title": "ajudante"}
        ).json()

        resposta = client_com_chiefs.post(
            f"/hiring/requests/{pendente['request']['id']}/clarify",
            json={
                "job_title": "Redator de Conteúdo",
                "objective": "Produzir artigos semanais sobre produtividade para o blog.",
                "specialization": "conteúdo",
                "deliverables": ["4 artigos por mês"],
            },
        )

        assert resposta.status_code == 200
        assert resposta.json()["request"]["status"] == "FULFILLED"

    def test_esclarecer_requisicao_encerrada_retorna_409(
        self, client_com_chiefs: TestClient
    ) -> None:
        concluida = client_com_chiefs.post("/hiring/requests", json=PEDIDO_COMPLETO).json()

        resposta = client_com_chiefs.post(
            f"/hiring/requests/{concluida['request']['id']}/clarify", json={"objective": "x"}
        )

        assert resposta.status_code == 409

    def test_requisicao_inexistente_retorna_404(self, client: TestClient) -> None:
        inexistente = "00000000-0000-0000-0000-000000000000"

        assert client.get(f"/hiring/requests/{inexistente}").status_code == 404

    def test_lista_requisicoes_por_status(self, client_com_chiefs: TestClient) -> None:
        client_com_chiefs.post("/hiring/requests", json=PEDIDO_COMPLETO)
        client_com_chiefs.post(
            "/hiring/requests", json={"requested_by": "CMO", "job_title": "ajudante"}
        )

        corpo = client_com_chiefs.get(
            "/hiring/requests", params={"request_status": "FULFILLED"}
        ).json()

        assert corpo["total"] == 1


class TestBancoDeTalentos:
    def test_perfil_e_arquivado_apos_a_contratacao(self, client_com_chiefs: TestClient) -> None:
        client_com_chiefs.post("/hiring/requests", json=PEDIDO_COMPLETO)

        corpo = client_com_chiefs.get("/talent/profiles").json()

        assert corpo["total"] == 1
        assert corpo["profiles"][0]["usage_count"] == 1
        assert corpo["profiles"][0]["system_prompt"].startswith("# Cargo:")

    def test_busca_encontra_perfil_existente(self, client_com_chiefs: TestClient) -> None:
        client_com_chiefs.post("/hiring/requests", json=PEDIDO_COMPLETO)

        corpo = client_com_chiefs.get(
            "/talent/profiles/search", params={"role_title": "Analista de Dados"}
        ).json()

        assert corpo["found"] is True
        assert corpo["matched_on"] == "slug"

    def test_busca_sem_resultado(self, client: TestClient) -> None:
        corpo = client.get(
            "/talent/profiles/search", params={"role_title": "Astronauta"}
        ).json()

        assert corpo["found"] is False

    def test_historico_de_versoes(self, client_com_chiefs: TestClient) -> None:
        client_com_chiefs.post("/hiring/requests", json=PEDIDO_COMPLETO)

        corpo = client_com_chiefs.get("/talent/profiles/analista-de-dados/versions").json()

        assert corpo["total"] == 1

    def test_historico_de_perfil_inexistente(self, client: TestClient) -> None:
        assert client.get("/talent/profiles/inexistente/versions").status_code == 404

    def test_avaliacao_atualiza_a_media(self, client_com_chiefs: TestClient) -> None:
        client_com_chiefs.post("/hiring/requests", json=PEDIDO_COMPLETO)
        profile_id = client_com_chiefs.get("/talent/profiles").json()["profiles"][0]["id"]

        corpo = client_com_chiefs.post(
            f"/talent/profiles/{profile_id}/rating", json={"rating": 5, "feedback": "ótimo"}
        ).json()

        assert corpo["average_rating"] == 5.0
        assert corpo["rating_count"] == 1

    def test_avaliacao_de_perfil_inexistente(self, client: TestClient) -> None:
        inexistente = "00000000-0000-0000-0000-000000000000"

        resposta = client.post(f"/talent/profiles/{inexistente}/rating", json={"rating": 3})

        assert resposta.status_code == 404


class TestDemissao:
    def test_demissao_libera_a_estacao(self, client_com_chiefs: TestClient) -> None:
        agent_id = client_com_chiefs.post("/hiring/requests", json=PEDIDO_COMPLETO).json()[
            "agent"
        ]["id"]

        resposta = client_com_chiefs.post(
            f"/agents/subagents/{agent_id}/dismiss",
            json={"reason": "sprint concluída", "final_report": "Tudo certo.", "rating": 4},
        )

        assert resposta.status_code == 200
        assert resposta.json()["status"] == "TERMINATED"
        assert client_com_chiefs.get("/resources/status").json()["active_subagents"] == 0

    def test_chief_nao_pode_ser_demitido(self, client_com_chiefs: TestClient) -> None:
        ceo = client_com_chiefs.get("/agents/status").json()["chiefs"][0]

        resposta = client_com_chiefs.post(
            f"/agents/subagents/{ceo['id']}/dismiss", json={"reason": "teste"}
        )

        assert resposta.status_code == 422

    def test_demissao_de_agente_inexistente(self, client: TestClient) -> None:
        inexistente = "00000000-0000-0000-0000-000000000000"

        resposta = client.post(
            f"/agents/subagents/{inexistente}/dismiss", json={"reason": "teste"}
        )

        assert resposta.status_code == 404


class TestAuditoriaDaNatureza:
    def test_audit_request_aprova_com_narrativa(self, client: TestClient) -> None:
        corpo = client.post(
            "/nature/audit-request",
            json={"requested_by": "CTO", "job_title": "Arquiteto", "complexity": "COMPLEX"},
        ).json()

        assert corpo["decision"] == "ALLOWED"
        assert corpo["granted_model"] == "qwen3:8b"
        assert corpo["narrative"]

    def test_audit_request_forca_downgrade(self, db_session: Session) -> None:
        apertada = make_nature(ram_total=16_384, ram_used=12_236)
        app = create_app()
        app.dependency_overrides[get_db_session] = lambda: db_session
        app.dependency_overrides[get_nature_manager] = lambda: apertada
        app.dependency_overrides[get_ollama_client] = lambda: make_ollama()

        with TestClient(app) as cliente:
            corpo = cliente.post(
                "/nature/audit-request",
                json={
                    "requested_by": "CTO",
                    "job_title": "Arquiteto",
                    "complexity": "CRITICAL",
                    "requested_model": "deepseek-r1:8b",
                },
            ).json()

        assert corpo["decision"] == "DOWNGRADED"
        assert corpo["granted_model"] == "llama3.2:3b"

    def test_alertas_em_infraestrutura_saudavel(self, client: TestClient) -> None:
        corpo = client.get("/nature/alerts").json()

        assert corpo["status"] == "HEALTHY"
        assert corpo["total"] == 0

    def test_alertas_em_infraestrutura_critica(self, db_session: Session) -> None:
        esgotada = make_nature(ram_total=16_384, ram_used=16_300)
        app = create_app()
        app.dependency_overrides[get_db_session] = lambda: db_session
        app.dependency_overrides[get_nature_manager] = lambda: esgotada
        app.dependency_overrides[get_ollama_client] = lambda: make_ollama()

        with TestClient(app) as cliente:
            corpo = cliente.get("/nature/alerts").json()

        assert corpo["status"] == "CRITICAL"
        assert any(alerta["code"] == "CAPACITY_EXHAUSTED" for alerta in corpo["alerts"])


class TestFluxoCompleto:
    def test_chief_ra_natureza_subagente(self, app: FastAPI, client: TestClient) -> None:
        """Cadeia completa: conselho delibera, RA contrata e o subagente é demitido."""
        client.post("/agents/chiefs/init")
        client.post("/council/profiles/init")

        decisao = client.post(
            "/council/deliberate",
            json={
                "topic": "Produto de analytics",
                "description": (
                    "Atender o mercado de gestores com receita por assinatura e custo "
                    "controlado, dentro da estrategia de longo prazo."
                ),
            },
        ).json()
        assert decisao["outcome"] != "REJECTED"

        contratacao = client.post("/hiring/requests", json=PEDIDO_COMPLETO).json()
        assert contratacao["request"]["status"] == "FULFILLED"

        recontratacao = client.post("/hiring/requests", json=PEDIDO_COMPLETO).json()
        assert recontratacao["reused_profile"] is True

        for vaga in (contratacao, recontratacao):
            client.post(
                f"/agents/subagents/{vaga['agent']['id']}/dismiss",
                json={"reason": "fim da sprint", "rating": 5},
            )

        status = client.get("/agents/status").json()
        assert status["total"] == 5
        assert client.get("/talent/profiles").json()["profiles"][0]["usage_count"] == 2
