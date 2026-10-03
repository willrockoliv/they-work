"""Serialização do raciocínio em fluxograma e status ao vivo."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.models.enums import AgentStatus, ReasoningStatus
from app.services import reasoning_flow
from app.services.reasoning_tracer import ReasoningTracer
from tests.test_reasoning_tracer import make_agent


def trace_completo(db: Session, agent=None) -> ReasoningTracer:
    tracer = ReasoningTracer(db, task="Analisar retenção", agent=agent)
    tracer.start()
    tracer.on_thought("Preciso de dados.", tokens=12, duration_ms=40)
    tracer.on_action("memoria_corporativa", "retencao")
    tracer.on_observation("Nenhum registro.", tool="memoria_corporativa", duration_ms=3)
    tracer.on_thought("Vou concluir mesmo assim.", tokens=9)
    tracer.on_conclusion("Instrumentar o produto antes de decidir.")
    return tracer


class TestFluxograma:
    def test_nos_cobrem_tarefa_e_todos_os_passos(self, db_session: Session) -> None:
        tracer = trace_completo(db_session)
        tracer.complete("ok")

        flow = reasoning_flow.build_flow(tracer.session)

        tipos = [node["type"] for node in flow["nodes"]]
        assert tipos == [
            "TASK",
            "THOUGHT",
            "ACTION",
            "OBSERVATION",
            "THOUGHT",
            "CONCLUSION",
        ]

    def test_arestas_ligam_os_nos_em_sequencia(self, db_session: Session) -> None:
        tracer = trace_completo(db_session)
        tracer.complete("ok")

        flow = reasoning_flow.build_flow(tracer.session)

        assert len(flow["edges"]) == len(flow["nodes"]) - 1
        assert flow["edges"][0]["source"] == reasoning_flow.TASK_NODE_ID

    def test_retorno_observacao_pensamento_e_marcado_como_ciclo(
        self, db_session: Session
    ) -> None:
        tracer = trace_completo(db_session)
        tracer.complete("ok")

        flow = reasoning_flow.build_flow(tracer.session)

        loops = [edge for edge in flow["edges"] if edge["kind"] == "LOOP"]
        assert len(loops) == 1
        assert loops[0]["source"] == "step-3"
        assert loops[0]["target"] == "step-4"

    def test_layout_hints_posicionam_colunas_e_linhas(self, db_session: Session) -> None:
        tracer = trace_completo(db_session)
        tracer.complete("ok")

        flow = reasoning_flow.build_flow(tracer.session)
        por_id = {node["id"]: node for node in flow["nodes"]}

        assert por_id["step-1"]["column"] == 1
        assert por_id["step-2"]["column"] == 2
        assert por_id["step-3"]["column"] == 3
        assert por_id["step-4"]["row"] == 1
        assert flow["meta"]["rows"] == 2

    def test_metadados_por_no_trazem_tokens_e_duracao(self, db_session: Session) -> None:
        tracer = trace_completo(db_session)
        tracer.complete("ok")

        flow = reasoning_flow.build_flow(tracer.session)
        primeiro = flow["nodes"][1]

        assert primeiro["meta"]["tokens"] == 12
        assert primeiro["meta"]["duration_ms"] == 40
        assert primeiro["meta"]["timestamp"]

    def test_payload_da_acao_chega_ao_frontend(self, db_session: Session) -> None:
        tracer = trace_completo(db_session)
        tracer.complete("ok")

        flow = reasoning_flow.build_flow(tracer.session)
        acao = next(node for node in flow["nodes"] if node["type"] == "ACTION")

        assert acao["payload"]["tool"] == "memoria_corporativa"

    def test_fluxo_e_serializavel_em_json(self, db_session: Session) -> None:
        tracer = trace_completo(db_session)
        tracer.complete("ok")

        assert json.loads(json.dumps(reasoning_flow.build_flow(tracer.session)))

    def test_sessao_sem_passos_tem_apenas_o_no_da_tarefa(self, db_session: Session) -> None:
        tracer = ReasoningTracer(db_session, task="Tarefa vazia")
        tracer.start()

        flow = reasoning_flow.build_flow(tracer.session, [])

        assert len(flow["nodes"]) == 1
        assert flow["edges"] == []


class TestLiveStatus:
    def test_agente_sem_sessao(self, db_session: Session) -> None:
        agent = make_agent(db_session)

        status = reasoning_flow.build_live_status(agent, None, max_steps=4)

        assert status["session_id"] is None
        assert status["progress"] == 0.0

    def test_sessao_em_andamento_reporta_progresso_parcial(self, db_session: Session) -> None:
        agent = make_agent(db_session)
        agent.status = AgentStatus.WORKING
        tracer = trace_completo(db_session, agent)

        status = reasoning_flow.build_live_status(agent, tracer.session, max_steps=10)

        assert status["reasoning_status"] == ReasoningStatus.RUNNING.value
        assert 0 < status["progress"] < 1
        assert status["last_step_type"] == "CONCLUSION"
        assert status["last_action"] == "memoria_corporativa(retencao)"
        assert status["elapsed_ms"] >= 0

    def test_sessao_encerrada_reporta_progresso_total(self, db_session: Session) -> None:
        agent = make_agent(db_session)
        tracer = trace_completo(db_session, agent)
        tracer.complete("Instrumentar o produto antes de decidir.")

        status = reasoning_flow.build_live_status(agent, tracer.session, max_steps=10)

        assert status["progress"] == 1.0
        assert status["conclusion"] == "Instrumentar o produto antes de decidir."
