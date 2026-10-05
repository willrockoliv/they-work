"""A Natureza — traduz os limites físicos do hardware em regras corporativas.

Monitora RAM (psutil) e VRAM (nvidia-smi) e decide se o RA pode instanciar novos
subagentes, forçando downgrade de modelo ou bloqueando contratações quando a
"infraestrutura da empresa" atinge a capacidade máxima.
"""

from __future__ import annotations

import shutil
import subprocess
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
_VRAM_PROBE_TIMEOUT_S = 2.0

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


@dataclass(frozen=True, slots=True)
class NatureAlert:
    """Aviso corporativo estruturado, pronto para injetar no contexto dos agentes."""

    code: str
    severity: ResourceStatus
    message: str
    narrative: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
            "narrative": self.narrative,
        }


def _psutil_ram_probe() -> tuple[int, int]:
    memory = psutil.virtual_memory()
    return memory.total // _BYTES_IN_MB, (memory.total - memory.available) // _BYTES_IN_MB


def _nvidia_smi_vram_probe() -> tuple[int, int]:
    """Lê a VRAM da primeira GPU via nvidia-smi. Retorna (0, 0) sem GPU acessível."""
    binary = shutil.which("nvidia-smi")
    if binary is None:
        return 0, 0

    try:
        completed = subprocess.run(
            [
                binary,
                "--query-gpu=memory.total,memory.used",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=_VRAM_PROBE_TIMEOUT_S,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):  # pragma: no cover - depende do host
        logger.debug("nature.vram_probe_failed")
        return 0, 0

    first_line = completed.stdout.strip().splitlines()
    if not first_line:
        return 0, 0

    try:
        total, used = (int(float(field)) for field in first_line[0].split(","))
    except ValueError:  # pragma: no cover - formato inesperado do driver
        logger.debug("nature.vram_probe_unparseable", payload=first_line[0])
        return 0, 0

    return total, used


def _cpu_probe() -> float:
    return float(psutil.cpu_percent(interval=None))


@dataclass
class NatureManager:
    """Gestor de infraestrutura e limites físicos da simulação."""

    settings: Settings = field(default_factory=get_settings)
    ram_probe: MemoryProbe = _psutil_ram_probe
    vram_probe: MemoryProbe = _nvidia_smi_vram_probe
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
        ceiling = self._ceiling_for(preferred, snapshot.status)
        granted = model_catalog.best_fit_within(ceiling, budget_mb)

        if granted is None:
            return self._defer(
                request,
                snapshot,
                reason=(
                    f"Orçamento de {budget_mb} MB insuficiente para o teto '{ceiling.name}' "
                    f"em regime {snapshot.status.value}."
                ),
                narrative=_NO_BUDGET_NARRATIVE[snapshot.status].format(job=request.job_title),
            )

        if granted.tier < preferred.tier:
            contained = ceiling.tier < preferred.tier
            return self._verdict(
                NatureDecision.DOWNGRADED,
                request,
                snapshot,
                granted,
                reason=(
                    f"Regime de contenção ({snapshot.ram_usage_ratio:.0%} de RAM em uso): "
                    f"teto rebaixado de '{preferred.name}' para '{ceiling.name}'."
                    if contained
                    else (
                        f"'{preferred.name}' exige {preferred.ram_mb} MB, "
                        f"disponível {budget_mb} MB."
                    )
                ),
                narrative=(
                    "Em regime de contenção de custos, a diretoria aprovou a vaga apenas com "
                    f"o perfil mais enxuto ({granted.display_name}) em vez de "
                    f"{preferred.display_name}."
                    if contained
                    else (
                        f"O orçamento aprovado não comporta {preferred.display_name}; "
                        f"a vaga foi preenchida com {granted.display_name}."
                    )
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

    def _ceiling_for(self, preferred: ModelSpec, status: ResourceStatus) -> ModelSpec:
        """Teto de contratação ajustado ao regime da infraestrutura.

        Rebaixar o teto (em vez de desviar para um ramo próprio) mantém uma única regra de
        seleção: o orçamento continua decidindo, o regime só limita o quão longe ele vai.
        """
        if status is ResourceStatus.CRITICAL:
            return model_catalog.lightest_model()
        if status is ResourceStatus.WARNING:
            return model_catalog.tier_below(preferred)
        return preferred

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

    # --- Alertas -------------------------------------------------------------

    def alerts(
        self, snapshot: ResourceSnapshot | None = None, *, active_subagents: int = 0
    ) -> tuple[NatureAlert, ...]:
        """Avisos que a Natureza injeta no contexto da empresa no estado atual."""
        current = snapshot or self.snapshot()
        found: list[NatureAlert] = []

        if current.status is ResourceStatus.CRITICAL:
            found.append(
                NatureAlert(
                    code="CAPACITY_EXHAUSTED",
                    severity=ResourceStatus.CRITICAL,
                    message="Capacidade máxima de infraestrutura atingida.",
                    narrative=(
                        "A infraestrutura da empresa atingiu a capacidade máxima. Novas "
                        "contratações estão bloqueadas até que o projeto atual seja finalizado."
                    ),
                )
            )
        elif current.status is ResourceStatus.WARNING:
            found.append(
                NatureAlert(
                    code="CAPACITY_WARNING",
                    severity=ResourceStatus.WARNING,
                    message="Infraestrutura próxima do limite operacional.",
                    narrative=(
                        "O consumo de infraestrutura se aproxima do teto aprovado. A diretoria "
                        "deve priorizar perfis mais enxutos nas próximas contratações."
                    ),
                )
            )

        if active_subagents >= self.settings.nature_max_concurrent_subagents:
            found.append(
                NatureAlert(
                    code="HEADCOUNT_FULL",
                    severity=ResourceStatus.CRITICAL,
                    message="Quadro de subagentes lotado.",
                    narrative=(
                        "Todas as estações de trabalho estão ocupadas. Qualquer nova vaga "
                        "aguardará a demissão de um colaborador em atividade."
                    ),
                )
            )

        queued = len(self.pending())
        if queued:
            found.append(
                NatureAlert(
                    code="HIRING_QUEUE",
                    severity=ResourceStatus.WARNING,
                    message=f"{queued} contratação(ões) represada(s).",
                    narrative=(
                        f"O RH mantém {queued} vaga(s) em espera por falta de orçamento de "
                        "infraestrutura."
                    ),
                )
            )

        if current.gpu_detected and current.vram_allocatable_mb <= 0:
            found.append(
                NatureAlert(
                    code="VRAM_EXHAUSTED",
                    severity=ResourceStatus.CRITICAL,
                    message="VRAM alocada integralmente.",
                    narrative=(
                        "A aceleração por GPU está indisponível; os colaboradores passarão a "
                        "operar em ritmo reduzido até a liberação de memória de vídeo."
                    ),
                )
            )

        return tuple(found)


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

_NO_BUDGET_NARRATIVE: dict[ResourceStatus, str] = {
    ResourceStatus.HEALTHY: (
        "Não há orçamento de infraestrutura para mais um colaborador. "
        "A vaga de '{job}' entrou em espera."
    ),
    ResourceStatus.WARNING: (
        "O orçamento de infraestrutura chegou ao limite aprovado. "
        "A vaga de '{job}' entrou em espera até a liberação de recursos."
    ),
    ResourceStatus.CRITICAL: (
        "A infraestrutura da empresa atingiu a capacidade máxima. A contratação de "
        "'{job}' foi bloqueada até que o projeto atual seja finalizado."
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
