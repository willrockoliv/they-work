"""Testes de carga unitária da Natureza — tradução de limites físicos em regras corporativas."""

from __future__ import annotations

import pytest

from app.config.settings import Settings
from app.models.enums import NatureDecision, ResourceStatus, TaskComplexity
from app.services.nature_manager import HiringRequest
from tests.conftest import make_nature


def _request(
    complexity: TaskComplexity = TaskComplexity.SIMPLE, model: str | None = None
) -> HiringRequest:
    return HiringRequest(
        requested_by="CTO",
        job_title="Analista de Dados",
        complexity=complexity,
        requested_model=model,
    )


class TestSnapshot:
    def test_calcula_ram_alocavel_descontando_reserva(self) -> None:
        nature = make_nature(ram_used=4_000)
        snapshot = nature.snapshot()

        # 16384 (limite) - 4000 (em uso) - 2048 (reserva do SO/IDE)
        assert snapshot.ram_allocatable_mb == 10_336
        assert snapshot.ram_usage_ratio == pytest.approx(4_000 / 16_384, rel=1e-3)

    def test_status_saudavel_com_folga(self) -> None:
        assert make_nature(ram_used=4_000).snapshot().status is ResourceStatus.HEALTHY

    def test_status_warning_acima_de_75_porcento(self) -> None:
        assert make_nature(ram_used=13_000).snapshot().status is ResourceStatus.WARNING

    def test_status_critico_acima_de_90_porcento(self) -> None:
        assert make_nature(ram_used=15_200).snapshot().status is ResourceStatus.CRITICAL

    def test_vram_saturada_tambem_dispara_estado_critico(self) -> None:
        nature = make_nature(ram_used=2_000, vram_used=4_000)
        assert nature.snapshot().status is ResourceStatus.CRITICAL

    def test_sem_gpu_nao_contamina_a_classificacao(self) -> None:
        nature = make_nature(ram_used=2_000, vram_total=0, vram_used=0)
        snapshot = nature.snapshot()

        assert snapshot.gpu_detected is False
        assert snapshot.vram_usage_ratio == 0.0
        assert snapshot.status is ResourceStatus.HEALTHY

    def test_limite_respeita_a_ram_fisica_menor_que_o_configurado(self) -> None:
        nature = make_nature(ram_total=8_192, ram_used=1_000)
        assert nature.snapshot().ram_limit_mb == 8_192

    def test_serializacao_para_auditoria(self) -> None:
        data = make_nature().snapshot().to_dict()
        assert data["status"] == ResourceStatus.HEALTHY.value
        assert isinstance(data["timestamp"], str)


class TestHiringGovernance:
    def test_aprova_quando_ha_recursos(self) -> None:
        verdict = make_nature(ram_used=4_000).evaluate_hiring(_request(TaskComplexity.CRITICAL))

        assert verdict.decision is NatureDecision.ALLOWED
        assert verdict.granted_model == "deepseek-r1:8b"
        assert verdict.allowed is True

    def test_downgrade_por_orcamento_insuficiente(self) -> None:
        # Sobram ~3.3 GB: não cabe o DeepSeek R1 (5 GB), cabe o Gemma (3 GB).
        nature = make_nature(ram_used=11_000)
        verdict = nature.evaluate_hiring(_request(TaskComplexity.CRITICAL))

        assert verdict.decision is NatureDecision.DOWNGRADED
        assert verdict.granted_model == "gemma3n:e4b"
        assert verdict.allowed is True

    def test_estado_critico_forca_o_modelo_mais_leve(self) -> None:
        # 90%+ de uso, mas ainda sobram ~3 GB para o Llama 3.2 3B.
        settings = Settings(nature_ram_limit_mb=32_768, nature_reserved_ram_mb=1_024)
        nature = make_nature(
            ram_total=32_768, ram_used=29_600, vram_used=0, vram_total=0, settings=settings
        )
        verdict = nature.evaluate_hiring(_request(TaskComplexity.CRITICAL))

        assert verdict.decision is NatureDecision.DOWNGRADED
        assert verdict.granted_model == "llama3.2:3b"

    def test_regime_de_atencao_rebaixa_o_teto_em_um_tier(self) -> None:
        # Orçamento comporta o DeepSeek R1, mas o regime WARNING limita o teto ao Qwen3.
        settings = Settings(nature_ram_limit_mb=32_768, nature_reserved_ram_mb=1_024)
        nature = make_nature(ram_total=32_768, ram_used=25_000, settings=settings)
        snapshot = nature.snapshot()
        verdict = nature.evaluate_hiring(_request(TaskComplexity.CRITICAL))

        assert snapshot.status is ResourceStatus.WARNING
        assert snapshot.ram_allocatable_mb > 5_120  # o modelo preferido caberia
        assert verdict.decision is NatureDecision.DOWNGRADED
        assert verdict.granted_model == "qwen3:8b"
        assert "contenção" in verdict.narrative

    def test_reserva_domina_os_limiares_na_configuracao_do_projeto(self) -> None:
        """Com 16 GB e 2 GB de reserva, sair de HEALTHY já zera o orçamento.

        `reserva + modelo_mais_leve (4096 MB) > (1 - 0.75) * 16384`, então o regime de
        contenção nunca chega a conceder um modelo: a vaga é represada antes disso.
        """
        nature = make_nature(ram_used=13_000)
        snapshot = nature.snapshot()
        verdict = nature.evaluate_hiring(_request(TaskComplexity.CRITICAL))

        assert snapshot.status is ResourceStatus.WARNING
        assert snapshot.ram_allocatable_mb < 2_048
        assert verdict.decision is NatureDecision.QUEUED

    def test_vram_saturada_rebaixa_o_modelo_mesmo_sobrando_ram(self) -> None:
        """O orçamento só enxerga RAM; a pressão de VRAM chega pelo teto do regime."""
        nature = make_nature(ram_used=5_000, vram_used=4_000)
        snapshot = nature.snapshot()
        verdict = nature.evaluate_hiring(_request(TaskComplexity.CRITICAL))

        assert snapshot.status is ResourceStatus.CRITICAL
        assert snapshot.ram_allocatable_mb > 5_120  # o DeepSeek R1 caberia na RAM
        assert verdict.decision is NatureDecision.DOWNGRADED
        assert verdict.granted_model == "llama3.2:3b"

    def test_bloqueia_e_enfileira_quando_nao_ha_orcamento(self) -> None:
        nature = make_nature(ram_used=15_000)
        verdict = nature.evaluate_hiring(_request())

        assert verdict.decision is NatureDecision.QUEUED
        assert verdict.granted_model is None
        assert verdict.allowed is False
        assert verdict.queue_position == 1
        assert "capacidade máxima" in verdict.narrative

    def test_limite_de_subagentes_simultaneos_represa_a_vaga(self) -> None:
        nature = make_nature(ram_used=1_000)
        verdict = nature.evaluate_hiring(_request(), active_subagents=4)

        assert verdict.decision is NatureDecision.QUEUED
        assert "estações de trabalho" in verdict.narrative

    def test_modelo_explicito_e_respeitado_como_preferencia(self) -> None:
        nature = make_nature(ram_used=11_000)
        verdict = nature.evaluate_hiring(_request(TaskComplexity.SIMPLE, model="qwen3:8b"))

        # O pedido explícito vira o teto; o orçamento ainda limita o resultado.
        assert verdict.granted_model == "gemma3n:e4b"

    def test_fila_cheia_resulta_em_bloqueio_definitivo(self) -> None:
        settings = Settings(nature_max_queue_size=1)
        nature = make_nature(ram_used=15_000, settings=settings)

        assert nature.evaluate_hiring(_request()).decision is NatureDecision.QUEUED
        assert nature.evaluate_hiring(_request()).decision is NatureDecision.BLOCKED


class TestQueue:
    def test_fifo(self) -> None:
        nature = make_nature()
        first, second = _request(), _request(TaskComplexity.COMPLEX)

        assert nature.enqueue(first) == 1
        assert nature.enqueue(second) == 2
        assert len(nature.pending()) == 2
        assert nature.dequeue() is first
        assert nature.dequeue() is second
        assert nature.dequeue() is None

    def test_clear_queue(self) -> None:
        nature = make_nature()
        nature.enqueue(_request())
        nature.clear_queue()
        assert nature.pending() == ()


class TestAlerts:
    def test_infraestrutura_saudavel_nao_alerta(self) -> None:
        assert make_nature().alerts() == ()

    def test_alerta_de_atencao(self) -> None:
        alertas = make_nature(ram_total=16_384, ram_used=12_500).alerts()

        assert [alerta.code for alerta in alertas] == ["CAPACITY_WARNING"]
        assert alertas[0].severity is ResourceStatus.WARNING

    def test_alerta_de_capacidade_esgotada(self) -> None:
        alertas = make_nature(ram_total=16_384, ram_used=16_000).alerts()

        assert any(alerta.code == "CAPACITY_EXHAUSTED" for alerta in alertas)

    def test_alerta_de_quadro_lotado(self) -> None:
        nature = make_nature()

        alertas = nature.alerts(
            active_subagents=nature.settings.nature_max_concurrent_subagents
        )

        assert any(alerta.code == "HEADCOUNT_FULL" for alerta in alertas)

    def test_alerta_de_fila_de_contratacoes(self) -> None:
        nature = make_nature()
        nature.enqueue(_request())

        assert any(alerta.code == "HIRING_QUEUE" for alerta in nature.alerts())

    def test_alerta_de_vram_esgotada(self) -> None:
        alertas = make_nature(vram_total=4_096, vram_used=4_000).alerts()

        assert any(alerta.code == "VRAM_EXHAUSTED" for alerta in alertas)

    def test_alerta_e_serializavel(self) -> None:
        alerta = make_nature(ram_total=16_384, ram_used=16_000).alerts()[0]

        assert alerta.to_dict()["severity"] == ResourceStatus.CRITICAL.value
