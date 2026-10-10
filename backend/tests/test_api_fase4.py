"""API do mundo 2D: planta, estado do jogo, movimentação e canal `/ws/game-state`."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import AgentRole, ReasoningStatus
from app.services import agent_service, office_map
from app.services.reasoning_tracer import ReasoningTracer
from tests.test_office_map import make_subagent
from tests.test_reasoning_tracer import make_agent


class TestPlantaHttp:
    def test_map_devolve_comodos_postos_e_hotspots(self, client: TestClient) -> None:
        corpo = client.get("/game/map").json()
        assert corpo["tile_size"] == office_map.TILE_SIZE
        assert {room["id"] for room in corpo["rooms"]} == {
            "executive",
            "meeting",
            "server",
            "floor",
        }
        assert len(corpo["seats"]) == len(office_map.SEATS)
        assert len(corpo["hotspots"]) == len(office_map.ROOMS)


class TestEstadoDoJogo:
    def test_estado_vazio_ainda_traz_planta_relogio_e_recursos(self, client: TestClient) -> None:
        corpo = client.get("/game/state").json()
        assert corpo["agents"] == []
        assert corpo["clock"]["hour"] >= 9
        assert corpo["resources"]["status"] in {"HEALTHY", "WARNING", "CRITICAL"}
        assert corpo["economy"] == {
            "sessions": 0,
            "delivered": 0,
            "total_tokens": 0,
            "cost_mb_s": 0.0,
            "revenue_tokens": 0,
            "roi": 0.0,
        }
        assert corpo["layout"]["columns"] == office_map.GRID_COLUMNS

    def test_chiefs_aparecem_lotados_na_diretoria(
        self, client: TestClient, db_session: Session
    ) -> None:
        agent_service.init_chiefs(db_session)
        db_session.commit()

        corpo = client.get("/game/state").json()
        por_papel = {agente["role"]: agente for agente in corpo["agents"]}
        assert len(corpo["agents"]) == 5
        assert por_papel["CEO"]["seat_id"] == "desk-ceo"
        assert por_papel["CEO"]["room_id"] == "executive"
        assert por_papel["CEO"]["activity"] == "IDLE"
        assert por_papel["CEO"]["position"]["x"] == 3

    def test_agente_em_raciocinio_aparece_como_pensando(
        self, client: TestClient, db_session: Session
    ) -> None:
        agente = make_agent(db_session)
        tracer = ReasoningTracer(db_session, task="Analisar churn", agent=agente)
        tracer.start()
        tracer.on_thought("Preciso dos dados.")
        db_session.commit()

        corpo = client.get("/game/state").json()
        entrada = corpo["agents"][0]
        assert entrada["activity"] == "THINKING"
        assert entrada["reasoning"]["status"] == ReasoningStatus.RUNNING.value
        assert entrada["reasoning"]["task"] == "Analisar churn"
        assert 0.0 < entrada["reasoning"]["progress"] <= 1.0

    def test_economia_contabiliza_sessao_concluida(
        self, client: TestClient, db_session: Session
    ) -> None:
        agente = make_agent(db_session)
        tracer = ReasoningTracer(db_session, task="Analisar churn", agent=agente)
        tracer.start()
        tracer.on_thought("Pronto.")
        tracer.complete(conclusion="Reter clientes premium.")
        db_session.commit()

        economia = client.get("/game/state").json()["economy"]
        assert economia["sessions"] == 1
        assert economia["delivered"] == 1


class TestMovimentacaoHttp:
    def test_position_devolve_o_posto_do_agente(
        self, client: TestClient, db_session: Session
    ) -> None:
        chiefs = agent_service.init_chiefs(db_session)
        db_session.commit()
        ceo = next(c for c in chiefs if c.role is AgentRole.CEO)

        corpo = client.get(f"/agents/{ceo.id}/position").json()
        assert corpo["seat_id"] == "desk-ceo"
        assert corpo["manual"] is False

    def test_move_leva_o_agente_para_o_tile_pedido(
        self, client: TestClient, db_session: Session
    ) -> None:
        agente = make_subagent(db_session, "Analista", minutes=1)
        db_session.commit()

        resposta = client.post(f"/agents/{agente.id}/move", json={"x": 20, "y": 5})
        corpo = resposta.json()
        assert resposta.status_code == 200
        assert (corpo["x"], corpo["y"]) == (20, 5)
        assert corpo["manual"] is True

    def test_recall_devolve_ao_posto(self, client: TestClient, db_session: Session) -> None:
        agente = make_subagent(db_session, "Analista", minutes=1)
        db_session.commit()
        client.post(f"/agents/{agente.id}/move", json={"x": 20, "y": 5})

        corpo = client.post(f"/agents/{agente.id}/recall").json()
        assert corpo["manual"] is False
        assert corpo["seat_id"] == "station-0"

    def test_destino_fora_do_grid_e_rejeitado(
        self, client: TestClient, db_session: Session
    ) -> None:
        agente = make_subagent(db_session, "Analista", minutes=1)
        db_session.commit()
        resposta = client.post(f"/agents/{agente.id}/move", json={"x": 999, "y": 0})
        assert resposta.status_code == 422

    def test_coordenada_negativa_e_rejeitada_pelo_schema(
        self, client: TestClient, db_session: Session
    ) -> None:
        agente = make_subagent(db_session, "Analista", minutes=1)
        db_session.commit()
        assert client.post(f"/agents/{agente.id}/move", json={"x": -1, "y": 0}).status_code == 422

    def test_agente_inexistente_devolve_404(self, client: TestClient) -> None:
        inexistente = "00000000-0000-0000-0000-000000000001"
        assert client.get(f"/agents/{inexistente}/position").status_code == 404


class TestCanalDoMundo:
    def test_snapshot_chega_antes_de_qualquer_evento(
        self, client: TestClient, db_session: Session
    ) -> None:
        agent_service.init_chiefs(db_session)
        db_session.commit()

        with client.websocket_connect("/ws/game-state") as ws:
            mensagem = ws.receive_json()

        assert mensagem["event"] == "game.snapshot"
        assert len(mensagem["data"]["agents"]) == 5
        assert mensagem["data"]["layout"]["tile_size"] == office_map.TILE_SIZE

    def test_tick_publica_relogio_recursos_e_economia(self, client: TestClient) -> None:
        with client.websocket_connect("/ws/game-state") as ws:
            ws.receive_json()
            tick = ws.receive_json()

        assert tick["event"] == "game.tick"
        assert set(tick["data"]) == {"clock", "resources", "economy"}

    def test_contratacao_vira_evento_agent_joined(
        self, client: TestClient, db_session: Session
    ) -> None:
        with client.websocket_connect("/ws/game-state") as ws:
            ws.receive_json()
            ws.receive_json()

            make_subagent(db_session, "Analista", minutes=1)
            db_session.commit()

            eventos = [ws.receive_json() for _ in range(2)]

        nomes = [evento["event"] for evento in eventos]
        assert "agent.joined" in nomes
        joined = eventos[nomes.index("agent.joined")]
        assert joined["data"]["name"] == "Analista"
        assert joined["data"]["seat_id"] == "station-0"

    def test_movimento_chega_ao_canal_do_mundo(
        self, client: TestClient, db_session: Session
    ) -> None:
        agente = make_subagent(db_session, "Analista", minutes=1)
        db_session.commit()

        with client.websocket_connect("/ws/game-state") as ws:
            ws.receive_json()
            client.post(f"/agents/{agente.id}/move", json={"x": 20, "y": 5})
            evento = ws.receive_json()
            while evento["event"] != "agent.moved":
                evento = ws.receive_json()

        assert evento["data"]["x"] == 20
        assert evento["data"]["manual"] is True
