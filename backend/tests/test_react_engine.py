"""Motor ReAct: parser, loop, ferramentas e fallback offline."""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy.orm import Session

from app.models.enums import (
    AgentStatus,
    AuditEventType,
    MemoryType,
    ReasoningStatus,
    ReasoningStepType,
    TaskComplexity,
)
from app.models.memory import CorporateMemory
from app.services import audit_service, react_engine, reasoning_tools, talent_bank
from app.services.nature_manager import NatureManager
from app.services.ollama_client import OllamaClient
from app.services.react_engine import TaskRequest, parse_turn
from app.services.reasoning_tools import ToolContext
from tests.conftest import make_react_ollama
from tests.test_reasoning_tracer import make_agent


class TestParser:
    def test_extrai_pensamento_acao_e_entrada(self) -> None:
        turno = parse_turn(
            "Pensamento: preciso do histórico\n"
            "Ação: memoria_corporativa\n"
            "Entrada da Ação: retenção de clientes"
        )

        assert turno.thought == "preciso do histórico"
        assert turno.tool == "memoria_corporativa"
        assert turno.tool_input == "retenção de clientes"
        assert not turno.is_final

    def test_conclusao_encerra_o_turno(self) -> None:
        turno = parse_turn("Pensamento: já sei\nConclusão: lançar em março")

        assert turno.is_final
        assert turno.conclusion == "lançar em março"
        assert turno.tool is None

    def test_tolera_acentuacao_negrito_e_sinonimos(self) -> None:
        turno = parse_turn("**Raciocinio**: ok\n**Ferramenta**: calculadora\nEntrada: 2+2")

        assert turno.thought == "ok"
        assert turno.tool == "calculadora"
        assert turno.tool_input == "2+2"

    def test_resposta_final_e_tratada_como_conclusao(self) -> None:
        assert parse_turn("Resposta Final: feito").conclusion == "feito"

    def test_texto_multilinha_e_preservado(self) -> None:
        turno = parse_turn("Pensamento: linha um\nlinha dois\nConclusão: fim")

        assert turno.thought == "linha um\nlinha dois"

    def test_texto_sem_rotulos_devolve_turno_vazio(self) -> None:
        turno = parse_turn("o modelo divagou sem seguir o formato")

        assert turno.thought == ""
        assert turno.conclusion is None


class TestFerramentas:
    def test_memoria_corporativa_registra_termos_e_resultados(self, db_session: Session) -> None:
        db_session.add(
            CorporateMemory(
                memory_type=MemoryType.REPORT,
                title="Retenção trimestral",
                content="A retenção caiu 8% no trimestre.",
                author_role="SUBAGENT",
                importance=7,
                tags={},
            )
        )
        db_session.flush()

        resultado = reasoning_tools.TOOLS["memoria_corporativa"].run(
            ToolContext(db=db_session), "retencao trimestral"
        )

        assert resultado.payload["search_terms"] == ["retencao", "trimestral"]
        assert resultado.payload["results"][0]["title"] == "Retenção trimestral"

    def test_memoria_vazia_devolve_observacao_explicita(self, db_session: Session) -> None:
        resultado = reasoning_tools.TOOLS["memoria_corporativa"].run(
            ToolContext(db=db_session), "qualquer coisa"
        )

        assert "Nenhum registro" in resultado.output

    def test_infraestrutura_usa_a_natureza(
        self, db_session: Session, nature: NatureManager
    ) -> None:
        resultado = reasoning_tools.TOOLS["infraestrutura"].run(
            ToolContext(db=db_session, nature=nature), "quanta RAM sobra?"
        )

        assert resultado.payload["snapshot"]["ram_limit_mb"] == 16_384

    def test_infraestrutura_sem_natureza_reporta_erro(self, db_session: Session) -> None:
        resultado = reasoning_tools.TOOLS["infraestrutura"].run(ToolContext(db=db_session), "")

        assert resultado.error == "nature_unavailable"

    def test_calculadora_avalia_sem_eval(self, db_session: Session) -> None:
        resultado = reasoning_tools.TOOLS["calculadora"].run(
            ToolContext(db=db_session), "(120 * 3) / 4"
        )

        assert resultado.payload["result"] == 90.0

    def test_calculadora_recusa_codigo_arbitrario(self, db_session: Session) -> None:
        resultado = reasoning_tools.TOOLS["calculadora"].run(
            ToolContext(db=db_session), "__import__('os').system('ls')"
        )

        assert resultado.error is not None

    def test_lookup_tolera_acento_e_caixa(self) -> None:
        assert reasoning_tools.get_tool("Memória Corporativa") is reasoning_tools.TOOLS[
            "memoria_corporativa"
        ]
        assert reasoning_tools.get_tool("inexistente") is None

    def test_banco_de_talentos_sem_correspondencia(self, db_session: Session) -> None:
        resultado = reasoning_tools.TOOLS["banco_de_talentos"].run(
            ToolContext(db=db_session), "Astronauta"
        )

        assert resultado.payload["matched"] is False

    def test_banco_de_talentos_encontra_perfil(self, db_session: Session) -> None:
        talent_bank.create_profile(
            db_session,
            role_title="Analista de Dados",
            specialization="métricas de produto",
            system_prompt="Você analisa métricas.",
            complexity=TaskComplexity.MODERATE,
            tools=["planilha"],
            recommended_model="llama3.2:3b",
        )

        resultado = reasoning_tools.TOOLS["banco_de_talentos"].run(
            ToolContext(db=db_session), "Analista de Dados"
        )

        assert resultado.payload["matched"] is True
        assert "Analista de Dados" in resultado.output

    def test_auditoria_vazia_e_com_eventos(self, db_session: Session) -> None:
        ctx = ToolContext(db=db_session)
        assert "vazia" in reasoning_tools.TOOLS["auditoria"].run(ctx, "tudo").output

        audit_service.record_event(
            db_session,
            event_type=AuditEventType.SYSTEM,
            summary="empresa fundada",
        )
        db_session.flush()

        resultado = reasoning_tools.TOOLS["auditoria"].run(ctx, "tudo")
        assert resultado.payload["results"][0]["summary"] == "empresa fundada"

    def test_calculadora_aceita_sinal_unario(self, db_session: Session) -> None:
        resultado = reasoning_tools.TOOLS["calculadora"].run(ToolContext(db=db_session), "-5 + 3")

        assert resultado.payload["result"] == -2.0

    def test_catalogo_lista_todas_as_ferramentas(self) -> None:
        catalogo = reasoning_tools.catalog()

        for nome in reasoning_tools.TOOLS:
            assert nome in catalogo


class TestLoop:
    def test_ciclo_completo_com_modelo_roteirizado(
        self, db_session: Session, nature: NatureManager
    ) -> None:
        agent = make_agent(db_session)
        ollama = make_react_ollama(
            [
                "Pensamento: preciso de contexto\nAção: auditoria\nEntrada da Ação: contratações",
                "Pensamento: já tenho o suficiente\nConclusão: seguir com a contratação",
            ]
        )

        session = react_engine.run_task(
            db_session,
            agent=agent,
            request=TaskRequest(task="Avaliar se devemos contratar um analista"),
            nature=nature,
            ollama=ollama,
        )

        tipos = [step.step_type for step in sorted(session.steps, key=lambda s: s.sequence)]
        assert tipos == [
            ReasoningStepType.THOUGHT,
            ReasoningStepType.ACTION,
            ReasoningStepType.OBSERVATION,
            ReasoningStepType.THOUGHT,
            ReasoningStepType.CONCLUSION,
        ]
        assert session.status is ReasoningStatus.COMPLETED
        assert session.conclusion == "seguir com a contratação"
        assert session.total_tokens > 0
        assert agent.status is AgentStatus.IDLE

    def test_fallback_offline_quando_ollama_indisponivel(
        self, db_session: Session, nature: NatureManager
    ) -> None:
        session = react_engine.run_task(
            db_session,
            agent=make_agent(db_session),
            request=TaskRequest(task="Quanta RAM ainda temos para novos subagentes?"),
            nature=nature,
            ollama=None,
        )

        acoes = [s for s in session.steps if s.step_type is ReasoningStepType.ACTION]
        assert session.status is ReasoningStatus.COMPLETED
        assert acoes[0].payload["tool"] == "infraestrutura"
        assert session.error is None

    def test_falha_do_ollama_fica_registrada_na_sessao(
        self, db_session: Session, nature: NatureManager
    ) -> None:
        falhando = OllamaClient(transport=httpx.MockTransport(lambda _: httpx.Response(500)))

        session = react_engine.run_task(
            db_session,
            agent=make_agent(db_session),
            request=TaskRequest(task="Quanta RAM ainda temos para novos subagentes?"),
            nature=nature,
            ollama=falhando,
        )

        assert session.status is ReasoningStatus.COMPLETED
        assert session.error is not None
        assert session.error.startswith("ollama_indisponivel")
        assert session.conclusion

    def test_ferramenta_desconhecida_vira_observacao_de_erro(
        self, db_session: Session, nature: NatureManager
    ) -> None:
        ollama = make_react_ollama(
            [
                "Pensamento: vou tentar\nAção: oraculo\nEntrada da Ação: futuro",
                "Pensamento: desisto\nConclusão: sem ferramenta adequada",
            ]
        )

        session = react_engine.run_task(
            db_session,
            agent=make_agent(db_session),
            request=TaskRequest(task="Prever o futuro do mercado"),
            nature=nature,
            ollama=ollama,
        )

        observacao = next(
            s for s in session.steps if s.step_type is ReasoningStepType.OBSERVATION
        )
        assert observacao.payload["error"] == "unknown_tool"

    def test_teto_de_passos_encerra_o_loop(
        self, db_session: Session, nature: NatureManager
    ) -> None:
        ollama = make_react_ollama(
            ["Pensamento: continuo\nAção: auditoria\nEntrada da Ação: tudo"] * 10
        )

        session = react_engine.run_task(
            db_session,
            agent=make_agent(db_session),
            request=TaskRequest(task="Investigar indefinidamente", max_steps=2),
            nature=nature,
            ollama=ollama,
        )

        conclusao = next(s for s in session.steps if s.step_type is ReasoningStepType.CONCLUSION)
        assert conclusao.payload["truncated"] is True
        assert session.status is ReasoningStatus.COMPLETED

    def test_modelo_fora_do_formato_vira_conclusao_direta(
        self, db_session: Session, nature: NatureManager
    ) -> None:
        ollama = make_react_ollama(["o modelo respondeu em prosa livre"])

        session = react_engine.run_task(
            db_session,
            agent=make_agent(db_session),
            request=TaskRequest(task="Resumir a situação da empresa"),
            nature=nature,
            ollama=ollama,
        )

        assert session.conclusion == "o modelo respondeu em prosa livre"

    def test_falha_do_motor_bloqueia_o_agente(
        self, db_session: Session, nature: NatureManager, monkeypatch
    ) -> None:
        agent = make_agent(db_session)

        def explode(*args: object, **kwargs: object) -> None:
            raise RuntimeError("ferramenta quebrou")

        monkeypatch.setattr(react_engine, "_execute_tool", explode)

        session = react_engine.run_task(
            db_session,
            agent=agent,
            request=TaskRequest(task="Consultar a memória corporativa da empresa"),
            nature=nature,
            ollama=None,
        )

        assert session.status is ReasoningStatus.FAILED
        assert session.error == "ferramenta quebrou"
        assert agent.status is AgentStatus.BLOCKED

    def test_complexidade_explicita_define_o_modelo(
        self, db_session: Session, nature: NatureManager
    ) -> None:
        session = react_engine.run_task(
            db_session,
            agent=None,
            request=TaskRequest(task="Classificar algo", complexity=TaskComplexity.TRIVIAL),
            nature=nature,
            ollama=None,
        )

        assert session.complexity is TaskComplexity.TRIVIAL
        assert session.model_name

    def test_pensamento_sem_acao_encerra_como_conclusao(
        self, db_session: Session, nature: NatureManager
    ) -> None:
        ollama = make_react_ollama(["Pensamento: a tarefa já está resolvida"])

        session = react_engine.run_task(
            db_session,
            agent=make_agent(db_session),
            request=TaskRequest(task="Confirmar o status do projeto", context={"origem": "CEO"}),
            nature=nature,
            ollama=ollama,
        )

        conclusao = next(s for s in session.steps if s.step_type is ReasoningStepType.CONCLUSION)
        assert conclusao.payload["reason"] == "sem_acao"
        assert session.conclusion == "a tarefa já está resolvida"


class TestPonteSincrona:
    @pytest.mark.asyncio
    async def test_await_funciona_com_loop_ativo(self) -> None:
        """Dentro de um loop em execução a corrotina vai para uma thread dedicada."""
        ollama = make_react_ollama(["Conclusão: ok"])

        completion = react_engine._await(ollama.generate(model="llama3.2:3b", prompt="oi"))

        assert completion.total_tokens == 46
