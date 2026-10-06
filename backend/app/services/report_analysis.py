"""Análise determinística de reports — o miolo das 7 ferramentas do Chief supervisor.

Tudo aqui é offline e reprodutível: heurísticas léxicas sobre o texto do report,
consultas ao histórico local de tarefas e fórmulas fechadas de custo/benefício.
Nenhuma chamada de rede. O `agent_decision_engine` usa estas funções tanto para
alimentar o ciclo ReAct quanto para decidir quando o modelo não está disponível.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import ChiefDecision, TaskStatus
from app.models.network import AgentTask
from app.services.complexity_classifier import normalize

#: Comprimento a partir do qual o report é considerado completo em extensão.
FULL_LENGTH_CHARS = 600

#: Palavras vazias descartadas na comparação entre objetivo e report.
_STOPWORDS: frozenset[str] = frozenset(
    {
        "para",
        "com",
        "uma",
        "que",
        "dos",
        "das",
        "nos",
        "nas",
        "por",
        "sobre",
        "como",
        "mais",
        "sem",
        "pelo",
        "pela",
        "este",
        "esta",
        "esse",
        "essa",
        "ser",
        "foi",
        "the",
        "and",
        "for",
    }
)

#: Marcadores de estrutura que um report bem redigido costuma trazer.
_STRUCTURE_MARKERS: tuple[str, ...] = (
    "resultado",
    "entrega",
    "conclusao",
    "proximo",
    "risco",
    "evidencia",
    "metrica",
)

_RISK_CATALOG: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("PERFORMANCE", ("lento", "latencia", "gargalo", "timeout", "demora"), "MEDIUM"),
    ("SCALABILITY", ("nao escala", "volume imprevisivel", "concorrencia alta"), "MEDIUM"),
    (
        "SECURITY",
        ("senha", "token", "vazamento", "pii", "dados sensiveis", "injecao", "exposta"),
        "HIGH",
    ),
    ("FINANCE", ("prejuizo", "orcamento estourado", "margem negativa", "caixa negativo"), "HIGH"),
    (
        "QUALITY",
        ("sem teste", "nao testado", "provisorio", "gambiarra", "workaround"),
        "MEDIUM",
    ),
    ("UNCERTAINTY", ("talvez", "possivelmente", "nao sei", "incerto", "suposicao"), "LOW"),
)

_SEVERITY_WEIGHT: dict[str, int] = {"HIGH": 25, "MEDIUM": 12, "LOW": 5}


@dataclass(frozen=True, slots=True)
class QualityScore:
    """Escore de qualidade do report, de 0 a 100."""

    score: int
    completeness: int
    clarity: int
    structure: int
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "completeness": self.completeness,
            "clarity": self.clarity,
            "structure": self.structure,
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class ObjectiveComparison:
    """Delta entre o que foi pedido e o que o report efetivamente entrega."""

    achievement_ratio: float
    covered: tuple[str, ...]
    gaps: tuple[str, ...]
    bonus: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "achievement_ratio": round(self.achievement_ratio, 3),
            "covered": list(self.covered),
            "gaps": list(self.gaps),
            "bonus": list(self.bonus),
        }


@dataclass(frozen=True, slots=True)
class Risk:
    """Risco identificado no texto do report."""

    category: str
    severity: str
    evidence: str

    def to_dict(self) -> dict[str, Any]:
        return {"category": self.category, "severity": self.severity, "evidence": self.evidence}


@dataclass(frozen=True, slots=True)
class CapabilityProfile:
    """Histórico do agente, consultado antes de reconvocá-lo."""

    agent_id: uuid.UUID | None
    total_tasks: int
    completed: int
    rejected: int
    average_quality: int
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": str(self.agent_id) if self.agent_id else None,
            "total_tasks": self.total_tasks,
            "completed": self.completed,
            "rejected": self.rejected,
            "average_quality": self.average_quality,
            "recommendation": self.recommendation,
        }


@dataclass(frozen=True, slots=True)
class Assessment:
    """Avaliação consolidada que sustenta o veredito do Chief."""

    quality: QualityScore
    comparison: ObjectiveComparison
    risks: tuple[Risk, ...]
    decision: ChiefDecision
    rationale: str
    next_steps: tuple[str, ...]

    @property
    def risk_level(self) -> str:
        return highest_severity(self.risks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "quality": self.quality.to_dict(),
            "comparison": self.comparison.to_dict(),
            "risks": [risk.to_dict() for risk in self.risks],
            "risk_level": self.risk_level,
            "decision": self.decision.value,
            "rationale": self.rationale,
            "next_steps": list(self.next_steps),
        }


def _terms(text: str) -> list[str]:
    """Termos significativos de um texto, normalizados e sem palavras vazias."""
    return [
        token
        for token in normalize(text).split()
        if len(token) > 3 and token not in _STOPWORDS and not token.isdigit()
    ]


def evaluate_quality(
    report_text: str, *, acceptance_criteria: tuple[str, ...] = ()
) -> QualityScore:
    """Escore de qualidade do report a partir de extensão, estrutura e clareza."""
    text = report_text.strip()
    folded = normalize(text)
    notes: list[str] = []

    completeness = min(100, round(len(text) / FULL_LENGTH_CHARS * 100))
    if completeness < 50:
        notes.append("Report curto demais para sustentar a conclusão.")

    markers = [marker for marker in _STRUCTURE_MARKERS if marker in folded]
    structure = min(100, len(markers) * 25)
    if structure < 50:
        notes.append("Faltam seções de resultado, evidência ou próximos passos.")

    sentences = [part for part in text.replace("\n", ".").split(".") if part.strip()]
    has_numbers = any(char.isdigit() for char in text)
    clarity = min(100, len(sentences) * 12 + (25 if has_numbers else 0))
    if not has_numbers:
        notes.append("Nenhum dado quantitativo foi apresentado.")

    met = [item for item in acceptance_criteria if any(t in folded for t in _terms(item))]
    criteria_ratio = len(met) / len(acceptance_criteria) if acceptance_criteria else 1.0
    if acceptance_criteria and criteria_ratio < 1.0:
        notes.append(
            f"{len(acceptance_criteria) - len(met)} critério(s) de aceitação sem evidência."
        )

    score = round(
        completeness * 0.3 + structure * 0.25 + clarity * 0.2 + criteria_ratio * 100 * 0.25
    )
    return QualityScore(
        score=max(0, min(100, score)),
        completeness=completeness,
        clarity=clarity,
        structure=structure,
        notes=tuple(notes),
    )


#: Radical usado para casar flexões do português ('mapear' vs. 'mapeei', 'mapeamento').
STEM_CHARS = 4


def _stem(term: str) -> str:
    return term[:STEM_CHARS]


def compare_vs_objective(objective: str, report_text: str) -> ObjectiveComparison:
    """Mede a cobertura dos termos do objetivo no texto do report."""
    expected = list(dict.fromkeys(_terms(objective)))
    delivered = set(_terms(report_text))
    if not expected:
        return ObjectiveComparison(1.0, (), (), tuple(sorted(delivered)[:5]))

    delivered_stems = {_stem(token) for token in delivered}
    covered = tuple(term for term in expected if _stem(term) in delivered_stems)
    gaps = tuple(term for term in expected if _stem(term) not in delivered_stems)
    expected_stems = {_stem(term) for term in expected}
    bonus = tuple(sorted(token for token in delivered if _stem(token) not in expected_stems)[:5])
    return ObjectiveComparison(
        achievement_ratio=len(covered) / len(expected),
        covered=covered,
        gaps=gaps,
        bonus=bonus,
    )


def check_risks(report_text: str) -> tuple[Risk, ...]:
    """Classifica riscos por categoria e severidade a partir de marcadores léxicos."""
    folded = normalize(report_text)
    risks: list[Risk] = []
    for category, markers, severity in _RISK_CATALOG:
        hit = next((marker for marker in markers if _mentions(folded, marker)), None)
        if hit is not None:
            risks.append(Risk(category=category, severity=severity, evidence=hit))
    return tuple(risks)


def _mentions(folded_text: str, marker: str) -> bool:
    """Casa o marcador por palavra inteira: 'senha' não pode casar com 'desenhar'."""
    return re.search(rf"\b{re.escape(marker)}\b", folded_text) is not None


def highest_severity(risks: tuple[Risk, ...]) -> str:
    """Pior severidade presente no conjunto de riscos."""
    for level in ("HIGH", "MEDIUM", "LOW"):
        if any(risk.severity == level for risk in risks):
            return level
    return "NONE"


def estimate_cost_benefit(
    quality: QualityScore, comparison: ObjectiveComparison, risks: tuple[Risk, ...]
) -> dict[str, Any]:
    """Custo, benefício e ROI de cada veredito possível, em unidades relativas."""
    risk_cost = sum(_SEVERITY_WEIGHT[risk.severity] for risk in risks)
    gap_cost = round(len(comparison.gaps) * 8)
    options = {
        ChiefDecision.APPROVE.value: {
            "cost": 0,
            "benefit": quality.score,
            "residual_risk": risk_cost + gap_cost,
        },
        ChiefDecision.MODIFY.value: {
            "cost": gap_cost or 8,
            "benefit": min(100, quality.score + len(comparison.gaps) * 6),
            "residual_risk": round(risk_cost * 0.4),
        },
        ChiefDecision.REJECT.value: {
            "cost": 40,
            "benefit": min(100, quality.score + 30),
            "residual_risk": round(risk_cost * 0.2),
        },
    }
    for option in options.values():
        net = option["benefit"] - option["cost"] - option["residual_risk"]
        option["roi"] = net
    best = max(options.items(), key=lambda item: item[1]["roi"])
    return {"options": options, "recommended": best[0]}


def identify_next_steps(
    task: AgentTask, comparison: ObjectiveComparison, risks: tuple[Risk, ...]
) -> tuple[str, ...]:
    """Próximos passos derivados dos gaps e dos riscos encontrados."""
    steps: list[str] = []
    if comparison.gaps:
        steps.append(
            "Cobrir os pontos do objetivo ainda sem evidência: "
            + ", ".join(comparison.gaps[:5])
        )
    for risk in risks:
        if risk.severity == "HIGH":
            steps.append(f"Mitigar risco {risk.category} antes de prosseguir ({risk.evidence}).")
    if not steps:
        steps.append(f"Consolidar '{task.title}' na memória corporativa e seguir o roadmap.")
    return tuple(steps)


def agent_capability(db: Session, agent_id: uuid.UUID | None) -> CapabilityProfile:
    """Histórico de entregas do agente, usado antes de reconvocá-lo."""
    if agent_id is None:
        return CapabilityProfile(None, 0, 0, 0, 0, "Agente desconhecido: supervisione de perto.")

    rows = list(
        db.scalars(
            select(AgentTask)
            .where(AgentTask.assigned_to_agent_id == agent_id)
            .order_by(AgentTask.created_at.desc())
            .limit(25)
        )
    )
    reviewed = [row for row in rows if row.reviewed_at is not None]
    completed = sum(1 for row in rows if row.status is TaskStatus.COMPLETED)
    rejected = sum(1 for row in rows if row.status is TaskStatus.REJECTED)
    average = round(sum(row.quality_score for row in reviewed) / len(reviewed)) if reviewed else 0

    if not reviewed:
        recommendation = "Sem histórico avaliado: acompanhe a primeira entrega de perto."
    elif average >= 80 and rejected == 0:
        recommendation = "Histórico sólido: viável reconvocar sem supervisão extra."
    elif rejected > completed:
        recommendation = "Taxa de rejeição alta: considere redelegar a outro agente."
    else:
        recommendation = "Desempenho irregular: reconvoque com critérios de aceitação explícitos."

    return CapabilityProfile(
        agent_id=agent_id,
        total_tasks=len(rows),
        completed=completed,
        rejected=rejected,
        average_quality=average,
        recommendation=recommendation,
    )


def assess(db: Session, task: AgentTask, report_text: str) -> Assessment:
    """Avaliação completa do report, com o veredito determinístico do Chief."""
    criteria = tuple(str(item) for item in task.context.get("acceptance_criteria", []))
    quality = evaluate_quality(report_text, acceptance_criteria=criteria)
    comparison = compare_vs_objective(task.task_description, report_text)
    risks = check_risks(report_text)
    decision, rationale = recommend(db, task, quality, comparison, risks)
    return Assessment(
        quality=quality,
        comparison=comparison,
        risks=risks,
        decision=decision,
        rationale=rationale,
        next_steps=identify_next_steps(task, comparison, risks),
    )


def recommend(
    db: Session,
    task: AgentTask,
    quality: QualityScore,
    comparison: ObjectiveComparison,
    risks: tuple[Risk, ...],
) -> tuple[ChiefDecision, str]:
    """Aplica a tabela de parametrização do Chief sobre qualidade, gaps e riscos."""
    severity = highest_severity(risks)
    ratio = comparison.achievement_ratio
    capability = agent_capability(db, task.assigned_to_agent_id)

    if severity == "HIGH":
        return (
            ChiefDecision.ESCALATE,
            (
                f"Risco {risks[0].category} de severidade alta detectado no report "
                f"('{risks[0].evidence}'): a decisão extrapola a minha diretoria."
            ),
        )

    if quality.score < 70 or ratio < 0.5:
        if capability.rejected > capability.completed and task.attempt > 1:
            return (
                ChiefDecision.ESCALATE,
                (
                    f"Segunda entrega insuficiente (qualidade {quality.score}, cobertura "
                    f"{ratio:.0%}) e o histórico do agente é ruim: levo ao CEO."
                ),
            )
        return (
            ChiefDecision.REJECT,
            (
                f"Qualidade {quality.score}/100 e apenas {ratio:.0%} do objetivo coberto. "
                f"Reconvoco o agente: {capability.recommendation}"
            ),
        )

    if quality.score < 90 or comparison.gaps:
        if severity == "MEDIUM" and len(comparison.gaps) > 4:
            return (
                ChiefDecision.CONSULT_PEERS,
                (
                    f"Entrega razoável (qualidade {quality.score}), mas {len(comparison.gaps)} "
                    "lacunas com risco médio afetam outras diretorias: consulto meus pares."
                ),
            )
        return (
            ChiefDecision.MODIFY,
            (
                f"Entrega aproveitável (qualidade {quality.score}, cobertura {ratio:.0%}). "
                f"Abro subtarefa para fechar {len(comparison.gaps)} lacuna(s)."
            ),
        )

    return (
        ChiefDecision.APPROVE,
        (
            f"Entrega completa: qualidade {quality.score}/100, {ratio:.0%} do objetivo "
            "coberto e nenhum risco relevante. Aprovado."
        ),
    )
