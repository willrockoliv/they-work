"""Análise determinística de reports — as 7 ferramentas do Chief supervisor."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from app.models.enums import ChiefDecision, TaskStatus
from app.models.network import AgentTask, InitialRequest
from app.services import reasoning_tools, report_analysis

GOOD_REPORT = (
    "Resultado: entrevistei 12 clientes do segmento juridico e mapeei a persona principal. "
    "Entrega: planilha com as 12 entrevistas, mapa de personas e analise de concorrentes. "
    "Metrica: 9 de 12 entrevistados confirmaram a dor de triagem documental. "
    "Evidencia: transcricoes arquivadas na memoria corporativa com data e identificador. "
    "Conclusao: a demanda esta validada e o posicionamento recomendado e automacao de "
    "triagem documental para escritorios de medio porte, com canais de aquisicao por "
    "indicacao e conteudo tecnico. Proximo passo: desenhar a oferta comercial e precificar "
    "o plano de entrada com base no custo de inferencia local medido nesta sprint."
)

WEAK_REPORT = "Fiz o que deu. Talvez funcione."


def _task(session: Session, *, description: str, report: str, attempt: int = 1) -> AgentTask:
    request = InitialRequest(topic="Validar mercado", description="Pesquisa de mercado.")
    session.add(request)
    session.flush()
    task = AgentTask(
        request_id=request.id,
        title="Frente de mercado",
        task_description=description,
        context={"acceptance_criteria": ["Mapa de personas", "Analise de concorrentes"]},
        status=TaskStatus.AWAITING_REVIEW,
        attempt=attempt,
        report_summary=report,
        assigned_to_agent_id=None,
    )
    session.add(task)
    session.flush()
    return task


def test_report_completo_pontua_alto(db_session: Session) -> None:
    quality = report_analysis.evaluate_quality(GOOD_REPORT)
    assert quality.score >= 80
    assert quality.completeness == 100
    assert quality.structure >= 75


def test_report_vazio_pontua_baixo() -> None:
    quality = report_analysis.evaluate_quality(WEAK_REPORT)
    assert quality.score < 50
    assert quality.notes


def test_criterios_de_aceitacao_sem_evidencia_viram_nota() -> None:
    quality = report_analysis.evaluate_quality(
        WEAK_REPORT, acceptance_criteria=("Mapa de personas",)
    )
    assert any("critério" in note for note in quality.notes)


def test_comparacao_com_objetivo_mede_cobertura() -> None:
    comparison = report_analysis.compare_vs_objective(
        "Mapear personas e concorrentes do segmento juridico", GOOD_REPORT
    )
    assert comparison.achievement_ratio > 0.5
    assert "personas" in comparison.covered

def test_objetivo_vazio_nao_divide_por_zero() -> None:
    comparison = report_analysis.compare_vs_objective("", GOOD_REPORT)
    assert comparison.achievement_ratio == 1.0
    assert comparison.gaps == ()


def test_riscos_sao_classificados_por_severidade() -> None:
    risks = report_analysis.check_risks("Guardei a senha do cliente em texto puro, sem teste.")
    categories = {risk.category for risk in risks}
    assert "SECURITY" in categories
    assert report_analysis.highest_severity(risks) == "HIGH"


def test_sem_risco_a_severidade_e_none() -> None:
    assert report_analysis.highest_severity(()) == "NONE"


def test_custo_beneficio_recomenda_a_opcao_de_maior_roi() -> None:
    quality = report_analysis.evaluate_quality(GOOD_REPORT)
    comparison = report_analysis.compare_vs_objective("Mapear personas", GOOD_REPORT)
    estimate = report_analysis.estimate_cost_benefit(quality, comparison, ())
    assert estimate["recommended"] in {decision.value for decision in ChiefDecision}
    assert estimate["options"]["APPROVE"]["cost"] == 0
    assert estimate["options"]["APPROVE"]["benefit"] == quality.score


def test_capacidade_de_agente_desconhecido(db_session: Session) -> None:
    profile = report_analysis.agent_capability(db_session, None)
    assert profile.total_tasks == 0
    assert "supervisione" in profile.recommendation


def test_veredito_rejeita_entrega_pobre(db_session: Session) -> None:
    task = _task(
        db_session,
        description="Mapear personas, concorrentes e canais do segmento juridico",
        report=WEAK_REPORT,
    )
    assessment = report_analysis.assess(db_session, task, WEAK_REPORT)
    assert assessment.decision is ChiefDecision.REJECT
    assert assessment.next_steps


def test_veredito_escala_quando_ha_risco_alto(db_session: Session) -> None:
    report = GOOD_REPORT + " Observacao: a senha do cliente ficou exposta no log."
    task = _task(db_session, description="Mapear personas", report=report)
    assessment = report_analysis.assess(db_session, task, report)
    assert assessment.decision is ChiefDecision.ESCALATE


def test_veredito_aprova_entrega_completa(db_session: Session) -> None:
    task = _task(db_session, description="Mapear personas e concorrentes", report=GOOD_REPORT)
    assessment = report_analysis.assess(db_session, task, GOOD_REPORT)
    assert assessment.decision is ChiefDecision.APPROVE
    assert assessment.risk_level == "NONE"


def test_lacuna_de_objetivo_pede_subtarefa(db_session: Session) -> None:
    """Termo do objetivo ausente do report vira MODIFY, não aprovação silenciosa."""
    task = _task(
        db_session,
        description="Mapear personas, concorrentes e o plano de internacionalizacao",
        report=GOOD_REPORT,
    )
    assessment = report_analysis.assess(db_session, task, GOOD_REPORT)
    assert assessment.decision is ChiefDecision.MODIFY
    assert "internacionalizacao" in assessment.comparison.gaps


@pytest.mark.parametrize(
    "tool_name",
    [
        "avaliar_qualidade_report",
        "comparar_vs_objetivo",
        "estimar_custo_beneficio",
        "proximos_passos",
        "capacidade_do_agente",
    ],
)
def test_ferramentas_exigem_tarefa_no_contexto(db_session: Session, tool_name: str) -> None:
    spec = reasoning_tools.get_tool(tool_name)
    assert spec is not None
    result = spec.run(reasoning_tools.ToolContext(db=db_session), "qualquer coisa")
    assert result.error == "no_task_in_context"


def test_ferramenta_de_qualidade_usa_a_tarefa_do_contexto(db_session: Session) -> None:
    task = _task(db_session, description="Entrevistar clientes", report=GOOD_REPORT)
    spec = reasoning_tools.get_tool("avaliar_qualidade_report")
    assert spec is not None
    result = spec.run(reasoning_tools.ToolContext(db=db_session, task_id=task.id), "")
    assert result.error is None
    assert result.payload["score"] >= 80


def test_ferramenta_de_precedentes_sem_historico(db_session: Session) -> None:
    spec = reasoning_tools.get_tool("precedentes_corporativos")
    assert spec is not None
    result = spec.run(reasoning_tools.ToolContext(db=db_session), "fundar startup")
    assert result.payload["precedents"] == []


def test_checar_riscos_funciona_sem_tarefa(db_session: Session) -> None:
    spec = reasoning_tools.get_tool("checar_riscos")
    assert spec is not None
    ctx = reasoning_tools.ToolContext(db=db_session, task_id=uuid.uuid4())
    result = spec.run(ctx, "O endpoint ficou lento e sem teste.")
    assert result.payload["risk_level"] in {"HIGH", "MEDIUM", "LOW"}
