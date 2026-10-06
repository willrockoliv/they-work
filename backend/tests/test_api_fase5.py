"""API da Fase 5 — pedidos, grafo, RA, delegação e vereditos dos Chiefs."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.services import network_orchestrator

TOPIC = "Fundar uma startup de triagem documental"
DESCRIPTION = (
    "Queremos lançar um produto de automação de triagem documental para escritórios "
    "de advocacia de médio porte. A persona é o sócio operacional e a receita vem de "
    "uma assinatura mensal por usuário, com custo de inferência local."
)


@pytest.fixture
def booted(client: TestClient) -> TestClient:
    assert client.post("/company/bootstrap").status_code == 201
    return client


def test_bootstrap_funda_a_empresa_e_e_idempotente(client: TestClient) -> None:
    assert client.get("/company/status").json()["total"] == 0

    first = client.post("/company/bootstrap")
    assert first.status_code == 201
    body = first.json()
    assert body["created"] == 5
    assert body["total"] == 5
    # Só `chiefs/init` deixaria o conselho sem persona: o bootstrap faz os dois passos.
    assert body["profiles"] == 5

    second = client.post("/company/bootstrap").json()
    assert second["created"] == 0
    assert second["total"] == 5
    assert client.get("/company/status").json()["total"] == 5


def test_pedido_sem_empresa_fundada_e_recusado(client: TestClient) -> None:
    response = client.post(
        "/council/request-action", json={"topic": TOPIC, "description": DESCRIPTION}
    )
    assert response.status_code == 409
    assert "não foi fundada" in response.json()["detail"]
    # Nada deve ter sido gravado.
    assert client.get("/council/requests").json()["total"] == 0


def test_start_devolve_na_hora_e_trabalha_depois(booted: TestClient) -> None:
    request_id = _submit(booted)["request"]["id"]

    response = booted.post(f"/council/requests/{request_id}/start")
    assert response.status_code == 202
    body = response.json()
    assert body["request"]["id"] == request_id
    assert body["started"] is True

    # A BackgroundTask do TestClient roda ao fechar a resposta: o turno já aconteceu.
    graph = booted.get(f"/council/requests/{request_id}/graph").json()
    kinds = {edge["communication_type"] for edge in graph["edges"]}
    assert {"AGENT_REQUEST", "AGENT_CREATED", "DELEGATION", "REPORT", "DECISION"} <= kinds
    assert len(graph["tasks"]) >= 3


def test_start_nao_empilha_turnos_do_mesmo_pedido(booted: TestClient) -> None:
    """Um turno leva minutos: clicar de novo não pode duplicar o trabalho."""
    request_id = _submit(booted)["request"]["id"]

    with network_orchestrator.turn(uuid.UUID(request_id)) as acquired:
        assert acquired
        response = booted.post(f"/council/requests/{request_id}/start")
        assert response.status_code == 202
        assert response.json()["started"] is False


def _chief_id(client: TestClient, role: str) -> str:
    chiefs = client.get("/agents/status").json()["chiefs"]
    return next(chief["id"] for chief in chiefs if chief["role"] == role)


def _submit(client: TestClient, *, auto_deliberate: bool = True) -> dict[str, Any]:
    response = client.post(
        "/council/request-action",
        json={"topic": TOPIC, "description": DESCRIPTION, "auto_deliberate": auto_deliberate},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_submeter_pedido_devolve_grafo(booted: TestClient) -> None:
    body = _submit(booted)

    assert body["request"]["topic"] == TOPIC
    assert body["request"]["status"] == "DELIBERATING"
    assert body["graph"]["nodes"][0]["id"] == "observer"
    kinds = {edge["communication_type"] for edge in body["graph"]["edges"]}
    assert {"REQUEST", "OPINION", "COORDINATION"} <= kinds


def test_pedido_sem_deliberacao_automatica(booted: TestClient) -> None:
    body = _submit(booted, auto_deliberate=False)
    assert body["request"]["status"] == "PROPOSED"
    assert len(body["graph"]["edges"]) == 1


def test_listar_e_detalhar_pedidos(booted: TestClient) -> None:
    request_id = _submit(booted)["request"]["id"]

    listing = booted.get("/council/requests").json()
    assert listing["total"] == 1

    detail = booted.get(f"/council/requests/{request_id}").json()
    assert detail["request"]["id"] == request_id

    graph = booted.get(f"/council/requests/{request_id}/graph").json()
    assert graph["request_id"] == request_id


def test_pedido_inexistente_devolve_404(booted: TestClient) -> None:
    missing = "00000000-0000-0000-0000-000000000000"
    assert booted.get(f"/council/requests/{missing}").status_code == 404


def test_chief_pede_agente_ao_ra(booted: TestClient) -> None:
    request_id = _submit(booted)["request"]["id"]

    response = booted.post(
        "/ra/create-agent",
        json={
            "requesting_chief": "CTO",
            "request_id": request_id,
            "job_title": "Engenheiro de Software",
            "objective": "Desenhar a arquitetura do motor de triagem documental offline",
            "specialization": "backend",
            "deliverables": ["Desenho da arquitetura", "Plano de testes"],
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["agent"] is not None
    assert body["reporting_chief"] == "CTO"
    assert body["agent"]["reports_to_id"] == _chief_id(booted, "CTO")

    created = booted.get("/ra/created-agents").json()
    assert created["total"] == 1


def test_ra_devolve_perguntas_para_pedido_vago(booted: TestClient) -> None:
    request_id = _submit(booted)["request"]["id"]
    response = booted.post(
        "/ra/create-agent",
        json={"requesting_chief": "CTO", "request_id": request_id, "job_title": "dev"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["agent"] is None
    assert body["questions"]


def test_ra_nao_pode_solicitar_agente_para_si(booted: TestClient) -> None:
    request_id = _submit(booted)["request"]["id"]
    response = booted.post(
        "/ra/create-agent",
        json={
            "requesting_chief": "RA",
            "request_id": request_id,
            "job_title": "Engenheiro de Software",
            "objective": "Desenhar a arquitetura do motor de triagem documental offline",
            "deliverables": ["Desenho da arquitetura"],
        },
    )
    assert response.status_code == 409
    assert "Chief supervisor" in response.json()["detail"]


def test_delegacao_report_e_veredito(booted: TestClient) -> None:
    request_id = _submit(booted)["request"]["id"]
    cmo_id = _chief_id(booted, "CMO")

    agent = booted.post(
        "/ra/create-agent",
        json={
            "requesting_chief": "CMO",
            "request_id": request_id,
            "job_title": "Analista de Mercado",
            "objective": "Mapear personas e concorrentes do segmento juridico de medio porte",
            "specialization": "pesquisa de mercado",
            "deliverables": ["Mapa de personas", "Analise de concorrentes"],
        },
    ).json()["agent"]

    task = booted.post(
        f"/chiefs/{cmo_id}/delegate",
        json={
            "request_id": request_id,
            "agent_id": agent["id"],
            "title": "Frente de mercado",
            "task_description": "Mapear personas e concorrentes do segmento juridico",
            "acceptance_criteria": ["Mapa de personas"],
        },
    )
    assert task.status_code == 201, task.text
    task_id = task.json()["id"]

    tasks = booted.get(f"/agents/{agent['id']}/tasks").json()
    assert tasks["total"] == 1

    reported = booted.post(f"/agents/{agent['id']}/tasks/{task_id}/report")
    assert reported.status_code == 200, reported.text
    assert reported.json()["status"] == "AWAITING_REVIEW"

    pending = booted.get(f"/chiefs/{cmo_id}/pending-reviews").json()
    assert pending["total"] == 1

    review = booted.post(f"/chiefs/{cmo_id}/tasks/{task_id}/review-and-decide")
    assert review.status_code == 200, review.text
    body = review.json()
    assert body["decision"] in {"APPROVE", "REJECT", "MODIFY", "CONSULT_PEERS", "ESCALATE"}
    assert body["review_reasoning_session_id"]
    assert "quality" in body["assessment"]


def test_chief_nao_revisa_tarefa_de_outra_diretoria(booted: TestClient) -> None:
    request_id = _submit(booted)["request"]["id"]
    cmo_id = _chief_id(booted, "CMO")
    cto_id = _chief_id(booted, "CTO")

    agent = booted.post(
        "/ra/create-agent",
        json={
            "requesting_chief": "CMO",
            "request_id": request_id,
            "job_title": "Analista de Mercado",
            "objective": "Mapear personas e concorrentes do segmento juridico de medio porte",
            "deliverables": ["Mapa de personas"],
        },
    ).json()["agent"]

    task_id = booted.post(
        f"/chiefs/{cmo_id}/delegate",
        json={
            "request_id": request_id,
            "agent_id": agent["id"],
            "title": "Frente de mercado",
            "task_description": "Mapear personas",
        },
    ).json()["id"]
    booted.post(f"/agents/{agent['id']}/tasks/{task_id}/report")

    response = booted.post(f"/chiefs/{cto_id}/tasks/{task_id}/review-and-decide")
    assert response.status_code == 409


def test_report_de_tarefa_alheia_e_recusado(booted: TestClient) -> None:
    request_id = _submit(booted)["request"]["id"]
    cmo_id = _chief_id(booted, "CMO")
    agent = booted.post(
        "/ra/create-agent",
        json={
            "requesting_chief": "CMO",
            "request_id": request_id,
            "job_title": "Analista de Mercado",
            "objective": "Mapear personas e concorrentes do segmento juridico de medio porte",
            "deliverables": ["Mapa de personas"],
        },
    ).json()["agent"]
    task_id = booted.post(
        f"/chiefs/{cmo_id}/delegate",
        json={
            "request_id": request_id,
            "agent_id": agent["id"],
            "title": "Frente",
            "task_description": "Mapear personas",
        },
    ).json()["id"]

    response = booted.post(f"/agents/{cmo_id}/tasks/{task_id}/report")
    assert response.status_code == 409


def test_ciclo_automatico_percorre_o_grafo_inteiro(booted: TestClient) -> None:
    request_id = _submit(booted)["request"]["id"]

    response = booted.post(f"/council/requests/{request_id}/run-cycle")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["executed_tasks"] == 3
    assert len(body["reviews"]) == 3
    kinds = {edge["communication_type"] for edge in body["graph"]["edges"]}
    assert {"AGENT_REQUEST", "AGENT_CREATED", "DELEGATION", "REPORT", "DECISION"} <= kinds

    for review in body["reviews"]:
        assert review["task"]["review_reasoning_session_id"]
        assert 0 <= review["achievement_ratio"] <= 1


def test_time_supervisionado_por_chief(booted: TestClient) -> None:
    request_id = _submit(booted)["request"]["id"]
    booted.post(f"/council/requests/{request_id}/run-cycle")

    cto_id = _chief_id(booted, "CTO")
    ra_id = _chief_id(booted, "RA")

    cto_team = booted.get(f"/chiefs/{cto_id}/supervised-agents").json()
    ra_team = booted.get(f"/chiefs/{ra_id}/supervised-agents").json()

    assert cto_team["total"] >= 1
    # O RA cria agentes, mas nunca supervisiona ninguém.
    assert ra_team["total"] == 0


def test_desempate_do_ceo_via_api(booted: TestClient) -> None:
    request_id = _submit(booted)["request"]["id"]
    cycle = booted.post(f"/council/requests/{request_id}/run-cycle").json()
    task_id = cycle["reviews"][0]["task"]["id"]

    response = booted.post(f"/ceo/final-decision/{task_id}")
    assert response.status_code == 200, response.text
    assert response.json()["decision"] in {"APPROVE", "REJECT", "MODIFY"}
