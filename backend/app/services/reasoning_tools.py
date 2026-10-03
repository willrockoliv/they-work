"""Ferramentas offline disponíveis aos agentes durante o ciclo ReAct.

Cada ferramenta devolve um texto legível (a "Observação" que volta ao modelo) e um
payload estruturado com a entrada bruta e o resultado — é esse payload que alimenta
o raio-X cognitivo do frontend.
"""

from __future__ import annotations

import ast
import operator
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.memory import CorporateMemory
from app.services import audit_service, talent_bank
from app.services.complexity_classifier import normalize
from app.services.nature_manager import NatureManager

#: Quantidade máxima de registros devolvida por uma consulta de ferramenta.
MAX_RESULTS = 5


@dataclass(frozen=True, slots=True)
class ToolContext:
    """Recursos que o agente pode alcançar sem sair do sandbox."""

    db: Session
    nature: NatureManager | None = None


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
    )
}


def get_tool(name: str) -> ToolSpec | None:
    """Ferramenta pelo nome normalizado, tolerante a acentos e caixa."""
    return TOOLS.get(normalize(name).replace(" ", "_").replace("-", "_"))


def catalog() -> str:
    """Descrição das ferramentas injetada no prompt ReAct."""
    return "\n".join(f"- {spec.name}: {spec.description}" for spec in TOOLS.values())
