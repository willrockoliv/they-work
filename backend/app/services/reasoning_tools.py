"""Ferramentas offline disponíveis aos agentes durante o ciclo ReAct.

Cada ferramenta devolve um texto legível (a "Observação" que volta ao modelo) e um
payload estruturado com a entrada bruta e o resultado — é esse payload que alimenta
o raio-X cognitivo do frontend.
"""

from __future__ import annotations

import ast
import operator
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.memory import CorporateMemory
from app.models.network import AgentTask
from app.services import audit_service, report_analysis, talent_bank
from app.services.complexity_classifier import normalize
from app.services.nature_manager import NatureManager

#: Quantidade máxima de registros devolvida por uma consulta de ferramenta.
MAX_RESULTS = 5


@dataclass(frozen=True, slots=True)
class ToolContext:
    """Recursos que o agente pode alcançar sem sair do sandbox."""

    db: Session
    nature: NatureManager | None = None
    #: Tarefa sob análise, quando o ciclo ReAct é uma revisão de report (Fase 5).
    task_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Observação devolvida ao agente, com o rastro estruturado da consulta."""

    output: str
    payload: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """Ferramenta registrada, exposta ao modelo no prompt ReAct."""

    name: str
    description: str
    run: Callable[[ToolContext, str], ToolResult]


def _memoria_corporativa(ctx: ToolContext, query: str) -> ToolResult:
    """Busca lexical nos relatórios e decisões arquivados."""
    terms = [term for term in normalize(query).split() if len(term) > 2]
    rows = list(
        ctx.db.scalars(
            select(CorporateMemory).order_by(CorporateMemory.created_at.desc()).limit(200)
        )
    )
    hits = [
        row
        for row in rows
        if not terms or any(term in normalize(f"{row.title} {row.content}") for term in terms)
    ][:MAX_RESULTS]

    payload = {
        "search_terms": terms,
        "results": [
            {"id": str(row.id), "title": row.title, "type": row.memory_type.value}
            for row in hits
        ],
        "total_scanned": len(rows),
    }
    if not hits:
        return ToolResult("Nenhum registro na memória corporativa casa com a busca.", payload)
    lines = [f"- [{row.memory_type.value}] {row.title}: {row.content[:200]}" for row in hits]
    return ToolResult("\n".join(lines), payload)


def _banco_de_talentos(ctx: ToolContext, query: str) -> ToolResult:
    """Procura um perfil já redigido pelo RA para um cargo."""
    match = talent_bank.search(ctx.db, role_title=query, specialization="")
    if match is None:
        return ToolResult(
            f"Nenhum perfil no Banco de Talentos corresponde a '{query}'.",
            {"query": query, "matched": False},
        )
    profile = match.profile
    payload = {
        "query": query,
        "matched": True,
        "profile_id": str(profile.id),
        "slug": profile.slug,
        "version": profile.version,
        "score": match.score,
        "matched_on": match.matched_on,
    }
    return ToolResult(
        (
            f"Perfil '{profile.role_title}' (v{profile.version}, aderência {match.score:.0%}), "
            f"modelo recomendado {profile.recommended_model or 'não definido'}."
        ),
        payload,
    )


def _auditoria(ctx: ToolContext, query: str) -> ToolResult:
    """Lê os eventos mais recentes da trilha corporativa."""
    events = audit_service.list_events(ctx.db, limit=MAX_RESULTS)
    payload = {
        "query": query,
        "results": [
            {"event_type": event.event_type.value, "actor": event.actor, "summary": event.summary}
            for event in events
        ],
    }
    if not events:
        return ToolResult("A trilha de auditoria ainda está vazia.", payload)
    lines = [f"- {event.event_type.value} ({event.actor}): {event.summary}" for event in events]
    return ToolResult("\n".join(lines), payload)


def _infraestrutura(ctx: ToolContext, query: str) -> ToolResult:
    """Consulta a Natureza sobre a capacidade atual da infraestrutura."""
    if ctx.nature is None:
        return ToolResult(
            "A Natureza não está disponível nesta execução.",
            {"query": query},
            error="nature_unavailable",
        )
    snapshot = ctx.nature.snapshot()
    return ToolResult(snapshot.narrative, {"query": query, "snapshot": snapshot.to_dict()})


_OPERATORS: dict[type[ast.AST], Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd | ast.USub):
        value = _eval_node(node.operand)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp):
        handler = _OPERATORS.get(type(node.op))
        if handler is not None:
            return float(handler(_eval_node(node.left), _eval_node(node.right)))
    msg = "Expressão aritmética não suportada."
    raise ValueError(msg)


def _calculadora(_: ToolContext, expression: str) -> ToolResult:
    """Avalia aritmética simples por AST — `eval` jamais é usado."""
    try:
        tree = ast.parse(expression, mode="eval")
        result = _eval_node(tree.body)
    except (SyntaxError, ValueError, ZeroDivisionError, OverflowError, TypeError) as exc:
        return ToolResult(
            f"Não foi possível calcular '{expression}': {exc}",
            {"expression": expression},
            error=str(exc),
        )
    return ToolResult(f"{expression} = {result:g}", {"expression": expression, "result": result})


# --- Ferramentas de análise de report (Fase 5) -------------------------------


def _current_task(ctx: ToolContext) -> AgentTask | None:
    return ctx.db.get(AgentTask, ctx.task_id) if ctx.task_id is not None else None


def _sem_tarefa(name: str) -> ToolResult:
    return ToolResult(
        f"A ferramenta '{name}' só funciona durante a revisão de uma tarefa delegada.",
        {"task_id": None},
        error="no_task_in_context",
    )


def _report_text(task: AgentTask, fallback: str) -> str:
    return task.report_summary or fallback


def _avaliar_qualidade_report(ctx: ToolContext, query: str) -> ToolResult:
    task = _current_task(ctx)
    if task is None:
        return _sem_tarefa("avaliar_qualidade_report")
    criteria = tuple(str(item) for item in task.context.get("acceptance_criteria", []))
    quality = report_analysis.evaluate_quality(
        _report_text(task, query), acceptance_criteria=criteria
    )
    notes = " ".join(quality.notes) or "Sem ressalvas estruturais."
    return ToolResult(
        (
            f"Qualidade {quality.score}/100 (completude {quality.completeness}, clareza "
            f"{quality.clarity}, estrutura {quality.structure}). {notes}"
        ),
        {"task_id": str(task.id), **quality.to_dict()},
    )


def _comparar_vs_objetivo(ctx: ToolContext, query: str) -> ToolResult:
    task = _current_task(ctx)
    if task is None:
        return _sem_tarefa("comparar_vs_objetivo")
    comparison = report_analysis.compare_vs_objective(
        task.task_description, _report_text(task, query)
    )
    gaps = ", ".join(comparison.gaps[:5]) or "nenhuma"
    return ToolResult(
        (
            f"Cobertura de {comparison.achievement_ratio:.0%} do objetivo. "
            f"Lacunas: {gaps}."
        ),
        {"task_id": str(task.id), **comparison.to_dict()},
    )


def _checar_riscos(ctx: ToolContext, query: str) -> ToolResult:
    task = _current_task(ctx)
    text = _report_text(task, query) if task is not None else query
    risks = report_analysis.check_risks(text)
    payload = {
        "task_id": str(task.id) if task else None,
        "risks": [risk.to_dict() for risk in risks],
        "risk_level": report_analysis.highest_severity(risks),
    }
    if not risks:
        return ToolResult("Nenhum risco relevante identificado no texto analisado.", payload)
    lines = [f"- [{risk.severity}] {risk.category}: '{risk.evidence}'" for risk in risks]
    return ToolResult("\n".join(lines), payload)


def _estimar_custo_beneficio(ctx: ToolContext, query: str) -> ToolResult:
    task = _current_task(ctx)
    if task is None:
        return _sem_tarefa("estimar_custo_beneficio")
    text = _report_text(task, query)
    criteria = tuple(str(item) for item in task.context.get("acceptance_criteria", []))
    quality = report_analysis.evaluate_quality(text, acceptance_criteria=criteria)
    comparison = report_analysis.compare_vs_objective(task.task_description, text)
    risks = report_analysis.check_risks(text)
    estimate = report_analysis.estimate_cost_benefit(quality, comparison, risks)
    options = "; ".join(
        f"{name} (ROI {data['roi']})" for name, data in estimate["options"].items()
    )
    return ToolResult(
        f"Melhor retorno: {estimate['recommended']}. Comparativo: {options}.",
        {"task_id": str(task.id), **estimate},
    )


def _proximos_passos(ctx: ToolContext, query: str) -> ToolResult:
    task = _current_task(ctx)
    if task is None:
        return _sem_tarefa("proximos_passos")
    text = _report_text(task, query)
    comparison = report_analysis.compare_vs_objective(task.task_description, text)
    risks = report_analysis.check_risks(text)
    steps = report_analysis.identify_next_steps(task, comparison, risks)
    return ToolResult(
        "\n".join(f"- {step}" for step in steps),
        {"task_id": str(task.id), "next_steps": list(steps)},
    )


def _capacidade_do_agente(ctx: ToolContext, query: str) -> ToolResult:
    task = _current_task(ctx)
    if task is None:
        return _sem_tarefa("capacidade_do_agente")
    profile = report_analysis.agent_capability(ctx.db, task.assigned_to_agent_id)
    return ToolResult(
        (
            f"{profile.total_tasks} tarefa(s) no histórico ({profile.completed} aprovadas, "
            f"{profile.rejected} rejeitadas), qualidade média {profile.average_quality}/100. "
            f"{profile.recommendation}"
        ),
        {"query": query, **profile.to_dict()},
    )


def _precedentes_corporativos(ctx: ToolContext, query: str) -> ToolResult:
    """Decisões passadas do conselho que servem de precedente para a atual."""
    task = _current_task(ctx)
    subject = query or (task.title if task else "")
    terms = [term for term in normalize(subject).split() if len(term) > 3]
    events = audit_service.list_events(ctx.db, limit=100)
    hits = [
        event
        for event in events
        if event.decision
        and (
            not terms
            or any(
                term in normalize(f"{event.summary} {event.narrative}") for term in terms
            )
        )
    ][:MAX_RESULTS]
    payload = {
        "query": query,
        "precedents": [
            {
                "event_type": event.event_type.value,
                "actor": event.actor,
                "decision": event.decision,
                "summary": event.summary,
            }
            for event in hits
        ],
    }
    if not hits:
        return ToolResult("Nenhum precedente corporativo encontrado para este assunto.", payload)
    lines = [f"- {event.actor} decidiu {event.decision}: {event.summary}" for event in hits]
    return ToolResult("\n".join(lines), payload)


TOOLS: dict[str, ToolSpec] = {
    spec.name: spec
    for spec in (
        ToolSpec(
            "memoria_corporativa",
            "Busca relatórios, decisões e atas já arquivados. Entrada: termos de pesquisa.",
            _memoria_corporativa,
        ),
        ToolSpec(
            "banco_de_talentos",
            "Consulta perfis de subagentes já redigidos pelo RA. Entrada: cargo procurado.",
            _banco_de_talentos,
        ),
        ToolSpec(
            "auditoria",
            "Lê os eventos corporativos mais recentes. Entrada: assunto de interesse.",
            _auditoria,
        ),
        ToolSpec(
            "infraestrutura",
            "Pergunta à Natureza a capacidade atual de RAM, VRAM e CPU. Entrada: livre.",
            _infraestrutura,
        ),
        ToolSpec(
            "calculadora",
            "Avalia uma expressão aritmética. Entrada: expressão, ex.: (120 * 3) / 4.",
            _calculadora,
        ),
        ToolSpec(
            "avaliar_qualidade_report",
            "Pontua de 0 a 100 o report da tarefa em revisão. Entrada: texto do report.",
            _avaliar_qualidade_report,
        ),
        ToolSpec(
            "comparar_vs_objetivo",
            "Mede a cobertura do objetivo pelo report e lista as lacunas. Entrada: livre.",
            _comparar_vs_objetivo,
        ),
        ToolSpec(
            "checar_riscos",
            "Classifica riscos por categoria e severidade. Entrada: texto a analisar.",
            _checar_riscos,
        ),
        ToolSpec(
            "precedentes_corporativos",
            "Busca decisões passadas que sirvam de precedente. Entrada: assunto.",
            _precedentes_corporativos,
        ),
        ToolSpec(
            "estimar_custo_beneficio",
            "Compara o ROI de aprovar, modificar ou rejeitar o report. Entrada: livre.",
            _estimar_custo_beneficio,
        ),
        ToolSpec(
            "proximos_passos",
            "Sugere as próximas tarefas a partir das lacunas e riscos. Entrada: livre.",
            _proximos_passos,
        ),
        ToolSpec(
            "capacidade_do_agente",
            "Consulta histórico e taxa de rejeição do subordinado. Entrada: livre.",
            _capacidade_do_agente,
        ),
    )
}


def get_tool(name: str) -> ToolSpec | None:
    """Ferramenta pelo nome normalizado, tolerante a acentos e caixa."""
    return TOOLS.get(normalize(name).replace(" ", "_").replace("-", "_"))


def catalog() -> str:
    """Descrição das ferramentas injetada no prompt ReAct."""
    return "\n".join(f"- {spec.name}: {spec.description}" for spec in TOOLS.values())
