"""Ferramentas e heurísticas determinísticas da revisão por evidências."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.models.enums import MemoryType
from app.models.memory import CorporateMemory
from app.services import reasoning_tools, report_analysis
from app.services.reasoning_tools import ToolContext


def run(db: Session, tool: str, query: str) -> reasoning_tools.ToolResult:
    return reasoning_tools.TOOLS[tool].run(ToolContext(db=db), query)


class TestCalcular:
    def test_ponto_de_equilibrio(self, db_session: Session) -> None:
        result = run(
            db_session,
            "calcular",
            "ponto_de_equilibrio custos_fixos=10000 preco=50 custo_variavel=30",
        )

        assert result.error is None
        assert result.payload["result"] == "500.00"
        assert result.payload["formula"] == "F/(p-v)"

    def test_ponto_de_equilibrio_aceita_formato_brasileiro(self, db_session: Session) -> None:
        result = run(
            db_session,
            "calcular",
            "ponto de equilíbrio custos_fixos=1.000,50 preco=10,5 custo_variavel=0,5",
        )

        assert result.payload["result"] == "100.05"

    def test_margem_nao_positiva(self, db_session: Session) -> None:
        result = run(
            db_session,
            "calcular",
            "ponto_de_equilibrio custos_fixos=100 preco=10 custo_variavel=10",
        )

        assert result.error == "margem_nao_positiva"

    def test_parametros_invalidos(self, db_session: Session) -> None:
        result = run(db_session, "calcular", "ponto_de_equilibrio preco=10")

        assert result.error == "parametros_invalidos"

    def test_decimal_com_unidade(self, db_session: Session) -> None:
        result = run(db_session, "calcular", "0.1 + 0.2 | reais")

        assert result.payload["result"] == "0.3"
        assert result.output.endswith("0.3 reais")

    def test_recusa_codigo(self, db_session: Session) -> None:
        result = run(db_session, "calcular", "__import__('os')")

        assert result.error is not None


class TestMemoriaBm25:
    def test_termo_raro_pesa_mais_que_termo_comum(self, db_session: Session) -> None:
        for title, content in (
            ("Clientes 1", "clientes clientes clientes do varejo"),
            ("Clientes 2", "clientes do atacado"),
            ("Churn", "churn de clientes caiu no trimestre"),
        ):
            db_session.add(
                CorporateMemory(
                    memory_type=MemoryType.REPORT,
                    title=title,
                    content=content,
                    author_role="SUBAGENT",
                    importance=5,
                    tags={},
                )
            )
        db_session.flush()

        result = run(db_session, "memoria_corporativa", "churn clientes")

        assert result.payload["results"][0]["title"] == "Churn"


class TestHeuristicas:
    @pytest.mark.parametrize(
        ("a", "b", "expected"),
        [("mapear", "mapeei", True), ("contrato", "conteudo", False), ("teste", "teste", True)],
    )
    def test_same_root(self, a: str, b: str, expected: bool) -> None:
        assert report_analysis.same_root(a, b) is expected

    def test_negacao_nao_conta_como_entrega(self) -> None:
        met, _ = report_analysis.lexical_criterion(
            "Mapear personas", "Não mapeei as personas ainda."
        )
        comparison = report_analysis.compare_vs_objective(
            "Mapear personas", "Não mapeei as personas ainda."
        )

        assert met is False
        assert comparison.achievement_ratio < 1.0
        assert "personas" in comparison.gaps

    def test_criterio_afirmado_e_encontrado(self) -> None:
        met, quote = report_analysis.lexical_criterion(
            "Mapear personas", "Mapeei três personas: sócio, associado e cliente."
        )

        assert met is True
        assert quote.startswith("Mapeei")

    def test_placeholder_limita_qualidade(self) -> None:
        text = "Resultado: receita de R$ X e custo de Y. " * 20

        quality = report_analysis.evaluate_quality(text)

        assert quality.score <= report_analysis.ARTIFACT_QUALITY_CAP
        assert report_analysis.detect_artifacts(text).placeholders

    def test_metatexto_e_detectado(self) -> None:
        artifacts = report_analysis.detect_artifacts("Pensamento: vou consultar a memória.")

        assert artifacts.blocking
        assert "vou consultar" in artifacts.metatext

    def test_numero_sem_unidade(self) -> None:
        artifacts = report_analysis.detect_artifacts("Atendemos 40 clientes e 15 casos.")

        assert artifacts.unitless_numbers == ("15",)

    def test_verify_quote_ignora_acento_e_exige_tamanho(self) -> None:
        text = "O ponto de equilíbrio é de 500 unidades."

        assert report_analysis.verify_quote("ponto de equilibrio e de 500", text)
        assert not report_analysis.verify_quote("sim", text)
        assert not report_analysis.verify_quote("lucro de 900 unidades", text)

    def test_premissas_marcam_calculo(self) -> None:
        premises = report_analysis.extract_premises("10000 / 20 = 500 unidades. Mercado de 3 mil.")

        assert premises[0].calculated
        assert not premises[-1].calculated
