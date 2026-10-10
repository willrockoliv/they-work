"""Motor de decisão do Chief supervisor — analisa o report e define o próximo passo.

O veredito vem do modelo, apoiado em evidências (`chief_review`, ADR-022). Este
módulo decide o que fazer com ele:

* modo `shadow` (padrão) — vale a heurística do `report_analysis`; o veredito do
  modelo fica registrado para medir a concordância. Sem veredito válido do
  modelo, a heurística nunca aprova sozinha;
* modo `model` — vale o veredito do modelo; sem ele, o caso sobe ao CEO;
* vetos objetivos (placeholder, metatexto, entregável ausente, report sem
  modelo) transformam APPROVE em MODIFY (ADR-024);
* no limite de tentativas, REJECT/MODIFY viram ESCALATE (Chief) ou REJECT final (CEO).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.config.logging import get_logger
from app.config.settings import Settings, get_settings
from app.models.agent import Agent
from app.models.base import utcnow
from app.models.enums import (
    SUPERVISING_ROLES,
    AgentRole,
    AuditEventType,
    ChiefDecision,
    CommunicationStatus,
    CommunicationType,
    DecisionSource,
    TaskStatus,
)
from app.models.network import AgentTask, InitialRequest
from app.models.reasoning import ReasoningSession
from app.services import (
    agent_service,
    audit_service,
    chief_review,
    communication_service,
    report_analysis,
)
from app.services.chief_review import ReviewFeedback, ReviewOutcome
from app.services.communication_service import DelegationIntake, HierarchyError
from app.services.nature_manager import NatureManager
from app.services.ollama_client import OllamaClient
from app.services.report_analysis import Assessment

logger = get_logger(__name__)

#: Cardápio de vereditos. Vai no **contexto**, nunca no enunciado da tarefa: o
#: planejador determinístico offline ecoa o enunciado na conclusão, e um rótulo
#: ecoado seria lido pelo parser como se fosse a decisão do Chief.
DECISION_MENU = "APPROVE | REJECT | MODIFY | CONSULT_PEERS | ESCALATE"

CEO_DECISIONS: tuple[ChiefDecision, ...] = (
    ChiefDecision.APPROVE,
    ChiefDecision.REJECT,
    ChiefDecision.MODIFY,
)

_REDELEGATING = (ChiefDecision.REJECT, ChiefDecision.MODIFY)

_DECISION_PATTERNS: tuple[tuple[ChiefDecision, re.Pattern[str]], ...] = (
    (
        ChiefDecision.CONSULT_PEERS,
        re.compile(r"consult\w*\b[\s\w]{0,12}\b(peers|pares|colegas)", re.I),
    ),
    (ChiefDecision.ESCALATE, re.compile(r"escal(ar|o|ate|ação|acao)|levar ao ceo", re.I)),
    (ChiefDecision.REJECT, re.compile(r"reject|rejeit(ar|o|ado)|reconvoc", re.I)),
    (ChiefDecision.MODIFY, re.compile(r"modify|modific(ar|o)|subtarefa|ajust(ar|e)", re.I)),
    (ChiefDecision.APPROVE, re.compile(r"approve|aprov(ar|o|ado)", re.I)),
)


@dataclass(frozen=True, slots=True)
class ReviewResult:
    """Veredito do Chief sobre um report, com tudo o que ele desencadeou."""

    task: AgentTask
    decision: ChiefDecision
    rationale: str
    assessment: Assessment
    reasoning: ReasoningSession | None
    follow_up: AgentTask | None = None
    consulted_roles: tuple[AgentRole, ...] = field(default_factory=tuple)
    escalated_to_ceo: bool = False
    decision_source: DecisionSource = DecisionSource.HEURISTIC_SHADOW


def review_and_decide(
    session: Session,
    task: AgentTask,
    *,
    nature: NatureManager | None = None,
    ollama: OllamaClient | None = None,
    settings: Settings | None = None,
) -> ReviewResult:
    """Chief supervisor analisa o report do subordinado e aplica o veredito."""
    if task.status is not TaskStatus.AWAITING_REVIEW:
        msg = f"A tarefa '{task.title}' não está aguardando revisão (status {task.status.value})."
        raise HierarchyError(msg)

    chief = session.get(Agent, task.assigned_by_chief_id) if task.assigned_by_chief_id else None
    if chief is None or chief.role not in SUPERVISING_ROLES:
        msg = "Só o Chief supervisor que delegou a tarefa pode revisá-la."
        raise HierarchyError(msg)

    config = settings or get_settings()
    assessment = report_analysis.assess(session, task, task.report_summary or "")
    outcome = chief_review.review(
        session,
        task,
        chief,
        allowed=tuple(ChiefDecision),
        instruction=f"Analisar o report da tarefa '{task.title}' e definir o próximo passo.",
        context={
            "tarefa": task.title,
            "tentativa": task.attempt,
            "vereditos_possiveis": DECISION_MENU,
        },
        settings=config,
        nature=nature,
        ollama=ollama,
    )

    decision, source, rationale = _chief_choice(assessment, outcome, config)
    vetoes = _vetoes(session, task, assessment)
    decision, rationale = _veto(decision, rationale, vetoes)
    if decision in _REDELEGATING and task.attempt >= config.chief_review_max_attempts:
        source = DecisionSource.ATTEMPT_LIMIT
        rationale = (
            f"Limite de {config.chief_review_max_attempts} tentativas atingido com "
            f"{decision.value}: levo o caso ao CEO. {rationale}"
        )
        decision = ChiefDecision.ESCALATE

    _record(task, decision, source, rationale, assessment, outcome, vetoes, config)
    return _apply(
        session,
        task,
        chief,
        decision,
        rationale,
        assessment,
        outcome.reasoning,
        source=source,
        feedback=outcome.feedback(),
    )


def parse_decision(text: str) -> ChiefDecision | None:
    """Extrai o veredito de um texto livre, tolerando sinônimos em português.

    Não decide nada no fluxo de revisão (lá o veredito é JSON validado); serve
    para ler textos livres legados.
    """
    for decision, pattern in _DECISION_PATTERNS:
        if pattern.search(text):
            return decision
    return None


def _chief_choice(
    assessment: Assessment, outcome: ReviewOutcome, config: Settings
) -> tuple[ChiefDecision, DecisionSource, str]:
    """Veredito do Chief conforme o modo de rollout (ADR-026)."""
    if config.chief_review_mode == "model":
        if outcome.verdict is not None and outcome.decision is not None:
            return outcome.decision, DecisionSource.MODEL, outcome.verdict.justificativa
        detail = "; ".join(outcome.errors[:2]) or outcome.source.value
        return (
            ChiefDecision.ESCALATE,
            outcome.source,
            f"Sem veredito válido do modelo ({detail}): o caso sobe ao CEO.",
        )

    decision = assessment.decision
    rationale = assessment.rationale
    if decision is ChiefDecision.APPROVE and outcome.verdict is None:
        # Revisão degradada nunca aprova sozinha (ADR-024).
        detail = "; ".join(outcome.errors[:1]) or outcome.source.value
        return (
            ChiefDecision.ESCALATE,
            DecisionSource.HEURISTIC_SHADOW,
            f"A heurística aprovaria, mas não há veredito válido do modelo ({detail}): "
            f"levo ao CEO. {rationale}",
        )
    return decision, DecisionSource.HEURISTIC_SHADOW, rationale


def _vetoes(session: Session, task: AgentTask, assessment: Assessment) -> list[str]:
    """Fatos objetivos que impedem a aprovação, venha o veredito de onde vier."""
    reasons = list(assessment.vetoes)
    if task.report_reasoning_session_id is not None:
        report_session = session.get(ReasoningSession, task.report_reasoning_session_id)
        if report_session is not None and report_session.error:
            reasons.append(f"report sem modelo: {report_session.error[:80]}")
    return reasons


def _veto(
    decision: ChiefDecision, rationale: str, vetoes: list[str]
) -> tuple[ChiefDecision, str]:
    if decision is ChiefDecision.APPROVE and vetoes:
        return ChiefDecision.MODIFY, f"Aprovação vetada ({'; '.join(vetoes)}). {rationale}"
    return decision, rationale


def _record(
    task: AgentTask,
    decision: ChiefDecision,
    source: DecisionSource,
    rationale: str,
    assessment: Assessment,
    outcome: ReviewOutcome,
    vetoes: list[str],
    config: Settings,
) -> None:
    model_decision = outcome.decision.value if outcome.decision else None
    task.review_reasoning_session_id = outcome.reasoning.id
    task.quality_score = assessment.quality.score
    task.decision = decision
    task.decision_rationale = rationale
    task.decision_source = source.value
    task.review_evidence = {
        **outcome.to_evidence(),
        "mode": config.chief_review_mode,
        "applied": decision.value,
        "decision_source": source.value,
        "heuristic": assessment.decision.value,
        "model_decision": model_decision,
        "agrees": model_decision == assessment.decision.value if model_decision else None,
        "vetoes": vetoes,
        "attempt": task.attempt,
        "max_attempts": config.chief_review_max_attempts,
        "artifacts": assessment.artifacts.to_dict(),
        "deliverables": [check.to_dict() for check in assessment.deliverables],
    }
    task.reviewed_at = utcnow()


# --- Aplicação do veredito ---------------------------------------------------


def _apply(
    session: Session,
    task: AgentTask,
    chief: Agent,
    decision: ChiefDecision,
    rationale: str,
    assessment: Assessment,
    reasoning: ReasoningSession,
    *,
    source: DecisionSource,
    feedback: list[ReviewFeedback],
    redelegate: bool = True,
) -> ReviewResult:
    request = session.get(InitialRequest, task.request_id)
    if request is None:  # pragma: no cover - FK garante a existência
        msg = "Pedido da tarefa não encontrado."
        raise HierarchyError(msg)
    session.flush()

    communication_service.record_edge(
        session,
        request,
        communication_type=CommunicationType.DECISION,
        sender=chief,
        recipient=session.get(Agent, task.assigned_to_agent_id)
        if task.assigned_to_agent_id
        else None,
        summary=f"{decision.value}: {task.title}",
        content={
            "rationale": rationale,
            "decision_source": source.value,
            "feedback": [item.to_dict() for item in feedback],
            "assessment": assessment.to_dict(),
        },
        task=task,
        reasoning_session_id=reasoning.id,
        status=CommunicationStatus.PROCESSED,
    )

    audit_service.record_event(
        session,
        event_type=AuditEventType.TASK_REVIEWED,
        actor=chief.role.value,
        decision=decision.value,
        summary=f"{chief.role.value} decidiu {decision.value} sobre '{task.title}'",
        narrative=rationale,
        agent_id=chief.id,
        payload={
            "task_id": str(task.id),
            "request_id": str(request.id),
            "quality_score": assessment.quality.score,
            "decision_source": source.value,
            "assessment": assessment.to_dict(),
        },
    )

    follow_up: AgentTask | None = None
    consulted: tuple[AgentRole, ...] = ()
    escalated = False

    if decision is ChiefDecision.APPROVE:
        task.status = TaskStatus.COMPLETED
    elif decision in _REDELEGATING:
        task.status = (
            TaskStatus.REJECTED if decision is ChiefDecision.REJECT else TaskStatus.COMPLETED
        )
        if redelegate:
            follow_up = _redelegate(
                session, request, task, chief, decision, assessment, feedback
            )
    elif decision is ChiefDecision.CONSULT_PEERS:
        consulted = _consult_peers(session, request, task, chief, assessment)
        task.status = TaskStatus.AWAITING_REVIEW
    else:
        escalated = _escalate(session, request, task, chief, rationale)
        task.status = TaskStatus.AWAITING_REVIEW

    session.flush()
    communication_service.publish_task(task)

    if not communication_service.has_open_tasks(session, request.id):
        communication_service.close_request(
            session,
            request,
            outcome=decision.value,
            narrative=f"Todas as tarefas de '{request.topic}' foram encerradas. {rationale}",
        )

    logger.info(
        "network.task_reviewed",
        task_id=str(task.id),
        chief=chief.role.value,
        decision=decision.value,
        quality=assessment.quality.score,
    )
    return ReviewResult(
        task=task,
        decision=decision,
        rationale=rationale,
        assessment=assessment,
        reasoning=reasoning,
        follow_up=follow_up,
        consulted_roles=consulted,
        escalated_to_ceo=escalated,
        decision_source=source,
    )


def _redelegate(
    session: Session,
    request: InitialRequest,
    task: AgentTask,
    chief: Agent,
    decision: ChiefDecision,
    assessment: Assessment,
    feedback: list[ReviewFeedback],
) -> AgentTask | None:
    """Reconvoca o agente com o objetivo original e o feedback estruturado.

    REJECT pede para refazer; MODIFY pede um complemento. Em ambos a descrição
    preserva o objetivo original e lista o que corrigir, com o trecho criticado.
    """
    agent = session.get(Agent, task.assigned_to_agent_id) if task.assigned_to_agent_id else None
    if agent is None:
        return None

    # Mesmo quando o CEO desempata, quem redelega é o supervisor direto do agente:
    # o CEO decide, mas não assume o time de outra diretoria.
    supervisor = session.get(Agent, task.assigned_by_chief_id) or chief

    items = feedback or [
        ReviewFeedback(gap, "", f"Cobrir com evidência: {gap}")
        for gap in assessment.comparison.gaps[:5]
    ]
    if not items:
        items = [
            ReviewFeedback(
                "Objetivo", "", "Refazer cobrindo o objetivo original com dados concretos."
            )
        ]
    lines = "\n".join(
        f"- {item.criterio}: {item.correcao}"
        + (f' (trecho criticado: "{item.citacao[:160]}")' if item.citacao else "")
        for item in items
    )

    objective = report_analysis.objective_of(task)
    # Sem isto o título acumula "[Refazer] [Refazer] ..." a cada tentativa.
    base_title = re.sub(r"^(\[Refazer\]|\[Ajuste\])\s*", "", task.title).strip()
    if decision is ChiefDecision.REJECT:
        title = f"[Refazer] {base_title}"
        instruction = (
            f"O report anterior foi rejeitado pelo {chief.role.value}. "
            f"Refaça a entrega corrigindo:\n{lines}"
        )
    else:
        title = f"[Ajuste] {base_title}"
        instruction = f"Complemente a entrega anterior corrigindo:\n{lines}"

    feedback_dicts = [item.to_dict() for item in items]
    task.context = {**task.context, "feedback_emitido": feedback_dicts}
    deliverables = tuple(str(item) for item in task.context.get("deliverables", []))

    return communication_service.delegate_task(
        session,
        request,
        supervisor,
        agent,
        DelegationIntake(
            title=title,
            task_description=f"{objective}\n\n{instruction}",
            acceptance_criteria=(
                report_analysis.criteria_of(task) or assessment.comparison.gaps[:5]
            ),
            deliverables=deliverables,
            context={
                "origin_task_id": str(task.id),
                "decision": decision.value,
                "objetivo_original": objective,
                "instrucao_de_ajuste": instruction,
                "feedback": feedback_dicts,
            },
        ),
        parent=task,
    )


def _consult_peers(
    session: Session, request: InitialRequest, task: AgentTask, chief: Agent, assessment: Assessment
) -> tuple[AgentRole, ...]:
    """O Chief pede a leitura dos colegas; divergência manda o caso ao CEO."""
    peers = [role for role in SUPERVISING_ROLES if role not in (chief.role, AgentRole.CEO)]
    consulted: list[AgentRole] = []
    for role in peers:
        peer = agent_service.get_chief(session, role)
        if peer is None:
            continue
        communication_service.record_edge(
            session,
            request,
            communication_type=CommunicationType.CONSULTATION,
            sender=chief,
            recipient=peer,
            summary=f"{chief.role.value} consulta {role.value} sobre '{task.title}'",
            content={
                "question": "A entrega afeta a sua diretoria? Aprovo ou peço ajuste?",
                "assessment": assessment.to_dict(),
            },
            task=task,
        )
        consulted.append(role)

    audit_service.record_event(
        session,
        event_type=AuditEventType.CHIEF_CONSULTATION,
        actor=chief.role.value,
        summary=f"{chief.role.value} consultou os pares sobre '{task.title}'",
        narrative=assessment.rationale,
        agent_id=chief.id,
        payload={"task_id": str(task.id), "peers": [role.value for role in consulted]},
    )
    return tuple(consulted)


def _escalate(
    session: Session, request: InitialRequest, task: AgentTask, chief: Agent, rationale: str
) -> bool:
    """Leva o caso ao CEO, que detém o voto de desempate."""
    ceo = agent_service.get_chief(session, AgentRole.CEO)
    if ceo is None:
        return False
    communication_service.record_edge(
        session,
        request,
        communication_type=CommunicationType.ESCALATION,
        sender=chief,
        recipient=ceo,
        summary=f"{chief.role.value} escala '{task.title}' ao CEO",
        content={"rationale": rationale},
        task=task,
    )
    return True


def ceo_final_decision(
    session: Session,
    task: AgentTask,
    *,
    nature: NatureManager | None = None,
    ollama: OllamaClient | None = None,
    settings: Settings | None = None,
) -> ReviewResult:
    """Desempate do CEO sobre uma tarefa escalada ou em consulta entre pares."""
    ceo = agent_service.get_chief(session, AgentRole.CEO)
    if ceo is None:
        msg = "O CEO não foi inicializado."
        raise HierarchyError(msg)

    request = session.get(InitialRequest, task.request_id)
    if request is None:  # pragma: no cover - FK garante a existência
        msg = "Pedido da tarefa não encontrado."
        raise HierarchyError(msg)

    assessment = report_analysis.assess(session, task, task.report_summary or "")
    config = settings or get_settings()
    escalated_from = {
        "decision": task.decision.value if task.decision else None,
        "decision_source": task.decision_source,
        "rationale": task.decision_rationale,
    }
    outcome = chief_review.review(
        session,
        task,
        ceo,
        allowed=CEO_DECISIONS,
        instruction=(
            f"Dar a palavra final sobre '{task.title}' após divergência ou escalonamento "
            "das diretorias."
        ),
        context={
            "tarefa": task.title,
            "tentativa": task.attempt,
            "vereditos_possiveis": " | ".join(item.value for item in CEO_DECISIONS),
            "motivo_do_escalonamento": (task.decision_rationale or "")[:300],
        },
        settings=config,
        nature=nature,
        ollama=ollama,
    )

    if config.chief_review_mode == "model" and outcome.decision in CEO_DECISIONS:
        decision = outcome.decision
        source = DecisionSource.MODEL
        basis = outcome.verdict.justificativa if outcome.verdict else ""
    else:
        decision = _tiebreak(assessment, model_available=outcome.verdict is not None)
        source = DecisionSource.CEO_FALLBACK
        basis = assessment.rationale
    vetoes = _vetoes(session, task, assessment)
    decision, basis = _veto(decision, basis, vetoes)

    redelegate = True
    if decision in _REDELEGATING and task.attempt >= config.chief_review_max_attempts:
        # Sem nova rodada: a frente se encerra rejeitada, com o histórico registrado.
        decision = ChiefDecision.REJECT
        source = DecisionSource.ATTEMPT_LIMIT
        redelegate = False
        basis = (
            f"Limite de {config.chief_review_max_attempts} tentativas atingido: "
            f"a frente se encerra rejeitada. {basis}"
        )
    rationale = f"Desempate do CEO: {decision.value}. {basis}"

    _record(task, decision, source, rationale, assessment, outcome, vetoes, config)
    task.review_evidence = {**task.review_evidence, "escalated_from": escalated_from}
    session.flush()

    audit_service.record_event(
        session,
        event_type=AuditEventType.CEO_TIEBREAK,
        actor=AgentRole.CEO.value,
        decision=decision.value,
        summary=f"CEO desempatou '{task.title}' com {decision.value}",
        narrative=rationale,
        agent_id=ceo.id,
        payload={
            "task_id": str(task.id),
            "request_id": str(request.id),
            "decision_source": source.value,
        },
    )
    return _apply(
        session,
        task,
        ceo,
        decision,
        rationale,
        assessment,
        outcome.reasoning,
        source=source,
        feedback=outcome.feedback(),
        redelegate=redelegate,
    )


def _tiebreak(assessment: Assessment, *, model_available: bool) -> ChiefDecision:
    """Critério conservador do CEO: sem veredito válido do modelo, nunca aprova."""
    if (
        model_available
        and assessment.quality.score >= 85
        and not assessment.comparison.gaps
    ):
        return ChiefDecision.APPROVE
    if assessment.quality.score < 60:
        return ChiefDecision.REJECT
    return ChiefDecision.MODIFY
