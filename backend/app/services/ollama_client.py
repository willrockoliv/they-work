"""Cliente HTTP assíncrono para o servidor Ollama local."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

from app.config.logging import get_logger
from app.config.settings import Settings, get_settings

logger = get_logger(__name__)

#: Invocado a cada fragmento de texto recebido do modelo.
TokenCallback = Callable[[str], None]


@dataclass(frozen=True, slots=True)
class InstalledModel:
    """Modelo efetivamente presente no repositório local do Ollama."""

    name: str
    size_mb: int
    digest: str
    parameter_size: str | None
    quantization: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "size_mb": self.size_mb,
            "digest": self.digest,
            "parameter_size": self.parameter_size,
            "quantization": self.quantization,
        }


class OllamaUnavailableError(RuntimeError):
    """O servidor Ollama não respondeu dentro do tempo esperado."""


@dataclass(frozen=True, slots=True)
class OllamaCompletion:
    """Resultado de uma geração, com a contabilidade de tokens do próprio Ollama."""

    model: str
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    duration_ms: int = 0
    done_reason: str | None = None

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "text": self.text,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "duration_ms": self.duration_ms,
            "done_reason": self.done_reason,
        }


class OllamaClient:
    """Wrapper fino sobre a API REST do Ollama."""

    def __init__(
        self,
        settings: Settings | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._settings.ollama_base_url,
            timeout=self._settings.ollama_timeout_seconds,
            transport=self._transport,
        )

    async def is_healthy(self) -> bool:
        """Verifica se o servidor Ollama está acessível."""
        try:
            async with self._client() as client:
                response = await client.get("/api/version", timeout=5.0)
                response.raise_for_status()
        except (httpx.HTTPError, OSError) as exc:
            logger.warning("ollama.health_check_failed", error=str(exc))
            return False
        return True

    async def version(self) -> str | None:
        """Versão reportada pelo servidor Ollama, ou `None` se indisponível."""
        try:
            async with self._client() as client:
                response = await client.get("/api/version", timeout=5.0)
                response.raise_for_status()
                payload: dict[str, Any] = response.json()
        except (httpx.HTTPError, OSError, ValueError) as exc:
            logger.warning("ollama.version_failed", error=str(exc))
            return None
        version = payload.get("version")
        return str(version) if version is not None else None

    async def list_installed(self) -> list[InstalledModel]:
        """Lista os modelos baixados no volume do Ollama."""
        try:
            async with self._client() as client:
                response = await client.get("/api/tags")
                response.raise_for_status()
                payload: dict[str, Any] = response.json()
        except (httpx.HTTPError, OSError, ValueError) as exc:
            raise OllamaUnavailableError(str(exc)) from exc

        models: list[InstalledModel] = []
        for item in payload.get("models", []):
            details = item.get("details") or {}
            models.append(
                InstalledModel(
                    name=str(item.get("name", "")),
                    size_mb=int(item.get("size", 0)) // (1024 * 1024),
                    digest=str(item.get("digest", "")),
                    parameter_size=details.get("parameter_size"),
                    quantization=details.get("quantization_level"),
                )
            )
        return models

    async def generate(
        self,
        *,
        model: str,
        prompt: str,
        system: str | None = None,
        options: dict[str, Any] | None = None,
        on_token: TokenCallback | None = None,
    ) -> OllamaCompletion:
        """Gera texto em streaming, repassando cada fragmento a `on_token`.

        O streaming é o que torna o pensamento do agente observável: o chamador
        recebe os tokens brutos enquanto o modelo ainda está escrevendo.
        """
        body: dict[str, Any] = {"model": model, "prompt": prompt, "stream": True}
        if system:
            body["system"] = system
        if options:
            body["options"] = options

        chunks: list[str] = []
        final: dict[str, Any] = {}
        try:
            async with (
                self._client() as client,
                client.stream("POST", "/api/generate", json=body) as response,
            ):
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    event = json.loads(line)
                    fragment = str(event.get("response", ""))
                    if fragment:
                        chunks.append(fragment)
                        if on_token is not None:
                            on_token(fragment)
                    if event.get("done"):
                        final = event
        except (httpx.HTTPError, OSError, ValueError) as exc:
            logger.warning("ollama.generate_failed", model=model, error=str(exc))
            raise OllamaUnavailableError(str(exc)) from exc

        return OllamaCompletion(
            model=str(final.get("model", model)),
            text="".join(chunks),
            prompt_tokens=int(final.get("prompt_eval_count", 0)),
            completion_tokens=int(final.get("eval_count", 0)),
            duration_ms=int(final.get("total_duration", 0)) // 1_000_000,
            done_reason=final.get("done_reason"),
        )
