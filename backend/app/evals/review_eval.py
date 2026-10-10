"""Avaliação da revisão do Chief contra o golden set (plano de revisão por evidências, 6.2).

Cada caso roda isolado num SQLite em memória — o banco da aplicação não é tocado.
Uso, dentro do container:

    docker compose exec backend python -m app.evals.review_eval            # modo model
    docker compose exec backend python -m app.evals.review_eval --offline  # sem Ollama

Sai com código 0 quando a concordância atinge `AGREEMENT_THRESHOLD` (Etapa 0.4).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config.settings import Settings, get_settings
from app.models import Base
from app.models.enums import AgentRole, DecisionSource, TaskStatus
from app.services import (
    agent_decision_engine,
    agent_service,
    communication_service,
    council_service,
)
from app.services.communication_service import DelegationIntake, RequestIntake
from app.services.nature_manager import NatureManager
from app.services.ollama_client import OllamaClient
from app.services.ra_service import HiringIntake

GOLDEN_PATH = Path(__file__).with_name("golden_review.json")

#: Concordância mínima para trocar o modo `shadow` pelo `model` (Etapa 0.4).
AGREEMENT_THRESHOLD = 0.9

_FALLBACK = frozenset({DecisionSource.UNAVAILABLE.value, DecisionSource.INVALID_OUTPUT.value})


@dataclass(frozen=True, slots=True)
class GoldenCase:
    id: str
    role: str
    objective: str
    criteria: tuple[str, ...]
    deliverables: tuple[str, ...]
    report: str
    expected: tuple[str, ...]
    tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CaseResult:
    id: str
    decision: str
    source: str
    expected: tuple[str, ...]
    ok: bool
    tokens: int
    tags: tuple[str, ...]


def load_cases(path: Path = GOLDEN_PATH) -> list[GoldenCase]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        GoldenCase(
            id=item["id"],
            role=item["role"],
            objective=item["objective"],
            criteria=tuple(item["criteria"]),
            deliverables=tuple(item["deliverables"]),
            report=item["report"],
            expected=tuple(item["expected"]),
            tags=tuple(item.get("tags", ())),
        )
        for item in data["cases"]
    ]


def run_case(
    case: GoldenCase,
    *,
    settings: Settings,
    nature: NatureManager,
    ollama: OllamaClient | None,
) -> CaseResult:
    """Monta a tarefa do caso num banco descartável e aplica a revisão do Chief."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session: Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    try:
        agent_service.init_chiefs(session)
        council_service.init_profiles(session)
        request = communication_service.submit_request(
            session, RequestIntake(topic=f"Golden {case.id}", description=case.objective)
        )
        chief = agent_service.get_chief(session, AgentRole(case.role))
        if chief is None:  # pragma: no cover - init_chiefs cria todas as diretorias
            msg = f"Diretoria {case.role} inexistente."
            raise ValueError(msg)
        agent = communication_service.request_agent(
            session,
            nature,
            request,
            chief,
            HiringIntake(
                requested_by=chief.role,
                job_title="Analista",
                specialization="avaliação do golden set",
                objective=f"Entregar a frente do caso {case.id}: {case.objective}",
                deliverables=case.deliverables,
            ),
        ).agent
        if agent is None:  # pragma: no cover - a Natureza do eval tem folga
            msg = "A Natureza negou a contratação do agente do caso."
            raise ValueError(msg)
        task = communication_service.delegate_task(
            session,
            request,
            chief,
            agent,
            DelegationIntake(
                title=f"Caso {case.id}",
                task_description=case.objective,
                acceptance_criteria=case.criteria,
                deliverables=case.deliverables,
            ),
        )
        task.status = TaskStatus.AWAITING_REVIEW
        task.report_summary = case.report
        session.flush()

        result = agent_decision_engine.review_and_decide(
            session, task, nature=nature, ollama=ollama, settings=settings
        )
        return CaseResult(
            id=case.id,
            decision=result.decision.value,
            source=result.decision_source.value,
            expected=case.expected,
            ok=result.decision.value in case.expected,
            tokens=int(task.review_evidence.get("tokens") or 0),
            tags=case.tags,
        )
    finally:
        session.close()
        engine.dispose()


def summarize(results: Sequence[CaseResult]) -> dict[str, Any]:
    total = len(results)

    def rate(count: int) -> float:
        return round(count / total, 4) if total else 0.0

    agreement = rate(sum(item.ok for item in results))
    return {
        "total": total,
        "agreement": agreement,
        "threshold": AGREEMENT_THRESHOLD,
        "passed": agreement >= AGREEMENT_THRESHOLD,
        "escalate_rate": rate(sum(item.decision == "ESCALATE" for item in results)),
        "fallback_rate": rate(sum(item.source in _FALLBACK for item in results)),
        "approved_unsafe": [
            item.id for item in results if item.decision == "APPROVE" and not item.ok
        ],
        "tokens": sum(item.tokens for item in results),
        "failures": [asdict(item) for item in results if not item.ok],
    }


def evaluate(
    cases: Sequence[GoldenCase],
    *,
    mode: Literal["shadow", "model"] = "model",
    settings: Settings | None = None,
    nature_factory: Callable[[], NatureManager] | None = None,
    ollama: OllamaClient | None = None,
) -> dict[str, Any]:
    """Roda os casos; cada um com uma Natureza nova, sem reservas herdadas do anterior."""
    config = (settings or get_settings()).model_copy(update={"chief_review_mode": mode})
    factory = nature_factory or (lambda: NatureManager(settings=config))
    results = [
        run_case(case, settings=config, nature=factory(), ollama=ollama) for case in cases
    ]
    return {"mode": mode, **summarize(results), "results": [asdict(item) for item in results]}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Avalia a revisão do Chief no golden set.")
    parser.add_argument("--mode", choices=("shadow", "model"), default="model")
    parser.add_argument("--offline", action="store_true", help="roda sem Ollama")
    parser.add_argument("--cases", type=Path, default=GOLDEN_PATH)
    parser.add_argument("--only", nargs="*", default=None, help="ids dos casos")
    args = parser.parse_args(argv)

    cases = load_cases(args.cases)
    if args.only:
        cases = [case for case in cases if case.id in set(args.only)]
    report = evaluate(cases, mode=args.mode, ollama=None if args.offline else OllamaClient())
    sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return 0 if report["passed"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
