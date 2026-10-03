"""Catálogo dos modelos open source disponíveis localmente via Ollama.

Os pesos em RAM consideram quantização Q4_K_M no hardware alvo do projeto
(16 GB de RAM, GPU com 4 GB de VRAM).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.models.enums import TaskComplexity


@dataclass(frozen=True, slots=True)
class ModelSpec:
    """Ficha técnica de um modelo local."""

    name: str
    display_name: str
    vendor: str
    parameters: str
    quantization: str
    ram_mb: int
    vram_mb: int
    tier: int
    max_complexity: TaskComplexity
    strengths: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["max_complexity"] = self.max_complexity.value
        data["strengths"] = list(self.strengths)
        return data


MODEL_CATALOG: tuple[ModelSpec, ...] = (
    ModelSpec(
        name="llama3.2:3b",
        display_name="Llama 3.2 3B",
        vendor="Meta",
        parameters="3B",
        quantization="Q4_K_M",
        ram_mb=2_048,
        vram_mb=2_048,
        tier=1,
        max_complexity=TaskComplexity.SIMPLE,
        strengths=("conversação", "sumarização", "atas de reunião", "e-mails corporativos"),
    ),
    ModelSpec(
        name="phi4-mini:3.8b",
        display_name="Phi-4 Mini 3.8B",
        vendor="Microsoft",
        parameters="3.8B",
        quantization="Q4_K_M",
        ram_mb=2_355,
        vram_mb=2_355,
        tier=2,
        max_complexity=TaskComplexity.MODERATE,
        strengths=("raciocínio lógico", "matemática", "estruturação de dados", "revisão técnica"),
    ),
    ModelSpec(
        name="gemma3n:e4b",
        display_name="Gemma 3n E4B",
        vendor="Google DeepMind",
        parameters="E4B",
        quantization="Q4_K_M",
        ram_mb=3_072,
        vram_mb=3_072,
        tier=3,
        max_complexity=TaskComplexity.MODERATE,
        strengths=("multimodal", "thinking mode", "análises visuais", "documentação extensa"),
    ),
    ModelSpec(
        name="qwen3:8b",
        display_name="Qwen3 8B",
        vendor="Alibaba",
        parameters="8B",
        quantization="Q4_K_M",
        ram_mb=4_710,
        vram_mb=3_900,
        tier=4,
        max_complexity=TaskComplexity.COMPLEX,
        strengths=("codificação pesada", "lógica de alto nível", "arquitetura de software"),
    ),
    ModelSpec(
        name="deepseek-r1:8b",
        display_name="DeepSeek R1 8B",
        vendor="DeepSeek",
        parameters="8B",
        quantization="Q4_K_M",
        ram_mb=5_120,
        vram_mb=3_900,
        tier=5,
        max_complexity=TaskComplexity.CRITICAL,
        strengths=("chain-of-thought", "impasses estratégicos", "decisões vitais"),
    ),
)

_BY_NAME: dict[str, ModelSpec] = {spec.name: spec for spec in MODEL_CATALOG}

# Modelo preferencial por peso cognitivo da tarefa.
_PREFERRED_BY_COMPLEXITY: dict[TaskComplexity, str] = {
    TaskComplexity.TRIVIAL: "llama3.2:3b",
    TaskComplexity.SIMPLE: "llama3.2:3b",
    TaskComplexity.MODERATE: "phi4-mini:3.8b",
    TaskComplexity.COMPLEX: "qwen3:8b",
    TaskComplexity.CRITICAL: "deepseek-r1:8b",
}


def all_models() -> tuple[ModelSpec, ...]:
    """Catálogo completo, do mais leve para o mais pesado."""
    return tuple(sorted(MODEL_CATALOG, key=lambda spec: spec.tier))


def get_model(name: str) -> ModelSpec | None:
    """Busca uma ficha técnica pelo tag Ollama."""
    return _BY_NAME.get(name)


def lightest_model() -> ModelSpec:
    """Modelo de menor footprint — a saída de emergência da Natureza."""
    return all_models()[0]


def tier_below(spec: ModelSpec) -> ModelSpec:
    """Modelo imediatamente mais leve que `spec`, ou o próprio se já for o mais leve."""
    lighter = [candidate for candidate in all_models() if candidate.tier < spec.tier]
    return lighter[-1] if lighter else spec


def preferred_for(complexity: TaskComplexity) -> ModelSpec:
    """Modelo ideal para a complexidade informada, ignorando restrições de recurso."""
    return _BY_NAME[_PREFERRED_BY_COMPLEXITY[complexity]]


def best_fit_within(ceiling: ModelSpec, ram_budget_mb: int) -> ModelSpec | None:
    """Modelo mais capaz que cabe no orçamento sem ultrapassar o teto informado."""
    candidates = [
        spec for spec in all_models() if spec.tier <= ceiling.tier and spec.ram_mb <= ram_budget_mb
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda spec: spec.tier)


def best_fit(complexity: TaskComplexity, ram_budget_mb: int) -> ModelSpec | None:
    """Modelo mais capaz que cabe no orçamento de RAM, sem exceder o necessário.

    Retorna `None` quando nem o modelo mais leve cabe no orçamento.
    """
    return best_fit_within(preferred_for(complexity), ram_budget_mb)
