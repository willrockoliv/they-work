"""Catálogo de modelos e regra de seleção por complexidade."""

from __future__ import annotations

import pytest

from app.models.enums import TaskComplexity
from app.services import model_catalog


def test_catalogo_tem_os_cinco_modelos_do_prd() -> None:
    names = [spec.name for spec in model_catalog.all_models()]
    assert names == [
        "llama3.2:3b",
        "phi4-mini:3.8b",
        "gemma3n:e4b",
        "qwen3:8b",
        "deepseek-r1:8b",
    ]


def test_catalogo_ordenado_do_mais_leve_ao_mais_pesado() -> None:
    tiers = [spec.tier for spec in model_catalog.all_models()]
    assert tiers == sorted(tiers)


def test_todos_cabem_no_hardware_alvo_de_16gb() -> None:
    assert all(spec.ram_mb <= 16_384 for spec in model_catalog.all_models())


@pytest.mark.parametrize(
    ("complexity", "expected"),
    [
        (TaskComplexity.TRIVIAL, "llama3.2:3b"),
        (TaskComplexity.SIMPLE, "llama3.2:3b"),
        (TaskComplexity.MODERATE, "phi4-mini:3.8b"),
        (TaskComplexity.COMPLEX, "qwen3:8b"),
        (TaskComplexity.CRITICAL, "deepseek-r1:8b"),
    ],
)
def test_modelo_preferencial_por_complexidade(
    complexity: TaskComplexity, expected: str
) -> None:
    assert model_catalog.preferred_for(complexity).name == expected


def test_best_fit_nunca_ultrapassa_o_preferencial() -> None:
    spec = model_catalog.best_fit(TaskComplexity.SIMPLE, 16_000)
    assert spec is not None
    assert spec.name == "llama3.2:3b"


def test_best_fit_escolhe_o_mais_capaz_dentro_do_orcamento() -> None:
    spec = model_catalog.best_fit(TaskComplexity.CRITICAL, 4_800)
    assert spec is not None
    assert spec.name == "qwen3:8b"


def test_best_fit_retorna_none_sem_orcamento() -> None:
    assert model_catalog.best_fit(TaskComplexity.CRITICAL, 512) is None


def test_lightest_model() -> None:
    assert model_catalog.lightest_model().name == "llama3.2:3b"


def test_get_model_desconhecido() -> None:
    assert model_catalog.get_model("gpt-inexistente") is None
