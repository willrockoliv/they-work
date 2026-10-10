"""Análise determinística de reports — sinais que alimentam a revisão do Chief.

Tudo aqui é offline e reprodutível: heurísticas léxicas sobre o texto do report,
consultas ao histórico local de tarefas e fórmulas fechadas. Nenhuma chamada de
rede. Estes resultados são **sinais e fatos** para o modelo do Chief; o veredito
heurístico (`recommend`) só vale no modo shadow (ADR-026).
"""

from __future__ import annotations

import os
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

#: Teto de qualidade para report com placeholder ou metatexto.
ARTIFACT_QUALITY_CAP = 50

#: Fração mínima dos termos de um critério/entregável presentes no report.
MATCH_RATIO = 0.6

#: Palavras que, nas posições anteriores ao termo, negam a entrega.
_NEGATIONS: frozenset[str] = frozenset(
    {"nao", "sem", "falta", "faltou", "faltam", "nenhum", "nenhuma", "pendente", "ausente"}
)
NEGATION_WINDOW = 3

_PLACEHOLDER_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?<![A-Za-zÀ-ÿ0-9])[XYZW](?![A-Za-zÀ-ÿ0-9])"),
    re.compile(r"\b(?:TODO|TBD|XXX+|lorem ipsum)\b", re.I),
    re.compile(r"\[(?:inserir|preencher|nome|valor|data|número|numero)[^\]]*\]", re.I),
    re.compile(r"<[a-zà-ÿ _]{2,30}>", re.I),
)

#: Metatexto de execução: o report descreve o processo do agente em vez da entrega.
_METATEXT_MARKERS: tuple[str, ...] = (
    "preciso de contexto",
    "vou consultar",
    "reuni o contexto",
    "com base no contexto interno consultado",
    "registrando a decisao na memoria corporativa",
    "como modelo de linguagem",
    "como uma ia",
    "nao tenho acesso",
    "sem modelo disponivel",
    "passos atingido sem conclusao",
    "pensamento:",
    "entrada da acao:",
    "observacao:",
)

_UNITS_RE = re.compile(
    r"^\s*(%|r\$|reais|mil|mi|milhoes|bi|usd|us\$|horas?|h|dias?|meses|mes|anos?|"
    r"clientes?|usuarios?|unidades?|pessoas|entrevistad\w*|escritorios?|ms|s|gb|mb)\b",
)
_NUMBER_RE = re.compile(r"(?<![\w.,])(r\$\s*)?(\d+(?:[.,]\d+)*)")
_CALC_RE = re.compile(r"\d\s*[-+*/=\u00d7\u00f7]\s*\d")

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
class Artifacts:
    """Sinais objetivos de report incompleto: placeholder, metatexto, número sem unidade."""

    placeholders: tuple[str, ...] = ()
    metatext: tuple[str, ...] = ()
    unitless_numbers: tuple[str, ...] = ()

    @property
    def blocking(self) -> bool:
        return bool(self.placeholders or self.metatext)

    def to_dict(self) -> dict[str, Any]:
        return {
            "placeholders": list(self.placeholders),
            "metatext": list(self.metatext),
            "unitless_numbers": list(self.unitless_numbers),
        }


@dataclass(frozen=True, slots=True)
class Premise:
    """Número citado no report, com a frase de origem."""

    value: str
    sentence: str
    calculated: bool

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value, "sentence": self.sentence, "calculated": self.calculated}


@dataclass(frozen=True, slots=True)
class DeliverableCheck:
    """Entregável esperado e o trecho do report que o comprova (se houver)."""

    deliverable: str
    found: bool
    excerpt: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "deliverable": self.deliverable,
            "status": "encontrado" if self.found else "faltando",
            "excerpt": self.excerpt,
        }


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
    artifacts: Artifacts = field(default_factory=Artifacts)
    deliverables: tuple[DeliverableCheck, ...] = ()

    @property
    def risk_level(self) -> str:
        return highest_severity(self.risks)

    @property
    def vetoes(self) -> tuple[str, ...]:
        """Fatos objetivos que impedem APPROVE, independentemente do modelo (ADR-024)."""
        reasons: list[str] = []
        if self.artifacts.placeholders:
            reasons.append("placeholder: " + ", ".join(self.artifacts.placeholders[:5]))
        if self.artifacts.metatext:
            reasons.append("metatexto: " + ", ".join(self.artifacts.metatext[:3]))
        missing = [check.deliverable for check in self.deliverables if not check.found]
        if missing:
            reasons.append("entregável ausente: " + ", ".join(missing[:5]))
        return tuple(reasons)

    def to_dict(self) -> dict[str, Any]:
        return {
            "quality": self.quality.to_dict(),
            "comparison": self.comparison.to_dict(),
            "risks": [risk.to_dict() for risk in self.risks],
            "risk_level": self.risk_level,
            "decision": self.decision.value,
            "rationale": self.rationale,
            "next_steps": list(self.next_steps),
            "artifacts": self.artifacts.to_dict(),
            "deliverables": [check.to_dict() for check in self.deliverables],
            "vetoes": list(self.vetoes),
        }


def _terms(text: str) -> list[str]:
    """Termos significativos de um texto, normalizados e sem palavras vazias."""
    return [token for token in _tokens(text) if _significant(token)]


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", normalize(text))


def _significant(token: str) -> bool:
    return len(token) > 3 and token not in _STOPWORDS and not token.isdigit()


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.;!?])\s+|\n+", text) if part.strip()]


def _affirmed_terms(text: str) -> list[str]:
    """Termos do report que não aparecem negados ('não mapeei', 'sem testes')."""
    affirmed: list[str] = []
    for sentence in _sentences(text):
        tokens = _tokens(sentence)
        for index, token in enumerate(tokens):
            if not _significant(token):
                continue
            window = tokens[max(0, index - NEGATION_WINDOW) : index]
            if any(word in _NEGATIONS for word in window):
                continue
            affirmed.append(token)
    return affirmed


def objective_of(task: AgentTask) -> str:
    """Objetivo original da frente, sem a instrução de ajuste de uma reconvocação."""
    return str(task.context.get("objetivo_original") or task.task_description)


def criteria_of(task: AgentTask) -> tuple[str, ...]:
    return tuple(str(item) for item in task.context.get("acceptance_criteria", []))


def deliverables_of(task: AgentTask) -> tuple[str, ...]:
    """Entregáveis definidos pelo Chief na delegação (critérios como fallback legado)."""
    items = task.context.get("deliverables") or task.context.get("acceptance_criteria", [])
    return tuple(str(item) for item in items)


def _matches(item: str, affirmed: list[str]) -> bool:
    terms = list(dict.fromkeys(_terms(item)))
    if not terms:
        return False
    hits = sum(1 for term in terms if any(same_root(term, token) for token in affirmed))
    return hits / len(terms) >= MATCH_RATIO


def detect_artifacts(report_text: str) -> Artifacts:
    """Placeholders (X/Y/Z/W, TODO, [inserir]), metatexto de execução e números sem unidade."""
    placeholders: list[str] = []
    for pattern in _PLACEHOLDER_RES:
        placeholders.extend(match.group(0) for match in pattern.finditer(report_text))

    folded = normalize(report_text)
    metatext = [marker for marker in _METATEXT_MARKERS if marker in folded]

    unitless: list[str] = []
    for match in _NUMBER_RE.finditer(folded):
        if match.group(1):
            continue
        tail = folded[match.end() :]
        if not _UNITS_RE.match(tail):
            unitless.append(match.group(2))

    return Artifacts(
        placeholders=tuple(dict.fromkeys(placeholders)),
        metatext=tuple(metatext),
        unitless_numbers=tuple(dict.fromkeys(unitless))[:10],
    )


def extract_premises(report_text: str) -> tuple[Premise, ...]:
    """Números do report com a frase em que aparecem e se há cálculo explícito."""
    premises: list[Premise] = []
    for sentence in _sentences(report_text):
        calculated = _CALC_RE.search(sentence) is not None
        for match in _NUMBER_RE.finditer(sentence):
            premises.append(Premise(match.group(0).strip(), sentence[:240], calculated))
    return tuple(premises[:20])


#: Citação mais curta que isso não prova nada (ex.: "sim", "ok").
MIN_QUOTE_CHARS = 8


def _flat(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9$%]+", normalize(text)))


def verify_quote(quote: str, text: str) -> bool:
    """A citação existe literalmente no texto (ignorando caixa, acento e pontuação)?"""
    needle = _flat(quote.strip().strip("\"'“”…").removesuffix("..."))
    return len(needle) >= MIN_QUOTE_CHARS and needle in _flat(text)


def lexical_criterion(criterion: str, report_text: str) -> tuple[bool, str]:
    """Juiz léxico de reserva: a primeira frase que cobre o critério, sem negação."""
    for sentence in _sentences(report_text):
        if _matches(criterion, _affirmed_terms(sentence)):
            return True, sentence[:240]
    return False, ""


def check_deliverables(
    report_text: str, deliverables: tuple[str, ...]
) -> tuple[DeliverableCheck, ...]:
    """Cada entregável com o trecho do report que o cobre, ou `faltando`."""
    sentences = _sentences(report_text)
    checks: list[DeliverableCheck] = []
    for deliverable in deliverables:
        excerpt = next(
            (s for s in sentences if _matches(deliverable, _affirmed_terms(s))),
            "",
        )
        checks.append(DeliverableCheck(deliverable, bool(excerpt), excerpt[:240]))
    return tuple(checks)


def evaluate_quality(
    report_text: str, *, acceptance_criteria: tuple[str, ...] = ()
) -> QualityScore:
    """Escore de qualidade do report a partir de extensão, estrutura e clareza.

    Sem critérios de aceitação o peso deles é redistribuído: ausência de critério
    não vale pontos. Placeholder ou metatexto limitam o escore a `ARTIFACT_QUALITY_CAP`.
    """
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

    if acceptance_criteria:
        affirmed = _affirmed_terms(text)
        met = [item for item in acceptance_criteria if _matches(item, affirmed)]
        criteria_ratio = len(met) / len(acceptance_criteria)
        if criteria_ratio < 1.0:
            notes.append(
                f"{len(acceptance_criteria) - len(met)} critério(s) de aceitação sem evidência."
            )
        score = round(
            completeness * 0.3 + structure * 0.25 + clarity * 0.2 + criteria_ratio * 100 * 0.25
        )
    else:
        score = round((completeness * 0.3 + structure * 0.25 + clarity * 0.2) / 0.75)

    artifacts = detect_artifacts(text)
    if artifacts.blocking:
        score = min(score, ARTIFACT_QUALITY_CAP)
        notes.append("Report com placeholder ou metatexto de execução.")

    return QualityScore(
        score=max(0, min(100, score)),
        completeness=completeness,
        clarity=clarity,
        structure=structure,
        notes=tuple(notes),
    )


#: Prefixo mínimo comum para casar flexões do português ('mapear' vs. 'mapeei').
STEM_CHARS = 4


def same_root(a: str, b: str) -> bool:
    """Mesmo radical: prefixo comum de pelo menos `max(4, menor - 3)` letras.

    'mapear'/'mapeei' casam (prefixo 4), mas 'contrato'/'conteudo' não (exige 5).
    """
    if a == b:
        return True
    need = max(STEM_CHARS, min(len(a), len(b)) - 3)
    return len(os.path.commonprefix([a, b])) >= need


def compare_vs_objective(objective: str, report_text: str) -> ObjectiveComparison:
    """Mede a cobertura dos termos do objetivo no texto do report (ignorando negados)."""
    expected = list(dict.fromkeys(_terms(objective)))
    delivered = sorted(set(_affirmed_terms(report_text)))
    if not expected:
        return ObjectiveComparison(1.0, (), (), tuple(delivered[:5]))

    covered = tuple(term for term in expected if any(same_root(term, t) for t in delivered))
    gaps = tuple(term for term in expected if term not in covered)
    bonus = tuple(
        token for token in delivered if not any(same_root(token, t) for t in expected)
    )[:5]
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
    """Avaliação completa do report, com o veredito heurístico (usado só em shadow)."""
    quality = evaluate_quality(report_text, acceptance_criteria=criteria_of(task))
    comparison = compare_vs_objective(objective_of(task), report_text)
    risks = check_risks(report_text)
    decision, rationale = recommend(db, task, quality, comparison, risks)
    return Assessment(
        quality=quality,
        comparison=comparison,
        risks=risks,
        decision=decision,
        rationale=rationale,
        next_steps=identify_next_steps(task, comparison, risks),
        artifacts=detect_artifacts(report_text),
        deliverables=check_deliverables(report_text, deliverables_of(task)),
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
