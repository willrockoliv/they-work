"""Testes de integração da API HTTP (banco em memória, Ollama simulado)."""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.models.enums import NatureDecision, ResourceStatus
from app.routes.deps import get_ollama_client
from app.services.nature_manager import get_nature_manager
from tests.conftest import make_nature, make_ollama


class TestHealth:
    def test_liveness(self, client: TestClient) -> None:
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_health_ok_com_todas_as_dependencias(self, client: TestClient) -> None:
        body = client.get("/health").json()

        assert body["status"] == "ok"
        assert body["app_name"] == "TheyWork"
        assert {component["name"] for component in body["components"]} == {"postgres", "ollama"}
        assert all(component["status"] == "ok" for component in body["components"])

    def test_health_degradado_quando_ollama_cai(self, app: FastAPI) -> None:
        def _down(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("conexão recusada")

        app.dependency_overrides[get_ollama_client] = lambda: make_ollama(
            httpx.MockTransport(_down)
        )
        with TestClient(app) as client:
            body = client.get("/health").json()

        assert body["status"] == "degraded"
        ollama = next(c for c in body["components"] if c["name"] == "ollama")
        assert ollama["status"] == "down"


class TestResources:
    def test_status_de_recursos(self, client: TestClient) -> None:
        body = client.get("/resources/status").json()

        assert body["status"] == ResourceStatus.HEALTHY.value
        assert body["ram_limit_mb"] == 16_384
        assert body["ram_allocatable_mb"] == 10_336
        assert body["gpu_detected"] is True
        assert body["active_subagents"] == 0
        assert body["max_concurrent_subagents"] == 4
        assert body["narrative"]

    def test_avaliacao_de_contratacao_aprovada(self, client: TestClient) -> None:
        body = client.post(
            "/resources/hiring/evaluate",
            json={
                "requested_by": "CTO",
                "job_title": "Engenheiro de Dados",
                "complexity": "COMPLEX",
            },
        ).json()

        assert body["decision"] == NatureDecision.ALLOWED.value
        assert body["allowed"] is True
        assert body["granted_model"] == "qwen3:8b"
        assert body["resources"]["status"] == ResourceStatus.HEALTHY.value

    def test_avaliacao_bloqueada_registra_auditoria(self, app: FastAPI) -> None:
        app.dependency_overrides[get_nature_manager] = lambda: make_nature(ram_used=15_500)
        with TestClient(app) as client:
            body = client.post(
                "/resources/hiring/evaluate",
                json={"requested_by": "CMO", "job_title": "Redator", "complexity": "SIMPLE"},
            ).json()

            assert body["decision"] == NatureDecision.QUEUED.value
            assert body["allowed"] is False
            assert body["granted_model"] is None
            assert body["queue_position"] == 1

    def test_payload_invalido(self, client: TestClient) -> None:
        response = client.post("/resources/hiring/evaluate", json={"requested_by": "X"})
        assert response.status_code == 422


class TestAgents:
    def test_init_chiefs_e_status(self, client: TestClient) -> None:
        created = client.post("/agents/chiefs/init")
        assert created.status_code == 201
        assert created.json()["created"] == 5
        assert created.json()["total"] == 5

        again = client.post("/agents/chiefs/init")
        assert again.json()["created"] == 0

        status = client.get("/agents/status").json()
        assert status["total"] == 5
        assert len(status["chiefs"]) == 5
        assert status["subagents"] == []

    def test_status_vazio_antes_da_inicializacao(self, client: TestClient) -> None:
        body = client.get("/agents/status").json()
        assert body == {"total": 0, "chiefs": [], "subagents": []}


class TestModels:
    def test_models_available_cruza_catalogo_com_ollama(self, client: TestClient) -> None:
        body = client.get("/models/available").json()

        assert body["ollama_reachable"] is True
        assert body["ollama_version"] == "0.12.11"
        assert len(body["models"]) == 5

        llama = next(m for m in body["models"] if m["name"] == "llama3.2:3b")
        assert llama["installed"] is True
        assert llama["installed_size_mb"] == 2_048
        assert llama["fits_current_budget"] is True

        deepseek = next(m for m in body["models"] if m["name"] == "deepseek-r1:8b")
        assert deepseek["installed"] is False

    def test_models_available_com_ollama_indisponivel(self, app: FastAPI) -> None:
        def _down(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("conexão recusada")

        app.dependency_overrides[get_ollama_client] = lambda: make_ollama(
            httpx.MockTransport(_down)
        )
        with TestClient(app) as client:
            body = client.get("/models/available").json()

        assert body["ollama_reachable"] is False
        assert all(model["installed"] is False for model in body["models"])

    @pytest.mark.parametrize(
        ("complexity", "expected"),
        [("SIMPLE", "llama3.2:3b"), ("MODERATE", "phi4-mini:3.8b"), ("CRITICAL", "deepseek-r1:8b")],
    )
    def test_selecao_automatica_de_modelo(
        self, client: TestClient, complexity: str, expected: str
    ) -> None:
        body = client.get("/models/select", params={"complexity": complexity}).json()

        assert body["selected_model"] == expected
        assert body["downgraded"] is False

    def test_selecao_sofre_downgrade_sob_pressao(self, app: FastAPI) -> None:
        app.dependency_overrides[get_nature_manager] = lambda: make_nature(ram_used=11_000)
        with TestClient(app) as client:
            body = client.get("/models/select", params={"complexity": "CRITICAL"}).json()

        assert body["preferred_model"] == "deepseek-r1:8b"
        assert body["selected_model"] == "gemma3n:e4b"
        assert body["downgraded"] is True
