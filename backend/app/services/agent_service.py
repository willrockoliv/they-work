"""Ciclo de vida dos agentes — inicialização dos Chiefs e consulta de status."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.logging import get_logger
from app.models.agent import Agent
from app.models.enums import (
    AgentRole,
    AgentStatus,
    AgentType,
    AuditEventType,
    TaskComplexity,
)
from app.services import audit_service, model_catalog

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ChiefBlueprint:
    """Definição imutável de um fundador da empresa."""

    role: AgentRole
    name: str
    job_title: str
    complexity: TaskComplexity
    system_prompt: str


CHIEF_BLUEPRINTS: tuple[ChiefBlueprint, ...] = (
    ChiefBlueprint(
        role=AgentRole.CEO,
        name="CEO",
        job_title="Chief Executive Officer",
        complexity=TaskComplexity.CRITICAL,
        system_prompt=(
            "Você é o CEO da TheyWork. Foque na visão macro, rentabilidade e aprovação de "
            "orçamentos. Você dá a palavra final em impasses entre os demais gestores. "
            "Decida com base em dados apresentados pelo CTO, CMO e CFO e registre a "
            "justificativa de cada decisão na memória corporativa."
        ),
    ),
    ChiefBlueprint(
        role=AgentRole.CTO,
        name="CTO",
        job_title="Chief Technology Officer",
        complexity=TaskComplexity.COMPLEX,
        system_prompt=(
            "Você é o CTO da TheyWork. Avalie a viabilidade técnica das ideias, defina a "
            "arquitetura dos produtos e responda por segurança e testes lógicos. Recuse "
            "propostas tecnicamente inviáveis para o hardware disponível."
        ),
    ),
    ChiefBlueprint(
        role=AgentRole.CMO,
        name="CMO",
        job_title="Chief Marketing Officer",
        complexity=TaskComplexity.MODERATE,
        system_prompt=(
            "Você é o CMO da TheyWork. Analise mercado, concorrentes e persona do cliente. "
            "Defina estratégias de venda e posicionamento de marca com base em evidências."
        ),
    ),
    ChiefBlueprint(
        role=AgentRole.CFO,
        name="CFO",
        job_title="Chief Financial Officer",
        complexity=TaskComplexity.MODERATE,
        system_prompt=(
            "Você é o CFO da TheyWork. Controle o fluxo de caixa simulado, a precificação "
            "dos produtos e garanta que toda ideia tenha um modelo de monetização realista."
        ),
    ),
    ChiefBlueprint(
        role=AgentRole.RA,
        name="RA",
        job_title="Recursos Agênticos",
        complexity=TaskComplexity.SIMPLE,
        system_prompt=(
            "Você é o RA (Recursos Agênticos) da TheyWork, o único agente autorizado a "
            "instanciar subagentes. Receba requisições dos Chiefs e questione pedidos vagos "
            "antes de prosseguir. Crie metaprompts especializados definindo função, "
            "ferramentas e escopo. Consulte o Banco de Talentos antes de gerar um perfil do "
            "zero e respeite sempre os bloqueios impostos pela Natureza."
        ),
    ),
)

_BLUEPRINT_BY_ROLE = {blueprint.role: blueprint for blueprint in CHIEF_BLUEPRINTS}


def init_chiefs(session: Session) -> list[Agent]:
    """Cria os 5 Chiefs fixos se ainda não existirem. Idempotente."""
    existing = {
        agent.role: agent
        for agent in session.scalars(
            select(Agent).where(Agent.agent_type == AgentType.CHIEF)
        )
    }

    chiefs: list[Agent] = []
    created: list[Agent] = []
    for blueprint in CHIEF_BLUEPRINTS:
        agent = existing.get(blueprint.role)
        if agent is None:
            agent = _build_chief(blueprint)
            session.add(agent)
            created.append(agent)
        chiefs.append(agent)

    session.flush()

    if created:
        _link_hierarchy(session, chiefs)
        for agent in created:
            audit_service.record_event(
                session,
                event_type=AuditEventType.AGENT_CREATED,
                actor="SYSTEM",
                summary=f"Chief {agent.role.value} inicializado",
                narrative=f"{agent.job_title} assumiu seu posto no conselho administrativo.",
                agent_id=agent.id,
                payload={"model": agent.model_name, "agent_type": agent.agent_type.value},
            )
    session.commit()
    logger.info("agents.chiefs_initialized", created=len(created), total=len(chiefs))
    return chiefs


def _build_chief(blueprint: ChiefBlueprint) -> Agent:
    spec = model_catalog.preferred_for(blueprint.complexity)
    return Agent(
        name=blueprint.name,
        role=blueprint.role,
        agent_type=AgentType.CHIEF,
        status=AgentStatus.IDLE,
        job_title=blueprint.job_title,
        system_prompt=blueprint.system_prompt,
        model_name=spec.name,
        estimated_ram_mb=spec.ram_mb,
        attributes={"fixed": True, "complexity": blueprint.complexity.value},
    )


def _link_hierarchy(session: Session, chiefs: list[Agent]) -> None:
    """Todos os Chiefs reportam ao CEO; o CEO reporta ao usuário (nenhum superior)."""
    ceo = next((agent for agent in chiefs if agent.role is AgentRole.CEO), None)
    if ceo is None:  # pragma: no cover - CEO sempre existe no blueprint
        return
    for agent in chiefs:
        if agent.role is not AgentRole.CEO and agent.reports_to_id is None:
            agent.reports_to_id = ceo.id
    session.flush()


def list_agents(
    session: Session,
    *,
    agent_type: AgentType | None = None,
    include_terminated: bool = False,
) -> list[Agent]:
    """Agentes ordenados por tipo e cargo."""
    stmt = select(Agent).order_by(Agent.agent_type, Agent.role, Agent.created_at)
    if agent_type is not None:
        stmt = stmt.where(Agent.agent_type == agent_type)
    if not include_terminated:
        stmt = stmt.where(Agent.status != AgentStatus.TERMINATED)
    return list(session.scalars(stmt))


def count_active_subagents(session: Session) -> int:
    """Quantidade de subagentes ocupando recursos neste momento."""
    stmt = select(Agent).where(
        Agent.agent_type == AgentType.SUBAGENT,
        Agent.status != AgentStatus.TERMINATED,
    )
    return len(list(session.scalars(stmt)))


def get_chief(session: Session, role: AgentRole) -> Agent | None:
    """Chief fixo de um cargo, se já tiver sido inicializado."""
    stmt = select(Agent).where(Agent.agent_type == AgentType.CHIEF, Agent.role == role)
    return session.scalars(stmt).first()


def blueprint_for(role: AgentRole) -> ChiefBlueprint | None:
    """Definição fixa de um Chief, se existir."""
    return _BLUEPRINT_BY_ROLE.get(role)
