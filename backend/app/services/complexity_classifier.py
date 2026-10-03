"""Classificador heurístico de complexidade de tarefas.

Traduz a descrição textual de uma vaga em um `TaskComplexity`, que por sua vez
define o modelo Ollama preferencial. É determinístico e offline de propósito: a
decisão precisa ser auditável e não pode custar uma inferência só para decidir
qual modelo usar.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from app.models.enums import AgentRole, TaskComplexity

#: Sinais textuais e o peso que cada um adiciona ao score de complexidade.
_KEYWORD_WEIGHTS: dict[str, int] = {
    # Trivial / simples
    "resumir": -2,
    "resumo": -2,
    "sumarizar": -2,
    "transcrever": -2,
    "ata": -2,
    "email": -2,
    "e-mail": -2,
    "listar": -2,
    "formatar": -2,
    "revisar texto": -1,
    "traduzir": -1,
    # Moderado
    "analisar": 1,
    "analise": 1,
    "relatorio": 1,
    "pesquisa": 1,
    "comparar": 1,
    "planilha": 1,
    "estruturar": 1,
    "documentar": 1,
    "roteiro": 1,
    "persona": 1,
    "precificacao": 1,
    # Complexo
    "arquitetura": 3,
    "implementar": 3,
    "codigo": 3,
    "codificar": 3,
    "refatorar": 3,
    "algoritmo": 3,
    "integracao": 2,
    "pipeline": 2,
    "modelagem": 2,
    "performance": 2,
    "seguranca": 3,
    "debug": 2,
    "otimizar": 2,
    # Crítico
    "estrategia": 4,
    "impasse": 5,
    "decisao vital": 5,
    "fusao": 4,
    "crise": 4,
    "juridico": 4,
    "compliance": 4,
    "sobrevivencia": 5,
    "pivotar": 4,
}

#: Piso de complexidade por Chief solicitante — reflete o peso do cargo.
_ROLE_FLOOR: dict[AgentRole, TaskComplexity] = {
    AgentRole.CEO: TaskComplexity.MODERATE,
    AgentRole.CTO: TaskComplexity.MODERATE,
    AgentRole.CMO: TaskComplexity.SIMPLE,
    AgentRole.CFO: TaskComplexity.SIMPLE,
    AgentRole.RA: TaskComplexity.TRIVIAL,
}

_ORDER: tuple[TaskComplexity, ...] = (
    TaskComplexity.TRIVIAL,
    TaskComplexity.SIMPLE,
    TaskComplexity.MODERATE,
    TaskComplexity.COMPLEX,
    TaskComplexity.CRITICAL,
)

#: Score acumulado → nível. Limites inclusivos no limite superior.
_SCORE_BANDS: tuple[tuple[int, TaskComplexity], ...] = (
    (-1, TaskComplexity.TRIVIAL),
    (1, TaskComplexity.SIMPLE),
    (4, TaskComplexity.MODERATE),
    (8, TaskComplexity.COMPLEX),
)


@dataclass(frozen=True, slots=True)
class ComplexityAssessment:
    """Resultado da classificação, com os sinais que justificam o nível."""

    complexity: TaskComplexity
    score: int
    signals: tuple[str, ...] = field(default_factory=tuple)
    rationale: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "complexity": self.complexity.value,
            "score": self.score,
            "signals": list(self.signals),
            "rationale": self.rationale,
        }


def normalize(text: str) -> str:
    """Minúsculas sem acentuação, para casar palavras-chave de forma estável."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", stripped).strip()


def classify(
    description: str,
    *,
    requested_by: AgentRole | None = None,
    deliverables: int = 0,
    tools: int = 0,
) -> ComplexityAssessment:
    """Estima o peso cognitivo de uma tarefa a partir do texto e do contexto da vaga."""
    haystack = normalize(description)
    score = 0
    signals: list[str] = []

    for keyword, weight in _KEYWORD_WEIGHTS.items():
        if keyword in haystack:
            score += weight
            signals.append(f"{keyword}({weight:+d})")

    # Escopo largo (muitos entregáveis ou ferramentas) empurra para cima.
    if deliverables >= 3:
        score += 1
        signals.append("multiplos_entregaveis(+1)")
    if tools >= 3:
        score += 1
        signals.append("muitas_ferramentas(+1)")

    word_count = len(haystack.split())
    if word_count >= 60:
        score += 1
        signals.append("briefing_extenso(+1)")
    elif word_count <= 5:
        score -= 1
        signals.append("briefing_curto(-1)")

    complexity = _band_for(score)
    if requested_by is not None:
        floor = _ROLE_FLOOR.get(requested_by, TaskComplexity.TRIVIAL)
        if _ORDER.index(complexity) < _ORDER.index(floor):
            complexity = floor
            signals.append(f"piso_{requested_by.value}({floor.value})")

    return ComplexityAssessment(
        complexity=complexity,
        score=score,
        signals=tuple(signals),
        rationale=(
            f"Score {score} a partir de {len(signals)} sinal(is) textual(is) → {complexity.value}."
        ),
    )


def _band_for(score: int) -> TaskComplexity:
    for threshold, complexity in _SCORE_BANDS:
        if score <= threshold:
            return complexity
    return TaskComplexity.CRITICAL
