"""Configuração central da aplicação, carregada de variáveis de ambiente / `.env`."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "production"]
LogFormat = Literal["console", "json"]


class Settings(BaseSettings):
    """Parâmetros de execução do backend TheyWork."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Aplicação -----------------------------------------------------------
    app_name: str = "TheyWork"
    app_env: Environment = "development"
    app_version: str = "0.1.0"
    # Bind amplo é seguro aqui: a porta só é publicada em 127.0.0.1 pelo compose.
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = ""

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: LogFormat = "console"

    # --- Persistência --------------------------------------------------------
    database_url: str = "postgresql+psycopg://theywork:theywork@postgres:5432/theywork"
    database_pool_size: int = 5
    database_max_overflow: int = 10
    database_echo: bool = False

    redis_url: str = "redis://redis:6379/0"

    # --- Ollama --------------------------------------------------------------
    ollama_base_url: str = "http://ollama:11434"
    ollama_timeout_seconds: float = 120.0

    # --- A Natureza (limites físicos do hardware alvo) -----------------------
    nature_ram_limit_mb: int = Field(default=16_384, gt=0)
    nature_vram_limit_mb: int = Field(default=4_096, gt=0)
    # Reserva para SO, IDE e demais containers; não disponível para agentes.
    nature_reserved_ram_mb: int = Field(default=2_048, ge=0)
    nature_reserved_vram_mb: int = Field(default=512, ge=0)
    nature_warning_threshold: float = Field(default=0.75, gt=0, le=1)
    nature_critical_threshold: float = Field(default=0.90, gt=0, le=1)
    nature_poll_interval_seconds: float = Field(default=5.0, gt=0)
    nature_max_concurrent_subagents: int = Field(default=4, gt=0)
    nature_max_queue_size: int = Field(default=32, gt=0)

    # --- Observabilidade cognitiva (Fase 3) ----------------------------------
    reasoning_capture_enabled: bool = True
    reasoning_max_steps: int = Field(default=8, gt=0)
    reasoning_stream_buffer: int = Field(default=256, gt=0)
    reasoning_retention_days: int = Field(default=30, gt=0)
    reasoning_max_content_chars: int = Field(default=8_000, gt=0)

    @field_validator("nature_critical_threshold")
    @classmethod
    def _critical_above_warning(cls, value: float, info: object) -> float:
        # `info.data` contém os campos já validados (ordem de declaração).
        data = getattr(info, "data", {}) or {}
        warning = data.get("nature_warning_threshold")
        if warning is not None and value <= warning:
            msg = "nature_critical_threshold deve ser maior que nature_warning_threshold"
            raise ValueError(msg)
        return value

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"

    @property
    def allocatable_ram_mb(self) -> int:
        """RAM que a Natureza permite destinar a agentes."""
        return max(self.nature_ram_limit_mb - self.nature_reserved_ram_mb, 0)

    @property
    def allocatable_vram_mb(self) -> int:
        """VRAM que a Natureza permite destinar a agentes."""
        return max(self.nature_vram_limit_mb - self.nature_reserved_vram_mb, 0)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retorna a instância única de `Settings` (cacheada por processo)."""
    return Settings()
