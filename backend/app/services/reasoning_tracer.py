"""Interceptação do fluxo cognitivo — persiste e transmite cada passo do ciclo ReAct.

O `ReasoningTracer` é o ponto único por onde todo pensamento, ação, observação e
conclusão passa: grava o passo em `reasoning_steps`, atualiza os totais da sessão
e publica o evento no barramento para os clientes WebSocket (ADR-007).
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.config.logging import get_logger
from app.config.settings import Settings, get_settings
from app.models.agent import Agent
from app.models.base import utcnow
from app.models.enums import (
    AuditEventType,
    ReasoningStatus,
    ReasoningStepType,
    TaskComplexity,
)
from app.models.reasoning import ReasoningSession, ReasoningStep
from app.services import audit_service
from app.services.reasoning_broker import ReasoningBroker, get_broker

logger = get_logger(__name__)


class ReasoningTracer:
    """Captura o raciocínio de um agente durante uma única execução de tarefa."""

    def __init__(
        self,
        db: Session,
        *,
        task: str,
        agent: Agent | None = None,
        complexity: TaskComplexity = TaskComplexity.SIMPLE,
        model_name: str | None = None,
        thread_id: uuid.UUID | None = None,
        settings: Settings | None = None,
        broker: ReasoningBroker | None = None,
    ) -> None:
        self._db = db
        self._settings = settings or get_settings()
        self._broker = broker or get_broker()
        self._agent = agent
        self._sequence = 0
        self._started_monotonic = time.monotonic()
        self.session = ReasoningSession(
            agent_id=agent.id if agent else None,
            thread_id=thread_id,
            task=task,
            status=ReasoningStatus.RUNNING,
            complexity=complexity,
            model_name=model_name or (agent.model_name if agent else None),
            estimated_ram_mb=agent.estimated_ram_mb if agent else 0,
            started_at=utcnow(),
        )

    # --- Ciclo de vida -------------------------------------------------------

    def start(self) -> ReasoningSession:
        """Abre a sessão, registra a auditoria e anuncia o início no barramento."""
        self._db.add(self.session)
        self._db.flush()

        audit_service.record_event(
            self._db,
            event_type=AuditEventType.REASONING_STARTED,
            actor=self._actor,
            summary=f"Raciocínio iniciado: {self.session.task[:120]}",
            narrative=(
                f"{self._actor} começou a raciocinar sobre a tarefa designada; cada passo "
                "do ciclo ReAct será registrado na trilha cognitiva."
            ),
            agent_id=self.session.agent_id,
            payload={
                "session_id": str(self.session.id),
                "model": self.session.model_name,
                "complexity": self.session.complexity.value,
            },
        )
        self._db.flush()
        self._publish("session.started", self._session_event())
        return self.session

    def complete(self, conclusion: str = "", *, error: str | None = None) -> ReasoningSession:
        """Encerra a sessão com sucesso; `error` registra degradação sem mudar o status."""
        return self._finish(ReasoningStatus.COMPLETED, conclusion=conclusion, error=error)

    def fail(self, error: str) -> ReasoningSession:
        """Encerra a sessão em erro, preservando os passos já capturados."""
        return self._finish(ReasoningStatus.FAILED, error=error)

    def cancel(self, reason: str = "") -> ReasoningSession:
        return self._finish(ReasoningStatus.CANCELLED, error=reason or None)

    # --- Callbacks de interceptação -----------------------------------------

    def on_thought(
        self,
        content: str,
        *,
        tokens: int = 0,
        duration_ms: int = 0,
        payload: dict[str, Any] | None = None,
    ) -> ReasoningStep:
        """Pensamento bruto do modelo antes de decidir o que fazer."""
        return self._emit(ReasoningStepType.THOUGHT, content, tokens, duration_ms, payload)

    def on_action(
        self,
        tool: str,
        tool_input: str,
        *,
        tokens: int = 0,
        duration_ms: int = 0,
        payload: dict[str, Any] | None = None,
    ) -> ReasoningStep:
        """Uso de ferramenta: o termo de pesquisa / entrada bruta fica no payload."""
        data: dict[str, Any] = {"tool": tool, "tool_input": tool_input}
        data.update(payload or {})
        return self._emit(
            ReasoningStepType.ACTION, f"{tool}({tool_input})", tokens, duration_ms, data
        )

    def on_observation(
        self,
        content: str,
        *,
        tool: str | None = None,
        duration_ms: int = 0,
        error: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> ReasoningStep:
        """Resultado devolvido pela ferramenta ao agente."""
        data: dict[str, Any] = {"tool": tool, "error": error}
        data.update(payload or {})
        return self._emit(ReasoningStepType.OBSERVATION, content, 0, duration_ms, data)

    def on_conclusion(
        self,
        content: str,
        *,
        tokens: int = 0,
        duration_ms: int = 0,
        payload: dict[str, Any] | None = None,
    ) -> ReasoningStep:
        """Resposta final do agente para a tarefa."""
        return self._emit(ReasoningStepType.CONCLUSION, content, tokens, duration_ms, payload)

    # --- Contabilidade -------------------------------------------------------

    def account_usage(self, prompt_tokens: int, completion_tokens: int) -> None:
        """Soma o consumo de uma chamada ao modelo nos totais da sessão."""
        self.session.prompt_tokens += prompt_tokens
        self.session.completion_tokens += completion_tokens
        self.session.total_tokens = self.session.prompt_tokens + self.session.completion_tokens

    # --- Internos ------------------------------------------------------------

    @property
    def _actor(self) -> str:
        return self._agent.name if self._agent else "SYSTEM"

    def _emit(
        self,
        step_type: ReasoningStepType,
        content: str,
        tokens: int,
        duration_ms: int,
        payload: dict[str, Any] | None,
    ) -> ReasoningStep:
        self._sequence += 1
        step = ReasoningStep(
            session_id=self.session.id,
            sequence=self._sequence,
            step_type=step_type,
            content=self._truncate(content),
            model_name=self.session.model_name,
            tokens=tokens,
            duration_ms=duration_ms,
            payload=_clean(payload),
        )
        self.session.step_count = self._sequence

        if self._settings.reasoning_capture_enabled:
            self._db.add(step)
            self._db.flush()
            self._publish("step", step.to_dict())
        return step

    def _finish(
        self,
        status: ReasoningStatus,
        *,
        conclusion: str = "",
        error: str | None = None,
    ) -> ReasoningSession:
        self.session.status = status
        self.session.finished_at = utcnow()
        self.session.duration_ms = int((time.monotonic() - self._started_monotonic) * 1000)
        if conclusion:
            self.session.conclusion = self._truncate(conclusion)
        if error:
            self.session.error = self._truncate(error)

        event_type = (
            AuditEventType.REASONING_COMPLETED
            if status is ReasoningStatus.COMPLETED
            else AuditEventType.REASONING_FAILED
        )
        audit_service.record_event(
            self._db,
            event_type=event_type,
            actor=self._actor,
            decision=status.value,
            summary=f"Raciocínio {status.value}: {self.session.task[:100]}",
            narrative=error or conclusion or "Sessão de raciocínio encerrada.",
            agent_id=self.session.agent_id,
            payload={
                "session_id": str(self.session.id),
                "steps": self.session.step_count,
                "total_tokens": self.session.total_tokens,
                "duration_ms": self.session.duration_ms,
            },
        )
        self._db.flush()
        self._publish("session.finished", self._session_event())
        logger.info(
            "reasoning.session_finished",
            session_id=str(self.session.id),
            status=status.value,
            steps=self.session.step_count,
        )
        return self.session

    def _publish(self, event: str, data: dict[str, Any]) -> None:
        self._broker.publish(
            {"event": event, "session_id": str(self.session.id), "data": data},
            agent_id=self.session.agent_id,
        )

    def _session_event(self) -> dict[str, Any]:
        return {
            "id": str(self.session.id),
            "agent_id": str(self.session.agent_id) if self.session.agent_id else None,
            "task": self.session.task,
            "status": self.session.status.value,
            "model_name": self.session.model_name,
            "step_count": self.session.step_count,
            "total_tokens": self.session.total_tokens,
            "duration_ms": self.session.duration_ms,
            "conclusion": self.session.conclusion,
            "error": self.session.error,
        }

    def _truncate(self, content: str) -> str:
        limit = self._settings.reasoning_max_content_chars
        return content if len(content) <= limit else content[:limit] + "…[truncado]"


def _clean(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Remove chaves nulas para manter o JSONB enxuto."""
    return {key: value for key, value in (payload or {}).items() if value is not None}
