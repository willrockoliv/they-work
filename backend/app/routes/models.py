"""Endpoints do catálogo de modelos locais."""

from __future__ import annotations

from fastapi import APIRouter

from app.models.enums import TaskComplexity
from app.routes.deps import Nature, Ollama
from app.schemas.models import ModelAvailability, ModelsAvailableResponse, ModelSelectionResponse
from app.services import model_catalog
from app.services.ollama_client import OllamaUnavailableError

router = APIRouter(prefix="/models", tags=["modelos"])


@router.get("/available", response_model=ModelsAvailableResponse, summary="Modelos disponíveis")
async def available_models(ollama: Ollama, nature: Nature) -> ModelsAvailableResponse:
    """Cruza o catálogo do projeto com o que está realmente baixado no Ollama."""
    try:
        installed = {model.name: model for model in await ollama.list_installed()}
        reachable = True
    except OllamaUnavailableError:
        installed = {}
        reachable = False

    version = await ollama.version() if reachable else None
    budget_mb = nature.snapshot().ram_allocatable_mb

    models = []
    for spec in model_catalog.all_models():
        local = installed.get(spec.name) or installed.get(f"{spec.name}:latest")
        models.append(
            ModelAvailability(
                **spec.to_dict(),
                installed=local is not None,
                installed_size_mb=local.size_mb if local else None,
                fits_current_budget=spec.ram_mb <= budget_mb,
            )
        )

    return ModelsAvailableResponse(
        ollama_reachable=reachable,
        ollama_version=version,
        ram_allocatable_mb=budget_mb,
        models=models,
    )


@router.get(
    "/select",
    response_model=ModelSelectionResponse,
    summary="Seleciona automaticamente o modelo para uma complexidade de tarefa",
)
def select_model(
    nature: Nature, complexity: TaskComplexity = TaskComplexity.SIMPLE
) -> ModelSelectionResponse:
    """Aplica a regra de seleção por peso da tarefa, limitada pelo orçamento da Natureza."""
    budget_mb = nature.snapshot().ram_allocatable_mb
    preferred = model_catalog.preferred_for(complexity)
    selected = model_catalog.best_fit(complexity, budget_mb)

    if selected is None:
        reason = f"Nenhum modelo cabe no orçamento atual de {budget_mb} MB."
    elif selected.tier < preferred.tier:
        reason = (
            f"Downgrade forçado pela Natureza: '{preferred.name}' exige {preferred.ram_mb} MB, "
            f"disponível {budget_mb} MB."
        )
    else:
        reason = f"Modelo ideal disponível dentro do orçamento de {budget_mb} MB."

    return ModelSelectionResponse(
        complexity=complexity,
        preferred_model=preferred.name,
        selected_model=selected.name if selected else None,
        downgraded=selected is not None and selected.tier < preferred.tier,
        reason=reason,
        ram_allocatable_mb=budget_mb,
    )
