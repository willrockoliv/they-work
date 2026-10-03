"""Serialização do raciocínio em fluxograma consumível pelo frontend.

Converte a sequência linear de `reasoning_steps` no grafo
`[Pensamento] → [Uso de Ferramenta] → [Observação] → [Conclusão]`, com dicas de
layout (coluna/linha) para que o cliente D3.js / React Flow não precise recalcular
a topologia do ciclo ReAct.
"""

from __future__ import annotations

from typing import Any

from app.models.agent import Agent
from app.models.base import utcnow
from app.models.enums import ReasoningStatus, ReasoningStepType
from app.models.reasoning import ReasoningSession, ReasoningStep

#: Coluna fixa por tipo de nó — o ciclo ReAct avança da esquerda para a direita.
_COLUMN: dict[ReasoningStepType, int] = {
    ReasoningStepType.THOUGHT: 1,
    ReasoningStepType.ACTION: 2,
    ReasoningStepType.OBSERVATION: 3,
    ReasoningStepType.CONCLUSION: 4,
}

_STYLE: dict[ReasoningStepType, tuple[str, str, str]] = {
    ReasoningStepType.THOUGHT: ("Pensamento", "brain", "#6366f1"),
    ReasoningStepType.ACTION: ("Ferramenta", "wrench", "#f59e0b"),
    ReasoningStepType.OBSERVATION: ("Observação", "eye", "#0ea5e9"),
    ReasoningStepType.CONCLUSION: ("Conclusão", "flag", "#22c55e"),
}

TASK_NODE_ID = "task"


def build_flow(
    session: ReasoningSession, steps: list[ReasoningStep] | None = None
) -> dict[str, Any]:
    """Grafo completo da sessão: `{nodes, edges, meta}`."""
    ordered = sorted(steps if steps is not None else list(session.steps), key=lambda s: s.sequence)

    nodes: list[dict[str, Any]] = [
        {
            "id": TASK_NODE_ID,
            "type": "TASK",
            "label": "Tarefa",
            "content": session.task,
            "icon": "clipboard",
            "color": "#64748b",
            "column": 0,
            "row": 0,
            "meta": {
                "model": session.model_name,
                "complexity": session.complexity.value,
                "started_at": session.started_at.isoformat() if session.started_at else None,
            },
        }
    ]
    edges: list[dict[str, Any]] = []

    row = 0
    previous_id = TASK_NODE_ID
    previous_type: ReasoningStepType | None = None

    for step in ordered:
        if step.step_type is ReasoningStepType.THOUGHT and previous_type is not None:
            row += 1
        label, icon, color = _STYLE[step.step_type]
        node_id = f"step-{step.sequence}"
        nodes.append(
            {
                "id": node_id,
                "type": step.step_type.value,
                "label": f"{label} {step.sequence}",
                "content": step.content,
                "icon": icon,
                "color": color,
                "column": _COLUMN[step.step_type],
                "row": row,
                "payload": step.payload,
                "meta": {
                    "sequence": step.sequence,
                    "timestamp": step.created_at.isoformat() if step.created_at else None,
                    "duration_ms": step.duration_ms,
                    "tokens": step.tokens,
                    "model": step.model_name,
                },
            }
        )
        edges.append(
            {
                "id": f"edge-{previous_id}-{node_id}",
                "source": previous_id,
                "target": node_id,
                # A volta observação → pensamento é o que fecha o ciclo ReAct.
                "kind": (
                    "LOOP"
                    if previous_type is ReasoningStepType.OBSERVATION
                    and step.step_type is ReasoningStepType.THOUGHT
                    else "SEQUENCE"
                ),
                "label": _STYLE[step.step_type][0],
            }
        )
        previous_id = node_id
        previous_type = step.step_type

    return {
        "nodes": nodes,
        "edges": edges,
        "meta": {
            "session_id": str(session.id),
            "agent_id": str(session.agent_id) if session.agent_id else None,
            "status": session.status.value,
            "step_count": len(ordered),
            "total_tokens": session.total_tokens,
            "duration_ms": session.duration_ms,
            "conclusion": session.conclusion,
            "error": session.error,
            "columns": ["Tarefa", "Pensamento", "Ferramenta", "Observação", "Conclusão"],
            "rows": row + 1,
        },
    }


def build_live_status(
    agent: Agent,
    session: ReasoningSession | None,
    steps: list[ReasoningStep] | None = None,
    *,
    max_steps: int,
) -> dict[str, Any]:
    """Estado corrente do agente para a barra de progresso do painel onisciente."""
    base: dict[str, Any] = {
        "agent_id": str(agent.id),
        "agent_name": agent.name,
        "agent_status": agent.status.value,
        "model_name": agent.model_name,
        "session_id": None,
        "reasoning_status": None,
        "task": None,
        "step_count": 0,
        "progress": 0.0,
        "last_step_type": None,
        "last_action": None,
        "elapsed_ms": 0,
        "started_at": None,
    }
    if session is None:
        return base

    ordered = sorted(steps if steps is not None else list(session.steps), key=lambda s: s.sequence)
    last = ordered[-1] if ordered else None
    actions = [step for step in ordered if step.step_type is ReasoningStepType.ACTION]
    elapsed = (
        session.duration_ms
        if session.status is not ReasoningStatus.RUNNING and session.duration_ms
        else int((utcnow() - session.started_at).total_seconds() * 1000)
    )

    base.update(
        {
            "session_id": str(session.id),
            "reasoning_status": session.status.value,
            "task": session.task,
            "step_count": session.step_count,
            "progress": (
                1.0
                if session.status is not ReasoningStatus.RUNNING
                else min(session.step_count / max(max_steps, 1), 0.99)
            ),
            "last_step_type": last.step_type.value if last else None,
            "last_action": actions[-1].content if actions else None,
            "elapsed_ms": max(elapsed, 0),
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "conclusion": session.conclusion,
            "error": session.error,
        }
    )
    return base
