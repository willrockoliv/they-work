"""Cliente HTTP assíncrono para o servidor Ollama local."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.config.logging import get_logger
from app.config.settings import Settings, get_settings

logger = get_logger(__name__)


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
