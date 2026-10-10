"""Revisão por evidências — o modelo decide, as ferramentas fornecem os fatos.

Pipeline (ADR-022 a ADR-025):

1. **Exploração** — ciclo ReAct estrito com as ferramentas de revisão. Cada
   observação recebe um id citável (`O1`, `O2`...). `ler_report` e
   `checar_criterios` são obrigatórias; se o modelo não as usar, o sistema as
   executa e registra `protocolo_completado_pelo_sistema`.
2. **Veredito estruturado** — uma chamada final com `format=<JSON Schema>` e
   decodificação determinística (temperatura 0, seed fixa) devolve um `ChiefVerdict`.
3. **Validação** — evidências precisam existir, citações precisam estar no report e
   APPROVE com critério não atendido é inválido. Uma nova tentativa com o erro
   anexado; depois disso o resultado é `INVALID_OUTPUT`.

Este módulo não aplica o veredito: quem decide o que fazer com ele (shadow, vetos,
limite de tentativas) é o `agent_decision_engine`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session

from app.config.logging import get_logger
from app.config.settings import Settings
from app.models.agent import Agent
from app.models.enums import ChiefDecision, DecisionSource
from app.models.network import AgentTask
from app.models.reasoning import ReasoningSession
from app.services import model_catalog, react_engine, reasoning_tools, report_analysis
from app.services.nature_manager import NatureManager
from app.services.ollama_client import OllamaClient, OllamaUnavailableError, run_sync
from app.services.react_engine import Observed, TaskRequest
from app.services.reasoning_tools import ToolContext

logger = get_logger(__name__)

#: Ferramentas que precisam ter sido observadas antes do veredito.
REQUIRED_TOOLS: tuple[str, ...] = ("ler_report", "checar_criterios")

#: Passos da exploração: as duas obrigatórias, algumas de apoio e a conclusão.
EXPLORATION_MAX_STEPS = 8

#: Quanto de cada observação entra no prompt do veredito (cabe em `num_ctx`).
OBSERVATION_CHARS = 700

VerdictLabel = Literal["APPROVE", "REJECT", "MODIFY", "CONSULT_PEERS", "ESCALATE"]


class CriterionVerdict(BaseModel):
    """Julgamento de um critério de aceitação, com a citação que o sustenta."""

    model_config = ConfigDict(extra="forbid")

    criterio: str
    atendido: bool
    citacao: str = ""
    correcao: str = ""


class ChiefVerdict(BaseModel):
    """Contrato do veredito: o que o modelo precisa devolver na chamada final."""

    model_config = ConfigDict(extra="forbid")

    veredito: VerdictLabel
    justificativa: str = Field(min_length=10)
    evidencias: list[str] = Field(min_length=1)
    criterios: list[CriterionVerdict] = Field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ReviewFeedback:
    """Item de feedback estruturado que acompanha uma reconvocação."""

    criterio: str
    citacao: str
    correcao: str

    def to_dict(self) -> dict[str, str]:
        return {"criterio": self.criterio, "citacao": self.citacao, "correcao": self.correcao}


@dataclass(slots=True)
class ReviewOutcome:
    """Resultado do pipeline: veredito válido, ou a causa de não haver um."""

    reasoning: ReasoningSession
    observations: list[Observed]
    source: DecisionSource
    verdict: ChiefVerdict | None = None
    errors: list[str] = field(default_factory=list)
    completed_by_system: list[str] = field(default_factory=list)
    tokens: int = 0

    @property
    def decision(self) -> ChiefDecision | None:
        return ChiefDecision(self.verdict.veredito) if self.verdict else None

    def feedback(self) -> list[ReviewFeedback]:
        """Critérios não atendidos, com citação e correção pedida."""
        if self.verdict is not None:
            items = [
                ReviewFeedback(
                    item.criterio,
                    item.citacao,
                    item.correcao or f"Cobrir explicitamente: {item.criterio}",
                )
                for item in self.verdict.criterios
                if not item.atendido
            ]
            if items:
                return items
        return [
            ReviewFeedback(
                str(item["criterio"]),
                str(item.get("citacao") or ""),
                f"Cobrir explicitamente: {item['criterio']}",
            )
            for item in _criteria_payload(self.observations)
            if not item.get("atendido")
        ]

    def to_evidence(self) -> dict[str, Any]:
        return {
            "source": self.source.value,
            "verdict": self.verdict.model_dump() if self.verdict else None,
            "errors": list(self.errors),
            "protocolo_completado_pelo_sistema": list(self.completed_by_system),
            "observations": [
                {
                    "id": item.id,
                    "tool": item.tool,
                    "input": item.tool_input[:200],
                    "output": item.output[:OBSERVATION_CHARS],
                    "error": item.error,
                }
                for item in self.observations
            ],
            "criteria": _criteria_payload(self.observations),
            "tokens": self.tokens,
        }


def review(
    session: Session,
    task: AgentTask,
    agent: Agent,
    *,
    allowed: tuple[ChiefDecision, ...],
    instruction: str,
    context: dict[str, Any],
    settings: Settings,
    nature: NatureManager | None = None,
    ollama: OllamaClient | None = None,
) -> ReviewOutcome:
    """Explora com ferramentas, pede o veredito estruturado e o valida."""
    observations: list[Observed] = []
    reasoning = react_engine.run_task(
        session,
        agent=agent,
        request=TaskRequest(
            task=instruction,
            max_steps=EXPLORATION_MAX_STEPS,
            context=context,
            strict=True,
            required_tools=REQUIRED_TOOLS,
            tools=reasoning_tools.REVIEW_TOOLS,
        ),
        nature=nature,
        ollama=ollama,
        settings=settings,
        task_id=task.id,
        observed=observations,
    )

    unavailable = _unavailable_cause(reasoning)
    ctx = ToolContext(
        db=session,
        nature=nature,
        task_id=task.id,
        ollama=None if unavailable else ollama,
        settings=settings,
    )
    completed = _complete_protocol(ctx, observations)
    outcome = ReviewOutcome(
        reasoning=reasoning,
        observations=observations,
        source=DecisionSource.UNAVAILABLE,
        completed_by_system=completed,
    )
    if unavailable or ollama is None:
        outcome.errors.append(unavailable or react_engine.CAUSE_OLLAMA_NONE)
        return outcome

    model = agent.model_name or model_catalog.preferred_for(reasoning.complexity).name
    prompt = _verdict_prompt(task, instruction, allowed, observations)
    schema = verdict_schema(allowed)
    for _attempt in range(2):
        try:
            completion = run_sync(
                ollama.generate(
                    model=model,
                    prompt=prompt,
                    system=VERDICT_SYSTEM,
                    format=schema,
                    options={
                        "temperature": 0,
                        "seed": settings.chief_decision_seed,
                        "num_ctx": settings.chief_decision_num_ctx,
                    },
                )
            )
        except OllamaUnavailableError as exc:
            outcome.errors.append(f"{react_engine.CAUSE_OLLAMA_UNAVAILABLE}: {exc}")
            outcome.source = DecisionSource.UNAVAILABLE
            return outcome
        outcome.tokens += completion.total_tokens
        _account(reasoning, completion.prompt_tokens, completion.completion_tokens)
        verdict, problems = validate(completion.text, task, observations, allowed)
        if verdict is not None:
            outcome.verdict = verdict
            outcome.source = DecisionSource.MODEL
            return outcome
        outcome.errors.extend(problems)
        prompt = (
            f"{prompt}\n\nSua resposta anterior foi recusada: {'; '.join(problems)}. "
            "Corrija e responda de novo apenas com o JSON."
        )
    outcome.source = DecisionSource.INVALID_OUTPUT
    logger.info("review.invalid_output", task_id=str(task.id), errors=outcome.errors)
    return outcome


VERDICT_SYSTEM = (
    "Você é o Chief supervisor emitindo o veredito final de uma revisão. Responda apenas "
    "com o JSON pedido. Toda afirmação precisa citar ids de observações em 'evidencias'. "
    "'citacao' deve ser um trecho LITERAL do report. Não aprove report com critério não "
    "atendido. " + reasoning_tools.REPORT_DATA_NOTICE
)


def verdict_schema(allowed: tuple[ChiefDecision, ...]) -> dict[str, Any]:
    """JSON Schema do `ChiefVerdict`, com o enum restrito aos vereditos permitidos."""
    schema = ChiefVerdict.model_json_schema()
    schema["properties"]["veredito"]["enum"] = [decision.value for decision in allowed]
    return schema


def validate(
    raw: str,
    task: AgentTask,
    observations: list[Observed],
    allowed: tuple[ChiefDecision, ...],
) -> tuple[ChiefVerdict | None, list[str]]:
    """Valida forma e substância do veredito; devolve os problemas encontrados."""
    try:
        verdict = ChiefVerdict.model_validate_json(raw)
    except ValidationError as exc:
        return None, [f"json_invalido: {exc.errors()[0]['msg']}"]

    problems: list[str] = []
    if verdict.veredito not in {decision.value for decision in allowed}:
        problems.append(f"veredito_fora_do_menu: {verdict.veredito}")

    valid_ids = {item.id for item in observations if item.error is None}
    unknown = [ref for ref in verdict.evidencias if ref not in valid_ids]
    if unknown or not set(verdict.evidencias) & valid_ids:
        problems.append(f"evidencia_inexistente: {', '.join(unknown) or 'nenhuma válida'}")

    report = task.report_summary or ""
    for item in verdict.criterios:
        if item.atendido and not report_analysis.verify_quote(item.citacao, report):
            problems.append(f"citacao_nao_encontrada: {item.criterio[:60]}")

    if verdict.veredito == ChiefDecision.APPROVE.value:
        expected = len(report_analysis.criteria_of(task))
        if any(not item.atendido for item in verdict.criterios):
            problems.append("approve_com_criterio_nao_atendido")
        if len(verdict.criterios) < expected:
            problems.append("approve_sem_julgar_todos_os_criterios")

    return (None, problems) if problems else (verdict, [])


# --- Internos ----------------------------------------------------------------


def _unavailable_cause(reasoning: ReasoningSession) -> str | None:
    error = reasoning.error or ""
    if error.startswith((react_engine.CAUSE_OLLAMA_NONE, react_engine.CAUSE_OLLAMA_UNAVAILABLE)):
        return error
    if reasoning.conclusion is None and error:
        return f"motor_falhou: {error}"
    return None


def _complete_protocol(ctx: ToolContext, observations: list[Observed]) -> list[str]:
    """Roda as ferramentas obrigatórias que o modelo deixou de usar."""
    done = {item.tool for item in observations if item.error is None}
    completed: list[str] = []
    for name in REQUIRED_TOOLS:
        if name in done:
            continue
        spec = reasoning_tools.TOOLS[name]
        result = spec.run(ctx, "")
        observations.append(
            Observed(
                f"O{len(observations) + 1}",
                spec.name,
                "",
                result.output,
                result.payload,
                result.error,
            )
        )
        completed.append(name)
    return completed


def _criteria_payload(observations: list[Observed]) -> list[dict[str, Any]]:
    """Resultado da última `checar_criterios` sem erro."""
    for item in reversed(observations):
        if item.tool == "checar_criterios" and item.error is None:
            return list(item.payload.get("criteria", []))
    return []


def _verdict_prompt(
    task: AgentTask,
    instruction: str,
    allowed: tuple[ChiefDecision, ...],
    observations: list[Observed],
) -> str:
    lines = [
        f"Tarefa revisada: '{task.title}' (tentativa {task.attempt}).",
        f"Objetivo original: {report_analysis.objective_of(task)}",
        f"Pedido: {instruction}",
        "Vereditos permitidos: " + " | ".join(decision.value for decision in allowed),
        "Critérios de aceitação: "
        + (
            "; ".join(
                f"[C{i}] {c}" for i, c in enumerate(report_analysis.criteria_of(task), 1)
            )
            or "nenhum"
        ),
        "",
        "Observações coletadas (cite pelos ids):",
    ]
    for item in observations:
        status = f" (erro: {item.error})" if item.error else ""
        lines.append(f"[{item.id}] {item.tool}{status}: {item.output[:OBSERVATION_CHARS]}")
    lines.append("")
    lines.append(
        "Responda com o JSON do veredito. Em REJECT ou MODIFY, liste em 'criterios' os "
        "não atendidos com a 'correcao' esperada."
    )
    return "\n".join(lines)


def _account(reasoning: ReasoningSession, prompt_tokens: int, completion_tokens: int) -> None:
    reasoning.prompt_tokens += prompt_tokens
    reasoning.completion_tokens += completion_tokens
    reasoning.total_tokens += prompt_tokens + completion_tokens
