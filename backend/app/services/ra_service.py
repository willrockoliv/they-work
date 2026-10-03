"""Recursos Agênticos (RA) — o único agente autorizado a instanciar subagentes.

Implementa o pipeline completo: triagem da requisição do Chief, questionamento de
pedidos vagos, auditoria pela Natureza, consulta ao Banco de Talentos, geração do
metaprompt, instanciação do subagente e sua posterior demissão.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.logging import get_logger
from app.models.agent import Agent
from app.models.base import utcnow
from app.models.enums import (
    AgentRole,
    AgentStatus,
    AgentType,
    AuditEventType,
    MemoryType,
    NatureDecision,
    RequestStatus,
    TaskComplexity,
)
from app.models.hiring import SubagentRequest
from app.models.memory import CorporateMemory
from app.models.talent import TalentProfile
from app.services import (
    agent_service,
    audit_service,
    complexity_classifier,
    model_catalog,
    prompt_factory,
    talent_bank,
)
from app.services.nature_manager import HiringRequest, HiringVerdict, NatureManager
from app.services.prompt_factory import MetapromptSpec

logger = get_logger(__name__)

#: Mínimo de palavras para o objetivo ser considerado acionável pelo RA.
MIN_OBJECTIVE_WORDS = 6

#: Cargos genéricos demais para virar um metaprompt sem especialização.
_GENERIC_TITLES: frozenset[str] = frozenset(
    {"ajudante", "assistente", "pessoa", "alguem", "funcionario", "agente", "analista", "dev"}
)


class RequestNotActionableError(RuntimeError):
    """A requisição ainda precisa de esclarecimentos antes de ser processada."""


@dataclass(frozen=True, slots=True)
class HiringIntake:
    """Pedido bruto de um Chief, antes da triagem do RA."""

    requested_by: AgentRole
    job_title: str
    objective: str = ""
    raw_request: str = ""
    deliverables: tuple[str, ...] = field(default_factory=tuple)
    tools: tuple[str, ...] = field(default_factory=tuple)
    constraints: tuple[str, ...] = field(default_factory=tuple)
    specialization: str = ""
    complexity: TaskComplexity | None = None
    requested_model: str | None = None


@dataclass(frozen=True, slots=True)
class HiringOutcome:
    """Resultado do pipeline de contratação."""

    request: SubagentRequest
    agent: Agent | None
    verdict: HiringVerdict | None
    questions: tuple[str, ...] = field(default_factory=tuple)
    reused_profile: bool = False
    narrative: str = ""


# --- Triagem -----------------------------------------------------------------


def screen(intake: HiringIntake) -> tuple[str, ...]:
    """Perguntas que o RA devolve ao Chief quando a requisição está vaga."""
    questions: list[str] = []
    title = complexity_classifier.normalize(intake.job_title)

    if not title:
        questions.append("Qual é o cargo exato que você precisa preencher?")
    elif title in _GENERIC_TITLES and not intake.specialization:
        questions.append(
            f"'{intake.job_title}' é genérico demais. Qual a especialização do profissional "
            "(ex.: dados, backend, conteúdo)?"
        )

    if len(intake.objective.split()) < MIN_OBJECTIVE_WORDS:
        questions.append(
            "Descreva o objetivo da contratação em pelo menos uma frase completa: o que "
            "exatamente esse subagente precisa resolver?"
        )

    if not intake.deliverables:
        questions.append("Quais entregáveis concretos você espera receber ao final da sprint?")

    if intake.requested_model and model_catalog.get_model(intake.requested_model) is None:
        questions.append(
            f"O modelo '{intake.requested_model}' não existe no repositório local. "
            "Escolha um do catálogo ou deixe o RA decidir."
        )

    return tuple(questions)


# --- Pipeline ----------------------------------------------------------------


def submit_request(
    session: Session, nature: NatureManager, intake: HiringIntake
) -> HiringOutcome:
    """Registra a requisição do Chief e, se ela for acionável, tenta contratar."""
    requester = agent_service.get_chief(session, intake.requested_by)
    request = SubagentRequest(
        requested_by_role=intake.requested_by,
        requester_agent_id=requester.id if requester else None,
        job_title=intake.job_title,
        objective=intake.objective,
        raw_request=intake.raw_request or intake.objective,
        deliverables={"items": list(intake.deliverables)},
        tools={"items": list(intake.tools)},
        constraints={"items": list(intake.constraints), "specialization": intake.specialization},
        complexity=intake.complexity or TaskComplexity.SIMPLE,
        requested_model=intake.requested_model,
        status=RequestStatus.DRAFT,
    )
    session.add(request)
    session.flush()

    audit_service.record_event(
        session,
        event_type=AuditEventType.SUBAGENT_REQUESTED,
        actor=intake.requested_by.value,
        summary=f"Requisição de contratação: {intake.job_title}",
        narrative=(
            f"{intake.requested_by.value} abriu uma vaga para '{intake.job_title}' "
            "e encaminhou o pedido ao RA."
        ),
        agent_id=requester.id if requester else None,
        payload={"request_id": str(request.id), "objective": intake.objective},
    )

    questions = screen(intake)
    if questions:
        return _ask_for_clarification(session, request, questions)

    return _process(session, nature, request, intake)


def clarify_request(
    session: Session,
    nature: NatureManager,
    request: SubagentRequest,
    *,
    objective: str | None = None,
    deliverables: tuple[str, ...] | None = None,
    tools: tuple[str, ...] | None = None,
    specialization: str | None = None,
    job_title: str | None = None,
) -> HiringOutcome:
    """Aplica as respostas do Chief e retoma a triagem da requisição."""
    if job_title:
        request.job_title = job_title
    if objective is not None:
        request.objective = objective
    if deliverables is not None:
        request.deliverables = {"items": list(deliverables)}
    if tools is not None:
        request.tools = {"items": list(tools)}
    if specialization is not None:
        constraints = dict(request.constraints)
        constraints["specialization"] = specialization
        request.constraints = constraints

    answers = list(_clarification_log(request))
    answers.append(
        {
            "answered_at": utcnow().isoformat(),
            "objective": request.objective,
            "deliverables": _items(request.deliverables),
        }
    )
    request.clarifications = {
        "questions": _clarification_questions(request),
        "answers": answers,
    }
    request.status = RequestStatus.CLARIFIED
    session.flush()

    intake = _intake_from(request)
    questions = screen(intake)
    if questions:
        return _ask_for_clarification(session, request, questions)

    return _process(session, nature, request, intake)


def _process(
    session: Session, nature: NatureManager, request: SubagentRequest, intake: HiringIntake
) -> HiringOutcome:
    """Classifica, submete à Natureza e materializa o subagente quando aprovado."""
    assessment = complexity_classifier.classify(
        " ".join([intake.job_title, intake.specialization, intake.objective, intake.raw_request]),
        requested_by=intake.requested_by,
        deliverables=len(intake.deliverables),
        tools=len(intake.tools),
    )
    complexity = intake.complexity or assessment.complexity
    request.complexity = complexity

    verdict = nature.evaluate_hiring(
        HiringRequest(
            requested_by=intake.requested_by.value,
            job_title=intake.job_title,
            complexity=complexity,
            requested_model=intake.requested_model,
        ),
        active_subagents=agent_service.count_active_subagents(session),
    )

    request.nature_decision = verdict.decision
    request.nature_narrative = verdict.narrative
    request.granted_model = verdict.granted_model
    request.queue_position = verdict.queue_position

    audit_service.record_event(
        session,
        event_type=AuditEventType.NATURE_DECISION,
        actor="NATURE",
        decision=verdict.decision.value,
        summary=f"{verdict.decision.value}: {intake.job_title}",
        narrative=verdict.narrative,
        resource_snapshot=verdict.snapshot.to_dict(),
        payload={
            "request_id": str(request.id),
            "requested_by": intake.requested_by.value,
            "complexity": complexity.value,
            "requested_model": intake.requested_model,
            "granted_model": verdict.granted_model,
            "reason": verdict.reason,
            "classification": assessment.to_dict(),
        },
    )

    if not verdict.allowed:
        request.status = (
            RequestStatus.QUEUED
            if verdict.decision is NatureDecision.QUEUED
            else RequestStatus.REJECTED
        )
        request.resolved_at = None if request.status is RequestStatus.QUEUED else utcnow()
        session.flush()
        return HiringOutcome(
            request=request, agent=None, verdict=verdict, narrative=verdict.narrative
        )

    profile, reused = _resolve_profile(session, request, intake, complexity, verdict)
    agent = _instantiate(session, request, intake, profile, verdict)

    request.status = RequestStatus.FULFILLED
    request.resolved_at = utcnow()
    request.talent_profile_id = profile.id
    request.reused_profile = reused
    request.created_agent_id = agent.id
    session.flush()

    return HiringOutcome(
        request=request,
        agent=agent,
        verdict=verdict,
        reused_profile=reused,
        narrative=verdict.narrative,
    )


def _resolve_profile(
    session: Session,
    request: SubagentRequest,
    intake: HiringIntake,
    complexity: TaskComplexity,
    verdict: HiringVerdict,
) -> tuple[TalentProfile, bool]:
    """Resgata o perfil do Banco de Talentos ou gera um metaprompt novo."""
    match = talent_bank.search(
        session, role_title=intake.job_title, specialization=intake.specialization
    )
    if match is not None:
        audit_service.record_event(
            session,
            event_type=AuditEventType.TALENT_PROFILE_REUSED,
            actor="RA",
            summary=f"Perfil reaproveitado: {match.profile.slug}",
            narrative=(
                f"O RA resgatou o perfil '{match.profile.role_title}' já existente no Banco "
                f"de Talentos (aderência {match.score:.0%}), poupando a redação de um novo "
                "metaprompt."
            ),
            payload={
                "request_id": str(request.id),
                "profile_id": str(match.profile.id),
                "matched_on": match.matched_on,
                "score": match.score,
                "version": match.profile.version,
            },
        )
        return match.profile, True

    metaprompt = prompt_factory.build_metaprompt(
        MetapromptSpec(
            job_title=intake.job_title,
            objective=intake.objective,
            complexity=complexity,
            reports_to=intake.requested_by,
            deliverables=intake.deliverables,
            tools=intake.tools,
            constraints=intake.constraints,
            specialization=intake.specialization,
        )
    )
    profile = talent_bank.create_profile(
        session,
        role_title=intake.job_title,
        specialization=intake.specialization,
        system_prompt=metaprompt,
        complexity=complexity,
        tools=list(intake.tools),
        recommended_model=verdict.granted_model,
    )
    audit_service.record_event(
        session,
        event_type=AuditEventType.TALENT_PROFILE_CREATED,
        actor="RA",
        summary=f"Novo perfil no Banco de Talentos: {profile.slug}",
        narrative=(
            f"O RA redigiu um metaprompt inédito para '{intake.job_title}' e o arquivou "
            "para futuras recontratações."
        ),
        payload={
            "request_id": str(request.id),
            "profile_id": str(profile.id),
            "complexity": complexity.value,
        },
    )
    return profile, False


def _instantiate(
    session: Session,
    request: SubagentRequest,
    intake: HiringIntake,
    profile: TalentProfile,
    verdict: HiringVerdict,
) -> Agent:
    """Cria o registro do subagente e o vincula ao Chief solicitante."""
    spec = model_catalog.get_model(verdict.granted_model or "") or model_catalog.lightest_model()
    agent = Agent(
        name=f"{intake.job_title} #{profile.usage_count + 1}",
        role=AgentRole.SUBAGENT,
        agent_type=AgentType.SUBAGENT,
        status=AgentStatus.IDLE,
        job_title=intake.job_title,
        system_prompt=profile.system_prompt,
        model_name=spec.name,
        estimated_ram_mb=spec.ram_mb,
        reports_to_id=request.requester_agent_id,
        talent_profile_id=profile.id,
        attributes={
            "request_id": str(request.id),
            "complexity": request.complexity.value,
            "talent_slug": profile.slug,
            "talent_version": profile.version,
            "nature_decision": verdict.decision.value,
        },
    )
    session.add(agent)
    session.flush()

    talent_bank.register_usage(
        session,
        profile,
        job_title=intake.job_title,
        requested_by=intake.requested_by.value,
        agent_id=agent.id,
        model_name=spec.name,
    )

    audit_service.record_event(
        session,
        event_type=AuditEventType.AGENT_CREATED,
        actor="RA",
        decision=verdict.decision.value,
        summary=f"Subagente contratado: {agent.name}",
        narrative=(
            f"{agent.name} foi admitido com {spec.display_name} e passa a reportar ao "
            f"{intake.requested_by.value}."
        ),
        agent_id=agent.id,
        payload={
            "request_id": str(request.id),
            "model": spec.name,
            "reports_to": intake.requested_by.value,
            "talent_profile_id": str(profile.id),
        },
    )
    logger.info(
        "ra.subagent_hired",
        job_title=intake.job_title,
        model=spec.name,
        reused_profile=request.reused_profile,
    )
    return agent


def _ask_for_clarification(
    session: Session, request: SubagentRequest, questions: tuple[str, ...]
) -> HiringOutcome:
    """Devolve o pedido ao Chief sem consumir recursos de infraestrutura."""
    request.status = RequestStatus.NEEDS_CLARIFICATION
    request.clarifications = {
        "questions": list(questions),
        "answers": list(_clarification_log(request)),
    }

    narrative = (
        f"O RA recusou-se a abrir a vaga de '{request.job_title}' sem antes esclarecer "
        f"{len(questions)} ponto(s) com o {request.requested_by_role.value}."
    )
    audit_service.record_event(
        session,
        event_type=AuditEventType.SUBAGENT_CLARIFICATION,
        actor="RA",
        summary=f"Esclarecimentos solicitados: {request.job_title}",
        narrative=narrative,
        payload={"request_id": str(request.id), "questions": list(questions)},
    )
    session.flush()
    logger.info("ra.clarification_requested", job_title=request.job_title, count=len(questions))
    return HiringOutcome(
        request=request, agent=None, verdict=None, questions=questions, narrative=narrative
    )


# --- Demissão ----------------------------------------------------------------


def dismiss_subagent(
    session: Session,
    agent: Agent,
    *,
    reason: str,
    final_report: str | None = None,
    rating: int | None = None,
) -> Agent:
    """Demite o subagente, liberando recursos e arquivando apenas o relatório final."""
    if agent.agent_type is not AgentType.SUBAGENT:
        msg = "Apenas subagentes podem ser demitidos."
        raise ValueError(msg)

    if final_report:
        session.add(
            CorporateMemory(
                memory_type=MemoryType.REPORT,
                title=f"Relatório final — {agent.job_title or agent.name}",
                content=final_report,
                author_agent_id=agent.id,
                author_role=AgentRole.SUBAGENT.value,
                importance=6,
                tags={"terms": ["relatorio", "subagente"], "reason": reason},
            )
        )

    if rating is not None and agent.talent_profile_id is not None:
        profile = session.get(TalentProfile, agent.talent_profile_id)
        if profile is not None:
            talent_bank.rate_profile(session, profile, rating=rating, feedback=reason)
            audit_service.record_event(
                session,
                event_type=AuditEventType.TALENT_PROFILE_RATED,
                actor="RA",
                summary=f"Perfil avaliado: {profile.slug}",
                narrative=(
                    f"O desempenho de {agent.name} rendeu nota {rating}/5 ao perfil "
                    f"'{profile.role_title}' (média {profile.average_rating})."
                ),
                agent_id=agent.id,
                payload={"profile_id": str(profile.id), "rating": rating},
            )

    agent.status = AgentStatus.TERMINATED
    agent.terminated_at = utcnow()
    # Libera a RAM contabilizada pela Natureza; o metaprompt permanece no Banco de Talentos.
    agent.estimated_ram_mb = 0
    agent.system_prompt = ""
    agent.attributes = {**agent.attributes, "dismissal_reason": reason}
    session.flush()

    audit_service.record_event(
        session,
        event_type=AuditEventType.AGENT_TERMINATED,
        actor="RA",
        summary=f"Subagente demitido: {agent.name}",
        narrative=(
            f"{agent.name} encerrou seu contrato ({reason}). A memória de trabalho foi "
            "liberada e apenas o relatório final permanece arquivado."
        ),
        agent_id=agent.id,
        payload={"reason": reason, "report_archived": bool(final_report)},
    )
    session.flush()
    logger.info("ra.subagent_dismissed", agent=agent.name, reason=reason)
    return agent


# --- Consultas ---------------------------------------------------------------


def get_request(session: Session, request_id: uuid.UUID) -> SubagentRequest | None:
    return session.get(SubagentRequest, request_id)


def list_requests(
    session: Session, *, status: RequestStatus | None = None, limit: int = 50
) -> list[SubagentRequest]:
    """Requisições mais recentes, opcionalmente filtradas por status."""
    stmt = select(SubagentRequest).order_by(SubagentRequest.created_at.desc()).limit(limit)
    if status is not None:
        stmt = stmt.where(SubagentRequest.status == status)
    return list(session.scalars(stmt))


# --- Auxiliares --------------------------------------------------------------


def _intake_from(request: SubagentRequest) -> HiringIntake:
    constraints = request.constraints or {}
    return HiringIntake(
        requested_by=request.requested_by_role,
        job_title=request.job_title,
        objective=request.objective,
        raw_request=request.raw_request,
        deliverables=tuple(_items(request.deliverables)),
        tools=tuple(_items(request.tools)),
        constraints=tuple(str(item) for item in constraints.get("items", [])),
        specialization=str(constraints.get("specialization") or ""),
        requested_model=request.requested_model,
    )


def _items(container: dict[str, object] | None) -> list[str]:
    raw = (container or {}).get("items", [])
    return [str(item) for item in raw] if isinstance(raw, list) else []


def _clarification_questions(request: SubagentRequest) -> list[str]:
    raw = (request.clarifications or {}).get("questions", [])
    return [str(item) for item in raw] if isinstance(raw, list) else []


def _clarification_log(request: SubagentRequest) -> list[dict[str, object]]:
    raw = (request.clarifications or {}).get("answers", [])
    return [dict(item) for item in raw] if isinstance(raw, list) else []
