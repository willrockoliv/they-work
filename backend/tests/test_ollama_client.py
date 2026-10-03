"""Cliente Ollama — parsing de respostas e tolerância a indisponibilidade."""

from __future__ import annotations

import httpx
import pytest

from app.services.ollama_client import OllamaClient, OllamaUnavailableError
from tests.conftest import make_ollama, stream_body


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


async def test_generate_agrega_tokens_do_streaming() -> None:
    capturados: list[str] = []
    client = OllamaClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=stream_body("Pensamento: ok"))
        )
    )

    completion = await client.generate(
        model="llama3.2:3b", prompt="oi", system="persona", on_token=capturados.append
    )

    assert completion.text == "Pensamento: ok"
    assert capturados == ["Pensamento: ok"]
    assert completion.prompt_tokens == 12
    assert completion.completion_tokens == 34
    assert completion.total_tokens == 46
    assert completion.duration_ms == 1_500
    assert completion.to_dict()["done_reason"] == "stop"


async def test_generate_propaga_indisponibilidade() -> None:
    def _down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("conexão recusada")

    client = OllamaClient(transport=httpx.MockTransport(_down))

    with pytest.raises(OllamaUnavailableError):
        await client.generate(model="llama3.2:3b", prompt="oi")
