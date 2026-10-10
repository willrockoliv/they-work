"""Planta do escritório e lotação determinística dos agentes (Fase 4)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.enums import AgentRole, AgentStatus, AgentType
from app.services import agent_service, office_map


def make_subagent(db: Session, name: str, *, minutes: int) -> Agent:
    agent = Agent(
        name=name,
        role=AgentRole.SUBAGENT,
        agent_type=AgentType.SUBAGENT,
        status=AgentStatus.IDLE,
        job_title=name,
        system_prompt="",
        model_name="llama3.2:3b",
        estimated_ram_mb=3_000,
        attributes={},
        created_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=minutes),
    )
    db.add(agent)
    db.flush()
    return agent


class TestPlanta:
    def test_comodos_cabem_dentro_do_grid(self) -> None:
        for room in office_map.ROOMS:
            assert room.x >= 0 and room.y >= 0
            assert room.x + room.width <= office_map.GRID_COLUMNS
            assert room.y + room.height <= office_map.GRID_ROWS

    def test_cada_posto_fica_dentro_do_proprio_comodo(self) -> None:
        rooms = {room.id: room for room in office_map.ROOMS}
        for seat in office_map.SEATS:
            room = rooms[seat.room_id]
            assert room.x <= seat.x < room.x + room.width
            assert room.y <= seat.y < room.y + room.height

    def test_nao_existem_postos_duplicados(self) -> None:
        ids = [seat.id for seat in office_map.SEATS]
        coords = [(seat.x, seat.y) for seat in office_map.SEATS]
        assert len(ids) == len(set(ids))
        assert len(coords) == len(set(coords))

    def test_todo_chief_tem_cadeira_cativa(self) -> None:
        papeis = {seat.role for seat in office_map.CHIEF_SEATS}
        assert papeis == {
            AgentRole.CEO,
            AgentRole.CTO,
            AgentRole.CMO,
            AgentRole.CFO,
            AgentRole.RA,
        }

    def test_layout_serializado_tem_o_contrato_esperado(self) -> None:
        layout = office_map.layout_dict()
        assert layout["tile_size"] == office_map.TILE_SIZE
        assert layout["columns"] == office_map.GRID_COLUMNS
        assert len(layout["rooms"]) == len(office_map.ROOMS)
        assert len(layout["seats"]) == len(office_map.SEATS)
        assert len(layout["hotspots"]) == len(office_map.ROOMS)
        assert layout["seats"][0]["role"] == "CEO"


class TestLotacao:
    def test_chief_senta_sempre_na_mesa_do_cargo(self, db_session: Session) -> None:
        chiefs = agent_service.init_chiefs(db_session)
        lotacao = office_map.get_office_map().place_all(chiefs)
        por_papel = {chief.role: lotacao[chief.id].seat_id for chief in chiefs}
        assert por_papel[AgentRole.CEO] == "desk-ceo"
        assert por_papel[AgentRole.RA] == "desk-ra"

    def test_subagentes_ocupam_estacoes_em_ordem_de_contratacao(
        self, db_session: Session
    ) -> None:
        primeiro = make_subagent(db_session, "Analista", minutes=10)
        segundo = make_subagent(db_session, "Redator", minutes=20)
        lotacao = office_map.get_office_map().place_all([segundo, primeiro])
        assert lotacao[primeiro.id].seat_id == "station-0"
        assert lotacao[segundo.id].seat_id == "station-1"

    def test_lotacao_e_estavel_entre_chamadas(self, db_session: Session) -> None:
        agentes = [make_subagent(db_session, f"Agente {i}", minutes=i) for i in range(5)]
        mapa = office_map.get_office_map()
        primeira = {a.id: mapa.place_all(agentes)[a.id].seat_id for a in agentes}
        segunda = {a.id: mapa.place_all(agentes)[a.id].seat_id for a in agentes}
        assert primeira == segunda

    def test_excedente_de_subagentes_divide_as_estacoes(self, db_session: Session) -> None:
        total = len(office_map.WORKSTATION_SEATS) + 1
        agentes = [make_subagent(db_session, f"Agente {i}", minutes=i) for i in range(total)]
        lotacao = office_map.get_office_map().place_all(agentes)
        assert lotacao[agentes[-1].id].seat_id == "station-0"

    def test_agente_que_sai_perde_a_lotacao(self, db_session: Session) -> None:
        a = make_subagent(db_session, "Analista", minutes=1)
        b = make_subagent(db_session, "Redator", minutes=2)
        mapa = office_map.get_office_map()
        mapa.place_all([a, b])
        restante = mapa.place_all([a])
        assert b.id not in restante
        assert mapa.get(b.id) is None


class TestMovimento:
    def test_move_sobrepoe_o_posto_fixo(self, db_session: Session) -> None:
        agente = make_subagent(db_session, "Analista", minutes=1)
        mapa = office_map.get_office_map()
        mapa.place_all([agente])
        destino = mapa.move(agente.id, 20, 5)
        assert (destino.x, destino.y) == (20, 5)
        assert destino.manual is True

        # Recalcular a lotação não arrasta de volta quem foi movido à mão.
        mapa.place_all([agente])
        assert mapa.get(agente.id).x == 20  # type: ignore[union-attr]

    def test_recall_devolve_o_agente_ao_posto(self, db_session: Session) -> None:
        agente = make_subagent(db_session, "Analista", minutes=1)
        mapa = office_map.get_office_map()
        mapa.place_all([agente])
        mapa.move(agente.id, 20, 5)
        voltou = mapa.recall(agente.id)
        assert voltou is not None
        assert voltou.manual is False
        assert (voltou.x, voltou.y) == (
            office_map.WORKSTATION_SEATS[0].x,
            office_map.WORKSTATION_SEATS[0].y,
        )

    def test_destino_e_limitado_ao_grid(self, db_session: Session) -> None:
        agente = make_subagent(db_session, "Analista", minutes=1)
        mapa = office_map.get_office_map()
        mapa.place_all([agente])
        destino = mapa.move(agente.id, 999, -5)
        assert destino.x == office_map.GRID_COLUMNS - 1
        assert destino.y == 0


class TestRelogioCorporativo:
    def test_expediente_comeca_as_nove(self) -> None:
        inicio = datetime(2026, 1, 1, tzinfo=UTC)
        assert office_map.corporate_clock(inicio, inicio)["label"] == "09:00"

    def test_um_segundo_real_vale_um_minuto_de_expediente(self) -> None:
        inicio = datetime(2026, 1, 1, tzinfo=UTC)
        agora = inicio + timedelta(seconds=90)
        relogio = office_map.corporate_clock(inicio, agora)
        assert relogio["label"] == "10:30"
        assert relogio["day"] == 1

    def test_expediente_vira_o_dia_apos_nove_horas_simuladas(self) -> None:
        inicio = datetime(2026, 1, 1, tzinfo=UTC)
        agora = inicio + timedelta(seconds=office_map.WORKDAY_MINUTES)
        relogio = office_map.corporate_clock(inicio, agora)
        assert relogio["day"] == 2
        assert relogio["label"] == "09:00"


class TestReuniao:
    @staticmethod
    def _alvo(mapa: office_map.OfficeMap, agent_id: uuid.UUID) -> tuple[float, float]:
        placement = mapa.get(agent_id)
        assert placement is not None
        return (placement.target_x, placement.target_y)

    @staticmethod
    def _coords(seat: office_map.Seat) -> tuple[float, float]:
        return (float(seat.x), float(seat.y))

    def test_participantes_vao_para_cadeiras_de_reuniao_distintas(
        self, db_session: Session
    ) -> None:
        a = make_subagent(db_session, "Analista", minutes=1)
        b = make_subagent(db_session, "Redator", minutes=2)
        mapa = office_map.get_office_map()
        mapa.place_all([a, b], now=0.0)
        mapa.send_to_meeting([a.id, b.id], now=0.0)
        assert self._alvo(mapa, a.id) == self._coords(office_map.MEETING_SEATS[0])
        assert self._alvo(mapa, b.id) == self._coords(office_map.MEETING_SEATS[1])

    def test_recalculo_nao_desfaz_a_reuniao(self, db_session: Session) -> None:
        a = make_subagent(db_session, "Analista", minutes=1)
        mapa = office_map.get_office_map()
        mapa.place_all([a], now=0.0)
        mapa.send_to_meeting([a.id], now=0.0, hold_seconds=10.0)
        mapa.place_all([a], now=5.0)
        assert self._alvo(mapa, a.id) == self._coords(office_map.MEETING_SEATS[0])

    def test_ao_fim_do_prazo_o_agente_volta_ao_posto(self, db_session: Session) -> None:
        a = make_subagent(db_session, "Analista", minutes=1)
        mapa = office_map.get_office_map()
        mapa.place_all([a], now=0.0)
        mapa.send_to_meeting([a.id], now=0.0, hold_seconds=10.0)
        mapa.place_all([a], now=9.9)
        assert self._alvo(mapa, a.id) == self._coords(office_map.MEETING_SEATS[0])

        mapa.place_all([a], now=10.0)
        assert self._alvo(mapa, a.id) == self._coords(office_map.WORKSTATION_SEATS[0])

    def test_novo_report_renova_o_prazo_sem_trocar_de_cadeira(
        self, db_session: Session
    ) -> None:
        a = make_subagent(db_session, "Analista", minutes=1)
        mapa = office_map.get_office_map()
        mapa.place_all([a], now=0.0)
        mapa.send_to_meeting([a.id], now=0.0, hold_seconds=10.0)
        mapa.send_to_meeting([a.id], now=8.0, hold_seconds=10.0)

        mapa.place_all([a], now=12.0)
        assert self._alvo(mapa, a.id) == self._coords(office_map.MEETING_SEATS[0])

        mapa.place_all([a], now=18.0)
        assert self._alvo(mapa, a.id) == self._coords(office_map.WORKSTATION_SEATS[0])

    def test_mover_a_mao_cancela_a_reuniao(self, db_session: Session) -> None:
        a = make_subagent(db_session, "Analista", minutes=1)
        mapa = office_map.get_office_map()
        mapa.place_all([a], now=0.0)
        mapa.send_to_meeting([a.id], now=0.0)
        mapa.move(a.id, 20, 5)
        mapa.place_all([a], now=1.0)
        assert self._alvo(mapa, a.id) == (20.0, 5.0)

    def test_sala_cheia_nao_recusa_a_reuniao(self, db_session: Session) -> None:
        total = len(office_map.MEETING_SEATS) + 1
        agentes = [make_subagent(db_session, f"Agente {i}", minutes=i) for i in range(total)]
        mapa = office_map.get_office_map()
        mapa.place_all(agentes, now=0.0)
        enviados = mapa.send_to_meeting([a.id for a in agentes], now=0.0)
        assert len(enviados) == total
