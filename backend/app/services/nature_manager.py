"""A Natureza — traduz os limites físicos do hardware em regras corporativas.

Monitora RAM (psutil) e VRAM (GPUtil) e decide se o RA pode instanciar novos
subagentes, forçando downgrade de modelo ou bloqueando contratações quando a
"infraestrutura da empresa" atinge a capacidade máxima.
"""

from __future__ import annotations

import threading
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

import psutil

from app.config.logging import get_logger
from app.config.settings import Settings, get_settings
from app.models.base import utcnow
from app.models.enums import NatureDecision, ResourceStatus, TaskComplexity
from app.services import model_catalog
from app.services.model_catalog import ModelSpec

logger = get_logger(__name__)

_BYTES_IN_MB = 1024 * 1024

#: Probe retorna (total_mb, used_mb).
MemoryProbe = Callable[[], tuple[int, int]]


@dataclass(frozen=True, slots=True)
class ResourceSnapshot:
    """Fotografia instantânea dos recursos físicos sob a ótica da Natureza."""

    timestamp: datetime
    status: ResourceStatus
    ram_limit_mb: int
    ram_total_mb: int
    ram_used_mb: int
    ram_allocatable_mb: int
    ram_usage_ratio: float
    vram_limit_mb: int
    vram_total_mb: int
    vram_used_mb: int
    vram_allocatable_mb: int
    vram_usage_ratio: float
    gpu_detected: bool
    cpu_percent: float
    narrative: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        data["status"] = self.status.value
        return data


@dataclass(frozen=True, slots=True)
class HiringRequest:
    """Requisição de contratação submetida pelo RA à Natureza."""

    requested_by: str
    job_title: str
    complexity: TaskComplexity
    requested_model: str | None = None


@dataclass(frozen=True, slots=True)
class HiringVerdict:
    """Veredito da Natureza sobre uma requisição de contratação."""

    decision: NatureDecision
    request: HiringRequest
    granted_model: str | None
    reason: str
    narrative: str
    snapshot: ResourceSnapshot
    queue_position: int | None = None

    @property
    def allowed(self) -> bool:
        return self.decision in (NatureDecision.ALLOWED, NatureDecision.DOWNGRADED)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "allowed": self.allowed,
            "requested_by": self.request.requested_by,
            "job_title": self.request.job_title,
            "complexity": self.request.complexity.value,
            "requested_model": self.request.requested_model,
            "granted_model": self.granted_model,
            "reason": self.reason,
            "narrative": self.narrative,
            "queue_position": self.queue_position,
            "resources": self.snapshot.to_dict(),
        }


def _psutil_ram_probe() -> tuple[int, int]:
    memory = psutil.virtual_memory()
    return memory.total // _BYTES_IN_MB, (memory.total - memory.available) // _BYTES_IN_MB


def _gputil_vram_probe() -> tuple[int, int]:
    """Lê a VRAM via GPUtil. Retorna (0, 0) quando não há GPU NVIDIA acessível."""
    try:
        import GPUtil  # importado sob demanda: ausente em runners sem GPU
    except ImportError:  # pragma: no cover - depende do ambiente
        return 0, 0

    try:
        gpus = GPUtil.getGPUs()
    except Exception:  # pragma: no cover - nvidia-smi ausente no container
        logger.debug("nature.vram_probe_failed")
        return 0, 0

    if not gpus:
        return 0, 0
    gpu = gpus[0]
    return int(gpu.memoryTotal), int(gpu.memoryUsed)


def _cpu_probe() -> float:
    return float(psutil.cpu_percent(interval=None))


@dataclass
class NatureManager:
    """Gestor de infraestrutura e limites físicos da simulação."""

    settings: Settings = field(default_factory=get_settings)
    ram_probe: MemoryProbe = _psutil_ram_probe
    vram_probe: MemoryProbe = _gputil_vram_probe
    cpu_probe: Callable[[], float] = _cpu_probe

    def __post_init__(self) -> None:
        self._lock = threading.Lock()
        self._queue: deque[HiringRequest] = deque(maxlen=self.settings.nature_max_queue_size)

    # --- Monitoramento -------------------------------------------------------

    def snapshot(self) -> ResourceSnapshot:
        """Lê RAM, VRAM e CPU e classifica a saúde da infraestrutura."""
        settings = self.settings

        ram_total, ram_used = self.ram_probe()
        vram_total, vram_used = self.vram_probe()

        ram_limit = min(settings.nature_ram_limit_mb, ram_total) if ram_total else (
            settings.nature_ram_limit_mb
        )
        gpu_detected = vram_total > 0
        vram_limit = min(settings.nature_vram_limit_mb, vram_total) if gpu_detected else 0

        ram_allocatable = max(ram_limit - ram_used - settings.nature_reserved_ram_mb, 0)
        vram_allocatable = max(vram_limit - vram_used - settings.nature_reserved_vram_mb, 0)

        ram_ratio = round(ram_used / ram_limit, 4) if ram_limit else 0.0
        vram_ratio = round(vram_used / vram_limit, 4) if vram_limit else 0.0

        status = self._classify(ram_ratio, vram_ratio)

        return ResourceSnapshot(
            timestamp=utcnow(),
            status=status,
            ram_limit_mb=ram_limit,
            ram_total_mb=ram_total,
            ram_used_mb=ram_used,
            ram_allocatable_mb=ram_allocatable,
            ram_usage_ratio=ram_ratio,
            vram_limit_mb=vram_limit,
            vram_total_mb=vram_total,
            vram_used_mb=vram_used,
            vram_allocatable_mb=vram_allocatable,
            vram_usage_ratio=vram_ratio,
            gpu_detected=gpu_detected,
            cpu_percent=self.cpu_probe(),
            narrative=_STATUS_NARRATIVE[status],
        )

    def _classify(self, ram_ratio: float, vram_ratio: float) -> ResourceStatus:
        worst = max(ram_ratio, vram_ratio)
        if worst >= self.settings.nature_critical_threshold:
            return ResourceStatus.CRITICAL
        if worst >= self.settings.nature_warning_threshold:
            return ResourceStatus.WARNING
        return ResourceStatus.HEALTHY

    # --- Governança de contratações -----------------------------------------

    def evaluate_hiring(
        self, request: HiringRequest, active_subagents: int = 0
    ) -> HiringVerdict:
        """Decide se a contratação prossegue, sofre downgrade, entra na fila ou é barrada."""
        snapshot = self.snapshot()
        preferred = self._preferred_model(request)

        if active_subagents >= self.settings.nature_max_concurrent_subagents:
            return self._defer(
                request,
                snapshot,
                reason=(
                    f"Limite de {self.settings.nature_max_concurrent_subagents} subagentes "
                    "simultâneos atingido."
                ),
                narrative=(
                    "Todas as estações de trabalho do escritório estão ocupadas. "
                    f"A contratação de '{request.job_title}' aguarda a liberação de uma mesa."
                ),
            )

        budget_mb = snapshot.ram_allocatable_mb

        if snapshot.status is ResourceStatus.CRITICAL:
            fallback = model_catalog.lightest_model()
            if fallback.ram_mb > budget_mb:
                return self._defer(
                    request,
                    snapshot,
                    reason="Recursos críticos: nem o modelo mais leve cabe no orçamento.",
                    narrative=(
                        "A infraestrutura da empresa atingiu a capacidade máxima. "
                        f"A contratação de '{request.job_title}' foi bloqueada até que o "
                        "projeto atual seja finalizado."
                    ),
                )
            return self._verdict(
                NatureDecision.DOWNGRADED,
                request,
                snapshot,
                fallback,
                reason=(
                    f"Recursos críticos ({snapshot.ram_usage_ratio:.0%} de RAM em uso): "
                    f"otimização forçada de '{preferred.name}' para '{fallback.name}'."
                ),
                narrative=(
                    "Em regime de contenção de custos, a diretoria aprovou a vaga apenas "
                    f"com o perfil mais enxuto ({fallback.display_name}) em vez de "
                    f"{preferred.display_name}."
                ),
            )

        granted = model_catalog.best_fit_within(preferred, budget_mb)
        if granted is None:
            return self._defer(
                request,
                snapshot,
                reason=f"Orçamento de {budget_mb} MB insuficiente para qualquer modelo.",
                narrative=(
                    "Não há orçamento de infraestrutura para mais um colaborador. "
                    f"A vaga de '{request.job_title}' entrou em espera."
                ),
            )

        if granted.tier < preferred.tier:
            return self._verdict(
                NatureDecision.DOWNGRADED,
                request,
                snapshot,
                granted,
                reason=(
                    f"'{preferred.name}' exige {preferred.ram_mb} MB, disponível {budget_mb} MB."
                ),
                narrative=(
                    f"O orçamento aprovado não comporta {preferred.display_name}; "
                    f"a vaga foi preenchida com {granted.display_name}."
                ),
            )

        return self._verdict(
            NatureDecision.ALLOWED,
            request,
            snapshot,
            granted,
            reason=f"Recursos suficientes ({budget_mb} MB alocáveis).",
            narrative=(
                f"Contratação aprovada: '{request.job_title}' assume a estação com "
                f"{granted.display_name}."
            ),
        )

    def _preferred_model(self, request: HiringRequest) -> ModelSpec:
        if request.requested_model:
            explicit = model_catalog.get_model(request.requested_model)
            if explicit is not None:
                return explicit
        return model_catalog.preferred_for(request.complexity)

    def _verdict(
        self,
        decision: NatureDecision,
        request: HiringRequest,
        snapshot: ResourceSnapshot,
        model: ModelSpec,
        *,
        reason: str,
        narrative: str,
    ) -> HiringVerdict:
        logger.info(
            "nature.hiring_decision",
            decision=decision.value,
            job_title=request.job_title,
            granted_model=model.name,
            ram_usage=snapshot.ram_usage_ratio,
        )
        return HiringVerdict(
            decision=decision,
            request=request,
            granted_model=model.name,
            reason=reason,
            narrative=narrative,
            snapshot=snapshot,
        )

    def _defer(
        self,
        request: HiringRequest,
        snapshot: ResourceSnapshot,
        *,
        reason: str,
        narrative: str,
    ) -> HiringVerdict:
        """Enfileira a requisição; bloqueia definitivamente se a fila estiver cheia."""
        position = self.enqueue(request)
        decision = NatureDecision.QUEUED if position is not None else NatureDecision.BLOCKED
        if position is None:
            narrative = (
                f"{narrative} A fila de contratações também está cheia — "
                "a requisição foi descartada."
            )
        logger.warning(
            "nature.hiring_deferred",
            decision=decision.value,
            job_title=request.job_title,
            reason=reason,
            queue_position=position,
        )
        return HiringVerdict(
            decision=decision,
            request=request,
            granted_model=None,
            reason=reason,
            narrative=narrative,
            snapshot=snapshot,
            queue_position=position,
        )

    # --- Fila de espera ------------------------------------------------------

    def enqueue(self, request: HiringRequest) -> int | None:
        """Adiciona a requisição à fila. Retorna a posição (1-based) ou `None` se cheia."""
        with self._lock:
            if len(self._queue) >= self.settings.nature_max_queue_size:
                return None
            self._queue.append(request)
            return len(self._queue)

    def dequeue(self) -> HiringRequest | None:
        """Remove e retorna a próxima requisição da fila."""
        with self._lock:
            return self._queue.popleft() if self._queue else None

    def pending(self) -> tuple[HiringRequest, ...]:
        """Requisições de contratação atualmente represadas."""
        with self._lock:
            return tuple(self._queue)

    def clear_queue(self) -> None:
        """Esvazia a fila de espera."""
        with self._lock:
            self._queue.clear()


_STATUS_NARRATIVE: dict[ResourceStatus, str] = {
    ResourceStatus.HEALTHY: (
        "A infraestrutura da empresa opera com folga; há espaço para novas contratações."
    ),
    ResourceStatus.WARNING: (
        "A infraestrutura da empresa se aproxima do limite. Novas contratações passarão "
        "por avaliação de custo."
    ),
    ResourceStatus.CRITICAL: (
        "A infraestrutura da empresa atingiu a capacidade máxima. Contratações estão "
        "congeladas até a conclusão dos projetos em andamento."
    ),
}

_nature_manager: NatureManager | None = None
_manager_lock = threading.Lock()


def get_nature_manager() -> NatureManager:
    """Instância singleton da Natureza usada pela API."""
    global _nature_manager
    if _nature_manager is None:
        with _manager_lock:
            if _nature_manager is None:
                _nature_manager = NatureManager()
    return _nature_manager
