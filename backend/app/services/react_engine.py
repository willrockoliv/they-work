"""Motor ReAct — executa uma tarefa expondo cada passo do raciocínio do agente.

Em vez de um framework de orquestração (ADR-004), o loop é escrito à mão sobre o
streaming do Ollama: o prompt impõe o formato `Pensamento / Ação / Entrada da Ação`,
o parser extrai cada rótulo e o `ReasoningTracer` publica o passo imediatamente.
Quando o Ollama está indisponível, um planejador determinístico assume o lugar do
modelo para que a simulação continue observável offline.
"""

from __future__ import annotations

import re
import time
import unicodedata
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.config.logging import get_logger
from app.config.settings import Settings, get_settings
from app.models.agent import Agent
from app.models.enums import AgentStatus, TaskComplexity
from app.models.reasoning import ReasoningSession
from app.services import complexity_classifier, model_catalog, reasoning_tools
from app.services.nature_manager import NatureManager
from app.services.ollama_client import (
    OllamaClient,
    OllamaCompletion,
    OllamaUnavailableError,
    run_sync,
)
from app.services.reasoning_tools import ToolContext
from app.services.reasoning_tracer import ReasoningTracer

logger = get_logger(__name__)

#: Causas pelas quais o turno não veio do modelo (registradas no payload do passo).
CAUSE_OLLAMA_NONE = "ollama_none"
CAUSE_OLLAMA_UNAVAILABLE = "ollama_indisponivel"
CAUSE_INVALID_FORMAT = "formato_invalido"

REACT_INSTRUCTIONS = """Você raciocina em voz alta seguindo estritamente o formato abaixo,
repetindo o bloco quantas vezes precisar antes de concluir:

Pensamento: <o que você sabe e o que falta descobrir>
Ação: <nome exato de uma ferramenta da lista>
Entrada da Ação: <o argumento da ferramenta>

Depois de receber a Observação, continue com um novo Pensamento. Quando tiver
informação suficiente, responda apenas:

Pensamento: <síntese final>
Conclusão: <resposta objetiva para a tarefa>

Ferramentas disponíveis:
{tools}

Nunca invente uma Observação: ela é fornecida pelo sistema."""


@dataclass(frozen=True, slots=True)
class ParsedTurn:
    """Rótulos extraídos de uma resposta do modelo."""

    thought: str = ""
    tool: str | None = None
    tool_input: str = ""
    conclusion: str | None = None

    @property
    def is_final(self) -> bool:
        return self.conclusion is not None


@dataclass(frozen=True, slots=True)
class TaskRequest:
    """Tarefa submetida a um agente para execução observável."""

    task: str
    complexity: TaskComplexity | None = None
    thread_id: uuid.UUID | None = None
    max_steps: int | None = None
    context: dict[str, Any] = field(default_factory=dict)
    #: Modo estrito (revisão do Chief): sem modelo não há conclusão, texto cru não
    #: vira conclusão e `required_tools` precisam ser observadas antes de concluir.
    strict: bool = False
    required_tools: tuple[str, ...] = ()
    #: Ferramentas permitidas (vazio = todas); filtra o catálogo e a execução.
    tools: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Observed:
    """Observação de ferramenta, citável como evidência pelo `id`."""

    id: str
    tool: str
    tool_input: str
    output: str
    payload: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


_LABELS: dict[str, str] = {
    "pensamento": "thought",
    "raciocinio": "thought",
    "acao": "tool",
    "ferramenta": "tool",
    "entrada da acao": "tool_input",
    "entrada": "tool_input",
    "conclusao": "conclusion",
    "resposta final": "conclusion",
}

_LABEL_RE = re.compile(r"^\s*\*{0,2}([A-Za-zÀ-ÿ ]{3,20})\*{0,2}\s*:\s*(.*)$")


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).strip()


def parse_turn(text: str) -> ParsedTurn:
    """Extrai os rótulos ReAct de uma resposta, tolerando ruído do modelo."""
    buckets: dict[str, list[str]] = {}
    current: str | None = None

    for line in text.splitlines():
        match = _LABEL_RE.match(line)
        label = _LABELS.get(_fold(match.group(1))) if match else None
        if label is not None and match is not None:
            current = label
            buckets.setdefault(label, []).append(match.group(2).strip())
            continue
        if current is not None and line.strip():
            buckets[current].append(line.strip())

    def joined(key: str) -> str:
        return "\n".join(part for part in buckets.get(key, []) if part).strip()

    conclusion = joined("conclusion")
    tool = joined("tool") or None
    return ParsedTurn(
        thought=joined("thought"),
        tool=None if conclusion else tool,
        tool_input=joined("tool_input"),
        conclusion=conclusion or None,
    )


def run_task(
    db: Session,
    *,
    agent: Agent | None,
    request: TaskRequest,
    nature: NatureManager | None = None,
    ollama: OllamaClient | None = None,
    settings: Settings | None = None,
    task_id: uuid.UUID | None = None,
    observed: list[Observed] | None = None,
) -> ReasoningSession:
    """Executa a tarefa capturando todo o ciclo ReAct em `reasoning_sessions`.

    `task_id` liga o ciclo a uma `AgentTask` da rede corporativa (Fase 5), o que
    habilita as ferramentas de revisão de report do Chief supervisor. Cada
    observação de ferramenta é anexada a `observed` com um id citável (`O1`, `O2`...).
    """
    config = settings or get_settings()
    complexity = request.complexity or complexity_classifier.classify(request.task).complexity
    model_name = _model_for(agent, complexity)
    max_steps = max(1, request.max_steps or config.reasoning_max_steps)

    tracer = ReasoningTracer(
        db,
        task=request.task,
        agent=agent,
        complexity=complexity,
        model_name=model_name,
        thread_id=request.thread_id,
        settings=config,
    )
    tracer.start()

    if agent is not None:
        agent.status = AgentStatus.WORKING
        db.flush()

    ctx = ToolContext(db=db, nature=nature, task_id=task_id, ollama=ollama, settings=config)
    system_prompt = _system_prompt(agent, request.tools)
    transcript: list[str] = []
    evidence = observed if observed is not None else []
    used_tools: set[str] = set()
    degraded: str | None = None

    try:
        for iteration in range(max_steps):
            turn, completion, cause = _next_turn(
                ollama, model_name, system_prompt, request, transcript, iteration
            )
            if completion is not None:
                tracer.account_usage(completion.prompt_tokens, completion.completion_tokens)

            if request.strict and cause is not None and cause != CAUSE_INVALID_FORMAT:
                message = f"Sem modelo disponível ({cause}): nenhuma conclusão foi produzida."
                tracer.on_conclusion(
                    message, payload={"iteration": iteration + 1, "fallback_cause": cause}
                )
                return _settle(db, agent, tracer, message, error=cause)
            if cause is not None and cause.startswith(CAUSE_OLLAMA_UNAVAILABLE):
                degraded = degraded or cause

            thought = turn.thought or "Avaliando a tarefa com as informações disponíveis."
            thought_payload: dict[str, Any] = {
                "iteration": iteration + 1,
                "raw": _raw_of(completion),
            }
            if cause is not None:
                thought_payload["fallback_cause"] = cause
            tracer.on_thought(
                thought,
                tokens=completion.completion_tokens if completion else 0,
                duration_ms=completion.duration_ms if completion else 0,
                payload=thought_payload,
            )
            transcript.append(f"Pensamento: {thought}")

            if request.strict and cause == CAUSE_INVALID_FORMAT:
                _nudge(
                    tracer,
                    transcript,
                    "Resposta fora do formato. Responda com 'Ação:' e 'Entrada da Ação:' "
                    "ou com 'Conclusão:'.",
                    CAUSE_INVALID_FORMAT,
                )
                continue

            if turn.is_final:
                missing = [name for name in request.required_tools if name not in used_tools]
                if request.strict and missing:
                    _nudge(
                        tracer,
                        transcript,
                        f"Protocolo incompleto: antes de concluir, use {', '.join(missing)}.",
                        "protocolo_incompleto",
                    )
                    continue
                conclusion = turn.conclusion or ""
                tracer.on_conclusion(conclusion, payload={"iteration": iteration + 1})
                return _settle(db, agent, tracer, conclusion, error=degraded)

            if turn.tool is None:
                if request.strict:
                    _nudge(
                        tracer,
                        transcript,
                        "Escolha uma Ação da lista de ferramentas ou escreva a Conclusão.",
                        "sem_acao",
                    )
                    continue
                conclusion = thought
                tracer.on_conclusion(
                    conclusion, payload={"iteration": iteration + 1, "reason": "sem_acao"}
                )
                return _settle(db, agent, tracer, conclusion, error=degraded)

            item = _execute_tool(
                tracer, ctx, turn, iteration, f"O{len(evidence) + 1}", request.tools
            )
            evidence.append(item)
            if item.error is None:
                used_tools.add(item.tool)
            transcript.append(f"Ação: {turn.tool}")
            transcript.append(f"Entrada da Ação: {turn.tool_input}")
            transcript.append(f"Observação [{item.id}]: {item.output}")

        conclusion = (
            f"Limite de {max_steps} passos atingido sem conclusão. Último estado conhecido: "
            f"{transcript[-1] if transcript else 'nenhum'}"
        )
        tracer.on_conclusion(conclusion, payload={"truncated": True, "max_steps": max_steps})
        return _settle(db, agent, tracer, conclusion, truncated=True, error=degraded)
    except Exception as exc:
        logger.warning("reasoning.run_failed", error=str(exc))
        if agent is not None:
            agent.status = AgentStatus.BLOCKED
        session = tracer.fail(str(exc))
        db.flush()
        return session


# --- Internos ----------------------------------------------------------------


def _settle(
    db: Session,
    agent: Agent | None,
    tracer: ReasoningTracer,
    conclusion: str,
    *,
    truncated: bool = False,
    error: str | None = None,
) -> ReasoningSession:
    if agent is not None:
        agent.status = AgentStatus.IDLE
    session = tracer.complete(conclusion, error=error)
    db.flush()
    logger.info("reasoning.run_completed", steps=session.step_count, truncated=truncated)
    return session


def _nudge(tracer: ReasoningTracer, transcript: list[str], message: str, reason: str) -> None:
    """Observação do sistema que devolve o modelo ao protocolo sem encerrar o ciclo."""
    tracer.on_observation(message, tool=None, error=reason)
    transcript.append(f"Observação [sistema]: {message}")


def _execute_tool(
    tracer: ReasoningTracer,
    ctx: ToolContext,
    turn: ParsedTurn,
    iteration: int,
    evidence_id: str,
    allowed: tuple[str, ...] = (),
) -> Observed:
    tool_name = turn.tool or ""
    tracer.on_action(tool_name, turn.tool_input, payload={"iteration": iteration + 1})

    spec = reasoning_tools.get_tool(tool_name)
    if spec is not None and allowed and spec.name not in allowed:
        spec = None
    if spec is None:
        hint = reasoning_tools.suggest(tool_name, allowed)
        message = (
            f"Ferramenta '{tool_name}' não existe."
            + (f" Você quis dizer '{hint}'?" if hint else "")
            + f" Disponíveis: {', '.join(allowed or tuple(reasoning_tools.TOOLS))}."
        )
        tracer.on_observation(
            message,
            tool=tool_name,
            error="unknown_tool",
            payload={"evidence_id": evidence_id, "suggestion": hint},
        )
        return Observed(evidence_id, tool_name, turn.tool_input, message, error="unknown_tool")

    started = time.monotonic()
    result = spec.run(ctx, turn.tool_input)
    elapsed = int((time.monotonic() - started) * 1000)
    tracer.on_observation(
        result.output,
        tool=spec.name,
        duration_ms=elapsed,
        error=result.error,
        payload={"evidence_id": evidence_id, **result.payload},
    )
    return Observed(
        evidence_id, spec.name, turn.tool_input, result.output, result.payload, result.error
    )


def _next_turn(
    ollama: OllamaClient | None,
    model_name: str,
    system_prompt: str,
    request: TaskRequest,
    transcript: list[str],
    iteration: int,
) -> tuple[ParsedTurn, OllamaCompletion | None, str | None]:
    """Pede o próximo passo ao modelo; cai no planejador determinístico se falhar.

    O terceiro item é a causa quando o turno não veio do modelo no formato esperado:
    `ollama_none`, `ollama_indisponivel: <erro>` ou `formato_invalido`.
    """
    if ollama is None:
        return _fallback_turn(request, transcript, iteration), None, CAUSE_OLLAMA_NONE

    prompt = _user_prompt(request, transcript)
    try:
        completion = _await(ollama.generate(model=model_name, prompt=prompt, system=system_prompt))
    except OllamaUnavailableError as exc:
        logger.warning("reasoning.ollama_unavailable", error=str(exc))
        failure = f"{CAUSE_OLLAMA_UNAVAILABLE}: {exc}"
        return _fallback_turn(request, transcript, iteration), None, failure
    parsed = parse_turn(completion.text)
    if parsed.thought or parsed.tool or parsed.conclusion:
        return parsed, completion, None
    raw = completion.text.strip()
    if request.strict:
        return ParsedTurn(thought=raw), completion, CAUSE_INVALID_FORMAT
    # Fora do modo estrito, a resposta crua vira pensamento e conclusão.
    return ParsedTurn(thought=raw, conclusion=raw), completion, CAUSE_INVALID_FORMAT


def _fallback_turn(request: TaskRequest, transcript: list[str], iteration: int) -> ParsedTurn:
    """Planejador determinístico: uma consulta de contexto e então a conclusão."""
    if iteration == 0:
        tool, tool_input = _pick_tool(request.task)
        return ParsedTurn(
            thought=(
                f"Preciso de contexto antes de responder sobre '{request.task[:120]}'. "
                f"Vou consultar {tool}."
            ),
            tool=tool,
            tool_input=tool_input,
        )
    observations = [line for line in transcript if line.startswith("Observação")]
    evidence = observations[-1].split(": ", 1)[-1].strip() if observations else "sem evidências"
    return ParsedTurn(
        thought="Reuni o contexto disponível no sandbox e já consigo fechar a resposta.",
        conclusion=(
            f"Sobre '{request.task[:160]}': com base no contexto interno consultado "
            f"({evidence[:400]}), a recomendação é avançar registrando a decisão na "
            "memória corporativa."
        ),
    )


_TOOL_HINTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("ram", "vram", "cpu", "infraestrutura", "hardware", "capacidade"), "infraestrutura"),
    (("contratar", "vaga", "cargo", "perfil", "talento", "subagente"), "banco_de_talentos"),
    (("auditoria", "evento", "historico", "trilha", "decisao"), "auditoria"),
)


def _pick_tool(task: str) -> tuple[str, str]:
    haystack = complexity_classifier.normalize(task)
    for terms, tool in _TOOL_HINTS:
        if any(term in haystack for term in terms):
            return tool, task[:120]
    return "memoria_corporativa", task[:120]


def _system_prompt(agent: Agent | None, tools: tuple[str, ...] = ()) -> str:
    persona = (agent.system_prompt or "").strip() if agent else ""
    instructions = REACT_INSTRUCTIONS.format(tools=reasoning_tools.catalog(tools))
    return f"{persona}\n\n{instructions}".strip()


def _user_prompt(request: TaskRequest, transcript: list[str]) -> str:
    parts = [f"Tarefa: {request.task}"]
    if request.context:
        details = "; ".join(f"{key}={value}" for key, value in request.context.items())
        parts.append(f"Contexto: {details}")
    if transcript:
        parts.append("\n".join(transcript))
    parts.append("Pensamento:")
    return "\n\n".join(parts)


def _model_for(agent: Agent | None, complexity: TaskComplexity) -> str:
    if agent is not None and agent.model_name:
        return agent.model_name
    return model_catalog.preferred_for(complexity).name


def _raw_of(completion: OllamaCompletion | None) -> str | None:
    return completion.text if completion is not None else None


def _await(coro: Any) -> OllamaCompletion:
    """Ponte síncrona para o Ollama (ver `ollama_client.run_sync`)."""
    return run_sync(coro)  # type: ignore[no-any-return]
