"""Fixtures compartilhadas — tudo roda offline, com SQLite em memória."""

from __future__ import annotations

import os

# Deve ocorrer antes de qualquer import de `app.*`: Settings é cacheado por processo.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("OLLAMA_BASE_URL", "http://ollama.test:11434")

# Os limites da Natureza são fixados aqui para que a suíte não dependa do `.env` da máquina:
# variáveis de ambiente têm precedência sobre o arquivo em pydantic-settings.
os.environ.setdefault("NATURE_RAM_LIMIT_MB", "16384")
os.environ.setdefault("NATURE_VRAM_LIMIT_MB", "4096")
os.environ.setdefault("NATURE_RESERVED_RAM_MB", "2048")
os.environ.setdefault("NATURE_RESERVED_VRAM_MB", "512")
os.environ.setdefault("NATURE_WARNING_THRESHOLD", "0.75")
os.environ.setdefault("NATURE_CRITICAL_THRESHOLD", "0.90")
os.environ.setdefault("NATURE_MAX_CONCURRENT_SUBAGENTS", "4")
os.environ.setdefault("NATURE_MAX_QUEUE_SIZE", "32")

os.environ.setdefault("REASONING_CAPTURE_ENABLED", "true")
os.environ.setdefault("REASONING_MAX_STEPS", "4")
os.environ.setdefault("REASONING_STREAM_BUFFER", "64")
os.environ.setdefault("REASONING_RETENTION_DAYS", "30")
os.environ.setdefault("REASONING_MAX_CONTENT_CHARS", "8000")

os.environ.setdefault("GAME_TICK_SECONDS", "0.1")
os.environ.setdefault("GAME_WALK_TILES_PER_SECOND", "3.0")

import json
from collections.abc import Iterator

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config.database import get_db_session
from app.config.settings import Settings, get_settings
from app.main import create_app
from app.models import Base
from app.routes.deps import get_ollama_client
from app.services.nature_manager import NatureManager, get_nature_manager
from app.services.office_map import get_office_map
from app.services.ollama_client import OllamaClient
from app.services.reasoning_broker import get_broker


@pytest.fixture
def settings() -> Settings:
    return get_settings()


@pytest.fixture
def db_session() -> Iterator[Session]:
    """Banco SQLite em memória, isolado por teste, com o schema completo."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def make_nature(
    *,
    ram_total: int = 16_384,
    ram_used: int = 4_000,
    vram_total: int = 4_096,
    vram_used: int = 500,
    cpu: float = 12.5,
    settings: Settings | None = None,
) -> NatureManager:
    """Natureza com sondas determinísticas (sem tocar no hardware real)."""
    return NatureManager(
        settings=settings or get_settings(),
        ram_probe=lambda: (ram_total, ram_used),
        vram_probe=lambda: (vram_total, vram_used),
        cpu_probe=lambda: cpu,
    )


@pytest.fixture
def nature() -> NatureManager:
    return make_nature()


def make_ollama(handler: httpx.MockTransport | None = None) -> OllamaClient:
    """Cliente Ollama com transporte simulado (nenhuma rede é tocada)."""
    if handler is None:

        def _default(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/version":
                return httpx.Response(200, json={"version": "0.12.11"})
            if request.url.path == "/api/tags":
                return httpx.Response(
                    200,
                    json={
                        "models": [
                            {
                                "name": "llama3.2:3b",
                                "size": 2_147_483_648,
                                "digest": "sha256:abc",
                                "details": {
                                    "parameter_size": "3.2B",
                                    "quantization_level": "Q4_K_M",
                                },
                            }
                        ]
                    },
                )
            return httpx.Response(404)

        handler = httpx.MockTransport(_default)
    return OllamaClient(transport=handler)


def stream_body(text: str, *, prompt_tokens: int = 12, completion_tokens: int = 34) -> bytes:
    """NDJSON equivalente ao que o Ollama devolve em `/api/generate?stream=true`."""
    lines = [json.dumps({"response": chunk, "done": False}) for chunk in text.splitlines(True)]
    lines.append(
        json.dumps(
            {
                "model": "llama3.2:3b",
                "response": "",
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": prompt_tokens,
                "eval_count": completion_tokens,
                "total_duration": 1_500_000_000,
            }
        )
    )
    return ("\n".join(lines)).encode()


def make_react_ollama(turns: list[str]) -> OllamaClient:
    """Cliente que devolve, em ordem, cada resposta ReAct roteirizada."""
    pending = list(turns)

    def _handler(request: httpx.Request) -> httpx.Response:
        if request.url.path != "/api/generate":
            return httpx.Response(404)
        text = pending.pop(0) if pending else "Conclusão: roteiro esgotado."
        return httpx.Response(200, content=stream_body(text))

    return OllamaClient(transport=httpx.MockTransport(_handler))


@pytest.fixture(autouse=True)
def _reset_broker() -> Iterator[None]:
    """Nenhum assinante nem lotação sobrevive de um teste para o outro."""
    get_broker().reset()
    get_office_map().reset()
    yield
    get_broker().reset()
    get_office_map().reset()


@pytest.fixture
def app(db_session: Session, nature: NatureManager) -> FastAPI:
    """App FastAPI com banco, Natureza e Ollama substituídos por dublês."""
    application = create_app()
    application.dependency_overrides[get_db_session] = lambda: db_session
    application.dependency_overrides[get_nature_manager] = lambda: nature
    application.dependency_overrides[get_ollama_client] = lambda: make_ollama()
    return application


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
