"""Planta do escritório virtual e posicionamento dos agentes no mapa 2D (Fase 4).

Nenhum modelo ORM tem coordenadas (ADR-010): a lotação vive em memória, por
processo, com a mesma disciplina do `reasoning_broker`. A atribuição de posto é
determinística — o mesmo quadro de pessoal sempre produz o mesmo mapa —, então
reiniciar o backend recoloca todo mundo no lugar canônico.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any, Literal

from app.models.agent import Agent
from app.models.enums import AgentRole, AgentType

#: Lado do tile, em pixels, usado pelo renderizador.
TILE_SIZE = 32
#: Dimensões do escritório, em tiles.
GRID_COLUMNS = 40
GRID_ROWS = 24

RoomKind = Literal["EXECUTIVE", "MEETING", "WORKSTATIONS", "BENCH", "SERVER"]
SeatKind = Literal["CHIEF", "MEETING", "WORKSTATION", "BENCH"]


@dataclass(frozen=True, slots=True)
class Room:
    """Cômodo retangular do escritório, em coordenadas de tile."""

    id: str
    label: str
    kind: RoomKind
    x: int
    y: int
    width: int
    height: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class Seat:
    """Posto de trabalho: uma mesa, uma cadeira de reunião ou um lugar no bench."""

    id: str
    kind: SeatKind
    room_id: str
    x: int
    y: int
    index: int
    role: AgentRole | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["role"] = self.role.value if self.role else None
        return data


ROOMS: tuple[Room, ...] = (
    Room(id="executive", label="Diretoria", kind="EXECUTIVE", x=1, y=1, width=14, height=10),
    Room(id="meeting", label="Sala de Reunião", kind="MEETING", x=16, y=1, width=12, height=8),
    Room(id="server", label="Sala dos Servidores", kind="SERVER", x=29, y=1, width=10, height=6),
    Room(
        id="floor",
        label="Estações de Trabalho",
        kind="WORKSTATIONS",
        x=1,
        y=12,
        width=27,
        height=11,
    ),
    Room(id="bench", label="Bench", kind="BENCH", x=29, y=8, width=10, height=15),
)

#: Cada Chief tem cadeira cativa — a diretoria nunca é remanejada.
CHIEF_SEATS: tuple[Seat, ...] = (
    Seat(id="desk-ceo", kind="CHIEF", room_id="executive", x=3, y=3, index=0, role=AgentRole.CEO),
    Seat(id="desk-cto", kind="CHIEF", room_id="executive", x=7, y=3, index=1, role=AgentRole.CTO),
    Seat(id="desk-cmo", kind="CHIEF", room_id="executive", x=11, y=3, index=2, role=AgentRole.CMO),
    Seat(id="desk-cfo", kind="CHIEF", room_id="executive", x=3, y=8, index=3, role=AgentRole.CFO),
    Seat(id="desk-ra", kind="CHIEF", room_id="executive", x=7, y=8, index=4, role=AgentRole.RA),
)

MEETING_SEATS: tuple[Seat, ...] = tuple(
    Seat(
        id=f"meeting-{index}",
        kind="MEETING",
        room_id="meeting",
        x=18 + (index % 3) * 3,
        y=3 + (index // 3) * 3,
        index=index,
    )
    for index in range(6)
)

WORKSTATION_SEATS: tuple[Seat, ...] = tuple(
    Seat(
        id=f"station-{index}",
        kind="WORKSTATION",
        room_id="floor",
        x=3 + (index % 6) * 4,
        y=15 + (index // 6) * 5,
        index=index,
    )
    for index in range(12)
)

BENCH_SEATS: tuple[Seat, ...] = tuple(
    Seat(
        id=f"bench-{index}",
        kind="BENCH",
        room_id="bench",
        x=31 + (index % 2) * 4,
        y=11 + (index // 2) * 3,
        index=index,
    )
    for index in range(8)
)

SEATS: tuple[Seat, ...] = CHIEF_SEATS + MEETING_SEATS + WORKSTATION_SEATS + BENCH_SEATS
_SEATS_BY_ID: dict[str, Seat] = {seat.id: seat for seat in SEATS}
_SEATS_BY_ROLE: dict[AgentRole, Seat] = {
    seat.role: seat for seat in CHIEF_SEATS if seat.role is not None
}

#: Pontos clicáveis que a UI usa para enquadrar a câmera.
HOTSPOTS: tuple[dict[str, Any], ...] = tuple(
    {
        "id": f"hotspot-{room.id}",
        "room_id": room.id,
        "label": room.label,
        "x": room.x + room.width / 2,
        "y": room.y + room.height / 2,
    }
    for room in ROOMS
)

#: O expediente simulado vai das 9h às 18h; 1 segundo real = 1 minuto corporativo.
WORKDAY_START_MINUTE = 9 * 60
WORKDAY_MINUTES = 9 * 60


@dataclass(slots=True)
class Placement:
    """Onde um agente está agora e para onde ele caminha."""

    agent_id: uuid.UUID
    seat_id: str | None
    x: float
    y: float
    target_x: float
    target_y: float
    manual: bool = field(default=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": str(self.agent_id),
            "seat_id": self.seat_id,
            "x": round(self.x, 3),
            "y": round(self.y, 3),
            "target_x": round(self.target_x, 3),
            "target_y": round(self.target_y, 3),
            "manual": self.manual,
        }


class OfficeMap:
    """Registro em memória da lotação do escritório."""

    def __init__(self) -> None:
        self._placements: dict[uuid.UUID, Placement] = {}
        self._lock = threading.Lock()

    def place_all(self, agents: Sequence[Agent]) -> dict[uuid.UUID, Placement]:
        """Recalcula a lotação do quadro inteiro e devolve o resultado."""
        assignments = _assign_seats(agents)
        with self._lock:
            live = {agent.id for agent in agents}
            for agent_id in list(self._placements):
                if agent_id not in live:
                    del self._placements[agent_id]

            for agent_id, seat in assignments.items():
                current = self._placements.get(agent_id)
                if current is None:
                    self._placements[agent_id] = Placement(
                        agent_id=agent_id,
                        seat_id=seat.id if seat else None,
                        x=seat.x if seat else GRID_COLUMNS / 2,
                        y=seat.y if seat else GRID_ROWS / 2,
                        target_x=seat.x if seat else GRID_COLUMNS / 2,
                        target_y=seat.y if seat else GRID_ROWS / 2,
                    )
                    continue
                current.seat_id = seat.id if seat else None
                if not current.manual and seat is not None:
                    current.target_x = float(seat.x)
                    current.target_y = float(seat.y)
            return {agent_id: _copy(p) for agent_id, p in self._placements.items()}

    def get(self, agent_id: uuid.UUID) -> Placement | None:
        with self._lock:
            placement = self._placements.get(agent_id)
            return _copy(placement) if placement else None

    def move(self, agent_id: uuid.UUID, x: float, y: float) -> Placement:
        """Move o agente para um tile arbitrário; o posto fixo deixa de valer."""
        clamped_x = _clamp(x, 0, GRID_COLUMNS - 1)
        clamped_y = _clamp(y, 0, GRID_ROWS - 1)
        with self._lock:
            placement = self._placements.get(agent_id)
            if placement is None:
                placement = Placement(
                    agent_id=agent_id,
                    seat_id=None,
                    x=clamped_x,
                    y=clamped_y,
                    target_x=clamped_x,
                    target_y=clamped_y,
                )
                self._placements[agent_id] = placement
            placement.target_x = clamped_x
            placement.target_y = clamped_y
            placement.x = clamped_x
            placement.y = clamped_y
            placement.manual = True
            return _copy(placement)

    def recall(self, agent_id: uuid.UUID) -> Placement | None:
        """Devolve o agente ao posto canônico, cancelando o movimento manual."""
        with self._lock:
            placement = self._placements.get(agent_id)
            if placement is None:
                return None
            placement.manual = False
            seat = _SEATS_BY_ID.get(placement.seat_id or "")
            if seat is not None:
                placement.target_x = float(seat.x)
                placement.target_y = float(seat.y)
                placement.x = float(seat.x)
                placement.y = float(seat.y)
            return _copy(placement)

    def reset(self) -> None:
        """Esvazia o escritório (usado entre testes)."""
        with self._lock:
            self._placements.clear()


def _copy(placement: Placement) -> Placement:
    return Placement(
        agent_id=placement.agent_id,
        seat_id=placement.seat_id,
        x=placement.x,
        y=placement.y,
        target_x=placement.target_x,
        target_y=placement.target_y,
        manual=placement.manual,
    )


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _assign_seats(agents: Iterable[Agent]) -> dict[uuid.UUID, Seat | None]:
    """Chief senta no posto do cargo; subagente ocupa a estação livre mais baixa."""
    assignments: dict[uuid.UUID, Seat | None] = {}
    subagents: list[Agent] = []
    for agent in agents:
        if agent.agent_type is AgentType.CHIEF:
            assignments[agent.id] = _SEATS_BY_ROLE.get(agent.role)
        else:
            subagents.append(agent)

    subagents.sort(key=lambda a: (a.created_at, str(a.id)))
    pool = [*WORKSTATION_SEATS, *BENCH_SEATS]
    for position, agent in enumerate(subagents):
        assignments[agent.id] = pool[position] if position < len(pool) else BENCH_SEATS[-1]
    return assignments


def layout_dict() -> dict[str, Any]:
    """Planta completa, pronta para o renderizador."""
    return {
        "tile_size": TILE_SIZE,
        "columns": GRID_COLUMNS,
        "rows": GRID_ROWS,
        "rooms": [room.to_dict() for room in ROOMS],
        "seats": [seat.to_dict() for seat in SEATS],
        "hotspots": [dict(hotspot) for hotspot in HOTSPOTS],
    }


def seat_by_id(seat_id: str) -> Seat | None:
    return _SEATS_BY_ID.get(seat_id)


def corporate_clock(started_at: datetime, now: datetime | None = None) -> dict[str, Any]:
    """Relógio corporativo simulado: 1 segundo real = 1 minuto de expediente."""
    now = now or datetime.now(UTC)
    elapsed = max((now - started_at).total_seconds(), 0.0)
    minutes = int(elapsed)
    day = minutes // WORKDAY_MINUTES + 1
    minute_of_day = WORKDAY_START_MINUTE + minutes % WORKDAY_MINUTES
    return {
        "day": day,
        "hour": minute_of_day // 60,
        "minute": minute_of_day % 60,
        "label": f"{minute_of_day // 60:02d}:{minute_of_day % 60:02d}",
        "elapsed_seconds": round(elapsed, 1),
    }


@lru_cache(maxsize=1)
def get_office_map() -> OfficeMap:
    """Instância única do escritório por processo."""
    return OfficeMap()
