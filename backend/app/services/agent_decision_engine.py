"""Motor de decisão do Chief supervisor — analisa o report e define o próximo passo.

O Chief raciocina com as 7 ferramentas de análise (ciclo ReAct completo, auditável)
e o veredito sai do texto da conclusão. Quando o modelo não devolve um rótulo
reconhecível — o caso comum offline — vale a avaliação determinística do
`report_analysis`, que nunca deixa a decisão em aberto.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.config.logging import get_logger
from app.models.agent import Agent
from app.models.base import utcnow
from app.models.enums import (
    SUPERVISING_ROLES,
    AgentRole,
    AuditEventType,
    ChiefDecision,
    CommunicationStatus,
    CommunicationType,
    TaskStatus,
)
from app.models.network import AgentTask, InitialRequest
from app.models.reasoning import ReasoningSession
from app.services import (
    agent_service,
    audit_service,
    communication_service,
    react_engine,
    report_analysis,
)
from app.services.communication_service import DelegationIntake, HierarchyError
from app.services.nature_manager import NatureManager
from app.services.ollama_client import OllamaClient
from app.services.react_engine import TaskRequest
from app.services.report_analysis import Assessment

logger = get_logger(__name__)

#: Passos extras: a revisão encadeia várias ferramentas antes de concluir.
REVIEW_MAX_STEPS = 6

#: Cardápio de vereditos. Vai no **contexto**, nunca no enunciado da tarefa: o
#: planejador determinístico offline ecoa o enunciado na conclusão, e um rótulo
#: ecoado seria lido pelo parser como se fosse a decisão do Chief.
DECISION_MENU = "APPROVE | REJECT | MODIFY | CONSULT_PEERS | ESCALATE"

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


def review_and_decide(
    session: Session,
    task: AgentTask,
    *,
    nature: NatureManager | None = None,
    ollama: OllamaClient | None = None,
) -> ReviewResult:
    """Chief supervisor analisa o report do subordinado e aplica o veredito."""
    if task.status is not TaskStatus.AWAITING_REVIEW:
        msg = f"A tarefa '{task.title}' não está aguardando revisão (status {task.status.value})."
        raise HierarchyError(msg)

    chief = session.get(Agent, task.assigned_by_chief_id) if task.assigned_by_chief_id else None
    if chief is None or chief.role not in SUPERVISING_ROLES:
        msg = "Só o Chief supervisor que delegou a tarefa pode revisá-la."
        raise HierarchyError(msg)

    report_text = task.report_summary or ""
    assessment = report_analysis.assess(session, task, report_text)

    reasoning = react_engine.run_task(
        session,
        agent=chief,
        request=TaskRequest(
            task=f"Analisar o report da tarefa '{task.title}' e definir o próximo passo.",
            max_steps=REVIEW_MAX_STEPS,
            context={
                "tarefa": task.title,
                "tentativa": task.attempt,
                "vereditos_possiveis": DECISION_MENU,
                "qualidade_estimada": assessment.quality.score,
                "cobertura": f"{assessment.comparison.achievement_ratio:.0%}",
            },
        ),
        nature=nature,
        ollama=ollama,
        task_id=task.id,
    )

    decision = parse_decision(reasoning.conclusion or "") or assessment.decision
    rationale = _rationale(reasoning, assessment, decision)

    task.review_reasoning_session_id = reasoning.id
    task.quality_score = assessment.quality.score
    task.decision = decision
    task.decision_rationale = rationale
    task.reviewed_at = utcnow()
    session.flush()

    return _apply(session, task, chief, decision, rationale, assessment, reasoning)


def parse_decision(text: str) -> ChiefDecision | None:
    """Extrai o veredito da conclusão do Chief, tolerando sinônimos em português."""
    for decision, pattern in _DECISION_PATTERNS:
        if pattern.search(text):
            return decision
    return None


# --- Aplicação do veredito ---------------------------------------------------


def _apply(
    session: Session,
    task: AgentTask,
    chief: Agent,
    decision: ChiefDecision,
    rationale: str,
    assessment: Assessment,
    reasoning: ReasoningSession,
) -> ReviewResult:
    request = session.get(InitialRequest, task.request_id)
    if request is None:  # pragma: no cover - FK garante a existência
        msg = "Pedido da tarefa não encontrado."
        raise HierarchyError(msg)

    communication_service.record_edge(
        session,
        request,
        communication_type=CommunicationType.DECISION,
        sender=chief,
        recipient=session.get(Agent, task.assigned_to_agent_id)
        if task.assigned_to_agent_id
        else None,
        summary=f"{decision.value}: {task.title}",
        content={"rationale": rationale, "assessment": assessment.to_dict()},
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
            "assessment": assessment.to_dict(),
        },
    )

    follow_up: AgentTask | None = None
    consulted: tuple[AgentRole, ...] = ()
    escalated = False

    if decision is ChiefDecision.APPROVE:
        task.status = TaskStatus.COMPLETED
    elif decision in (ChiefDecision.REJECT, ChiefDecision.MODIFY):
        task.status = (
            TaskStatus.REJECTED if decision is ChiefDecision.REJECT else TaskStatus.COMPLETED
        )
        follow_up = _redelegate(session, request, task, chief, decision, assessment)
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
    )


def _redelegate(
    session: Session,
    request: InitialRequest,
    task: AgentTask,
    chief: Agent,
    decision: ChiefDecision,
    assessment: Assessment,
) -> AgentTask | None:
    """REJECT reconvoca o mesmo agente; MODIFY abre uma subtarefa com os gaps."""
    agent = session.get(Agent, task.assigned_to_agent_id) if task.assigned_to_agent_id else None
    if agent is None:
        return None

    # Mesmo quando o CEO desempata, quem redelega é o supervisor direto do agente:
    # o CEO decide, mas não assume o time de outra diretoria.
    supervisor = session.get(Agent, task.assigned_by_chief_id) or chief

    gaps = ", ".join(assessment.comparison.gaps[:5]) or "os pontos levantados na revisão"
    # Sem isto o título acumula "[Refazer] [Refazer] ..." a cada tentativa.
    base_title = re.sub(r"^(\[Refazer\]|\[Ajuste\])\s*", "", task.title).strip()
    if decision is ChiefDecision.REJECT:
        title = f"[Refazer] {base_title}"
        description = (
            f"{task.task_description}\n\nO report anterior foi rejeitado pelo "
            f"{chief.role.value}. Refaça cobrindo: {gaps}."
        )
    else:
        title = f"[Ajuste] {base_title}"
        description = (
            f"Complementar a entrega anterior de '{base_title}' fechando as lacunas: {gaps}."
        )

    return communication_service.delegate_task(
        session,
        request,
        supervisor,
        agent,
        DelegationIntake(
            title=title,
            task_description=description,
            acceptance_criteria=assessment.comparison.gaps[:5],
            context={"origin_task_id": str(task.id), "decision": decision.value},
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
    reasoning = react_engine.run_task(
        session,
        agent=ceo,
        request=TaskRequest(
            task=(
                f"Dar a palavra final sobre '{task.title}' após divergência entre as "
                "diretorias."
            ),
            max_steps=REVIEW_MAX_STEPS,
            context={
                "tarefa": task.title,
                "vereditos_possiveis": "APPROVE | REJECT | MODIFY",
                "qualidade": assessment.quality.score,
            },
        ),
        nature=nature,
        ollama=ollama,
        task_id=task.id,
    )

    decision = parse_decision(reasoning.conclusion or "") or _tiebreak(assessment)
    if decision in (ChiefDecision.CONSULT_PEERS, ChiefDecision.ESCALATE):
        decision = _tiebreak(assessment)
    rationale = (
        f"Desempate do CEO: {decision.value}. {reasoning.conclusion or assessment.rationale}"
    )

    task.decision = decision
    task.decision_rationale = rationale
    task.review_reasoning_session_id = reasoning.id
    task.reviewed_at = utcnow()
    session.flush()

    audit_service.record_event(
        session,
        event_type=AuditEventType.CEO_TIEBREAK,
        actor=AgentRole.CEO.value,
        decision=decision.value,
        summary=f"CEO desempatou '{task.title}' com {decision.value}",
        narrative=rationale,
        agent_id=ceo.id,
        payload={"task_id": str(task.id), "request_id": str(request.id)},
    )
    return _apply(session, task, ceo, decision, rationale, assessment, reasoning)


def _tiebreak(assessment: Assessment) -> ChiefDecision:
    """Critério do CEO: menor risco de caixa, sem deixar a tarefa em aberto."""
    if assessment.quality.score >= 85 and not assessment.comparison.gaps:
        return ChiefDecision.APPROVE
    if assessment.quality.score < 60:
        return ChiefDecision.REJECT
    return ChiefDecision.MODIFY


def _rationale(
    reasoning: ReasoningSession, assessment: Assessment, decision: ChiefDecision
) -> str:
    conclusion = (reasoning.conclusion or "").strip()
    if conclusion and parse_decision(conclusion) is decision:
        return conclusion
    return assessment.rationale
