"""Barramento de eventos cognitivos — publica passos ReAct para assinantes WebSocket.

Pub/sub em memória, suficiente enquanto o backend roda num único worker (ADR-006).
`publish` é seguro para ser chamado de threads do pool do FastAPI: cada assinante
guarda o event loop em que foi criado e recebe o evento via `call_soon_threadsafe`.
"""

from __future__ import annotations

import asyncio
import contextlib
import itertools
import threading
import uuid
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from app.config.logging import get_logger
from app.config.settings import get_settings

logger = get_logger(__name__)

#: Canal que recebe os eventos de todos os agentes.
GLOBAL_CHANNEL = "*"


@dataclass(slots=True)
class Subscription:
    """Fila de um assinante, atrelada ao event loop que a criou."""

    id: int
    channel: str
    queue: asyncio.Queue[dict[str, Any]]
    loop: asyncio.AbstractEventLoop
    dropped: int = field(default=0)

    async def next_event(self) -> dict[str, Any]:
        return await self.queue.get()


class ReasoningBroker:
    """Distribui eventos de raciocínio por canal (um por agente + canal global)."""

    def __init__(self, buffer_size: int = 256) -> None:
        self._buffer_size = buffer_size
        self._subscribers: dict[int, Subscription] = {}
        self._lock = threading.Lock()
        self._ids = itertools.count(1)

    @property
    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscribers)

    def subscribe(self, agent_id: uuid.UUID | None = None) -> Subscription:
        """Registra um assinante. `agent_id=None` assina o canal global."""
        subscription = Subscription(
            id=next(self._ids),
            channel=GLOBAL_CHANNEL if agent_id is None else str(agent_id),
            queue=asyncio.Queue(maxsize=self._buffer_size),
            loop=asyncio.get_running_loop(),
        )
        with self._lock:
            self._subscribers[subscription.id] = subscription
        return subscription

    def unsubscribe(self, subscription: Subscription) -> None:
        with self._lock:
            self._subscribers.pop(subscription.id, None)

    def publish(self, event: dict[str, Any], *, agent_id: uuid.UUID | None = None) -> int:
        """Entrega o evento ao canal do agente e ao canal global. Nunca bloqueia."""
        channel = GLOBAL_CHANNEL if agent_id is None else str(agent_id)
        with self._lock:
            targets = [
                sub
                for sub in self._subscribers.values()
                if sub.channel == GLOBAL_CHANNEL or sub.channel == channel
            ]
        for subscription in targets:
            subscription.loop.call_soon_threadsafe(self._offer, subscription, event)
        return len(targets)

    @staticmethod
    def _offer(subscription: Subscription, event: dict[str, Any]) -> None:
        """Backpressure: assinante lento perde o evento mais antigo, não o mais novo."""
        if subscription.queue.full():
            with contextlib.suppress(asyncio.QueueEmpty):
                subscription.queue.get_nowait()
            subscription.dropped += 1
        subscription.queue.put_nowait(event)

    def reset(self) -> None:
        """Descarta todos os assinantes (usado entre testes)."""
        with self._lock:
            self._subscribers.clear()


@lru_cache(maxsize=1)
def get_broker() -> ReasoningBroker:
    """Instância única do barramento por processo."""
    return ReasoningBroker(buffer_size=get_settings().reasoning_stream_buffer)
