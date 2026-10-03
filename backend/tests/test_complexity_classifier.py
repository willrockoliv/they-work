"""Classificador heurístico de complexidade de tarefas."""

from __future__ import annotations

import pytest

from app.models import AgentRole, TaskComplexity
from app.services import complexity_classifier


class TestNormalize:
    def test_remove_acentos_e_caixa(self) -> None:
        assert complexity_classifier.normalize("Análise  de MERCADO") == "analise de mercado"


class TestClassify:
    @pytest.mark.parametrize(
        ("descricao", "esperado"),
        [
            ("resumir ata", TaskComplexity.TRIVIAL),
            (
                "Analisar relatorio de vendas do trimestre corrente da empresa",
                TaskComplexity.MODERATE,
            ),
            (
                "Implementar a arquitetura do modulo de codigo com foco em seguranca",
                TaskComplexity.CRITICAL,
            ),
        ],
    )
    def test_niveis_por_palavras_chave(
        self, descricao: str, esperado: TaskComplexity
    ) -> None:
        assert complexity_classifier.classify(descricao).complexity is esperado

    def test_escopo_largo_aumenta_o_score(self) -> None:
        base = complexity_classifier.classify("Analisar dados de clientes do mes")
        amplo = complexity_classifier.classify(
            "Analisar dados de clientes do mes", deliverables=4, tools=4
        )

        assert amplo.score == base.score + 2
        assert "multiplos_entregaveis(+1)" in amplo.signals
        assert "muitas_ferramentas(+1)" in amplo.signals

    def test_piso_do_cargo_eleva_tarefa_simples(self) -> None:
        avaliacao = complexity_classifier.classify("resumir ata", requested_by=AgentRole.CTO)

        assert avaliacao.complexity is TaskComplexity.MODERATE
        assert "piso_CTO(MODERATE)" in avaliacao.signals

    def test_piso_nao_rebaixa_tarefa_critica(self) -> None:
        avaliacao = complexity_classifier.classify(
            "Resolver o impasse estrategico sobre pivotar o produto",
            requested_by=AgentRole.CFO,
        )

        assert avaliacao.complexity is TaskComplexity.CRITICAL

    def test_resultado_e_serializavel(self) -> None:
        dados = complexity_classifier.classify("Documentar o roteiro de testes").to_dict()

        assert dados["complexity"] in {c.value for c in TaskComplexity}
        assert isinstance(dados["signals"], list)
        assert dados["rationale"]
