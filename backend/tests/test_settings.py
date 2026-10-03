"""Configuração de ambiente da aplicação."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config.settings import Settings


def test_orcamento_alocavel_desconta_reservas() -> None:
    settings = Settings(nature_ram_limit_mb=16_384, nature_reserved_ram_mb=2_048)
    assert settings.allocatable_ram_mb == 14_336


def test_orcamento_nunca_fica_negativo() -> None:
    settings = Settings(nature_ram_limit_mb=1_024, nature_reserved_ram_mb=4_096)
    assert settings.allocatable_ram_mb == 0


def test_vram_alocavel() -> None:
    settings = Settings(nature_vram_limit_mb=4_096, nature_reserved_vram_mb=512)
    assert settings.allocatable_vram_mb == 3_584


def test_limiar_critico_deve_superar_o_de_alerta() -> None:
    with pytest.raises(ValidationError):
        Settings(nature_warning_threshold=0.9, nature_critical_threshold=0.8)


def test_limites_devem_ser_positivos() -> None:
    with pytest.raises(ValidationError):
        Settings(nature_ram_limit_mb=0)
