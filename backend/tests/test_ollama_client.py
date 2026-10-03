"""Cliente Ollama — parsing de respostas e tolerância a indisponibilidade."""

from __future__ import annotations

import httpx
import pytest

from app.services.ollama_client import OllamaClient, OllamaUnavailableError
from tests.conftest import make_ollama


async def test_version() -> None:
    assert await make_ollama().version() == "0.12.11"


async def test_is_healthy() -> None:
    assert await make_ollama().is_healthy() is True


async def test_list_installed_parseia_detalhes() -> None:
    models = await make_ollama().list_installed()

    assert len(models) == 1
    assert models[0].name == "llama3.2:3b"
    assert models[0].size_mb == 2_048
    assert models[0].quantization == "Q4_K_M"


async def test_servidor_fora_do_ar() -> None:
    def _down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("conexão recusada")

    client = OllamaClient(transport=httpx.MockTransport(_down))

    assert await client.is_healthy() is False
    assert await client.version() is None
    with pytest.raises(OllamaUnavailableError):
        await client.list_installed()


async def test_resposta_http_de_erro() -> None:
    def _error(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    client = OllamaClient(transport=httpx.MockTransport(_error))
    with pytest.raises(OllamaUnavailableError):
        await client.list_installed()
