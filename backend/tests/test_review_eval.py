"""Script de avaliação do golden set — executado offline, sem Ollama."""

from __future__ import annotations

import json

import pytest

from app.evals import review_eval
from tests.conftest import make_nature


def test_golden_set_cobre_injecao_placeholder_e_positivos() -> None:
    cases = review_eval.load_cases()
    tags = {tag for case in cases for tag in case.tags}

    assert {"injecao", "placeholder", "positivo", "log"} <= tags
    assert len({case.id for case in cases}) == len(cases)


@pytest.mark.parametrize("mode", ["model", "shadow"])
def test_offline_nunca_aprova(mode: str) -> None:
    report = review_eval.evaluate(
        review_eval.load_cases(),
        mode=mode,  # type: ignore[arg-type]
        nature_factory=make_nature,
    )

    assert report["total"] == len(review_eval.load_cases())
    assert report["approved_unsafe"] == []
    assert all(item["decision"] != "APPROVE" for item in report["results"])
    if mode == "model":
        assert report["fallback_rate"] == 1.0
        assert report["escalate_rate"] == 1.0


def test_main_offline_imprime_json(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Sem sondas reais de hardware na suíte.
    monkeypatch.setattr(review_eval, "NatureManager", lambda settings: make_nature())

    code = review_eval.main(["--offline", "--only", "curto", "inj-aprovar"])

    report = json.loads(capsys.readouterr().out)
    assert report["total"] == 2
    assert code == (0 if report["passed"] else 1)
