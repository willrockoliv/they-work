"""Conselho administrativo — personas C-Level e resolução de impasses pelo CEO.

Cada Chief tem uma estrutura de raciocínio própria, determinística e auditável:
avalia a proposta sob a ótica da sua diretoria, devolve uma posição com confiança
e preocupações, e o CEO consolida o veredito final.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.logging import get_logger
from app.models.council import ChiefCommunication, ChiefProfile
from app.models.enums import (
    AgentRole,
    AuditEventType,
    CommunicationKind,
    CouncilOutcome,
    CouncilStance,
    TaskComplexity,
)
from app.services import agent_service, audit_service
from app.services.complexity_classifier import normalize

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Proposal:
    """Assunto submetido ao conselho."""

    topic: str
    description: str
    submitted_by: AgentRole = AgentRole.CEO
    context: dict[str, Any] = field(default_factory=dict)

    @property
    def haystack(self) -> str:
        return normalize(f"{self.topic} {self.description}")


@dataclass(frozen=True, slots=True)
class ChiefOpinion:
    """Parecer de um Chief sobre uma proposta."""

    role: AgentRole
    stance: CouncilStance
    confidence: int
    rationale: str
    concerns: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role.value,
            "stance": self.stance.value,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "concerns": list(self.concerns),
        }


@dataclass(frozen=True, slots=True)
class CouncilDecision:
    """Veredito consolidado da deliberação."""

    thread_id: uuid.UUID
    proposal: Proposal
    outcome: CouncilOutcome
    opinions: tuple[ChiefOpinion, ...]
    conditions: tuple[str, ...]
    narrative: str
    complexity: TaskComplexity

    def to_dict(self) -> dict[str, Any]:
        return {
            "thread_id": str(self.thread_id),
            "topic": self.proposal.topic,
            "outcome": self.outcome.value,
            "complexity": self.complexity.value,
            "opinions": [opinion.to_dict() for opinion in self.opinions],
            "conditions": list(self.conditions),
            "narrative": self.narrative,
        }


class ChiefAgent(ABC):
    """Base de raciocínio comum a todos os C-Level."""

    role: AgentRole
    headline: str
    mission: str
    reasoning_style: str
    objectives: tuple[str, ...] = ()
    decision_criteria: tuple[str, ...] = ()
    priority: int = 5
    default_complexity: TaskComplexity = TaskComplexity.MODERATE

    @abstractmethod
    def analyze(self, proposal: Proposal) -> ChiefOpinion:
        """Produz o parecer do Chief sobre a proposta."""

    def blueprint(self) -> dict[str, Any]:
        """Dados do perfil persistidos em `chief_profiles`."""
        return {
            "role": self.role,
            "headline": self.headline,
            "mission": self.mission,
            "reasoning_style": self.reasoning_style,
            "objectives": {"items": list(self.objectives)},
            "decision_criteria": {"items": list(self.decision_criteria)},
            "priority": self.priority,
            "default_complexity": self.default_complexity,
        }

    @staticmethod
    def _mentions(proposal: Proposal, terms: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(term for term in terms if term in proposal.haystack)


_INFEASIBLE_SIGNALS: tuple[str, ...] = (
    "treinar modelo",
    "fine-tuning",
    "cluster",
    "nuvem",
    "kubernetes",
    "gpu dedicada",
    "milhoes de usuarios",
    "escala global",
    "tempo real massivo",
)
_SECURITY_SIGNALS: tuple[str, ...] = ("dados sensiveis", "senha", "pagamento", "pessoais", "pii")
_MARKET_SIGNALS: tuple[str, ...] = ("mercado", "cliente", "publico", "persona", "concorrente")
_CHANNEL_SIGNALS: tuple[str, ...] = ("marca", "campanha", "canal", "posicionamento", "lancamento")
_REVENUE_SIGNALS: tuple[str, ...] = (
    "receita",
    "preco",
    "assinatura",
    "monetizacao",
    "margem",
    "faturamento",
    "licenca",
)
_COST_SIGNALS: tuple[str, ...] = ("custo", "investimento", "orcamento", "caixa", "despesa")
_STRATEGIC_SIGNALS: tuple[str, ...] = ("estrategia", "visao", "longo prazo", "pivotar", "mercado")


class CEOAgent(ChiefAgent):
    """Visão macro, aprovação de orçamentos e palavra final em impasses."""

    role = AgentRole.CEO
    headline = "Chief Executive Officer"
    mission = (
        "Garantir que a empresa persiga um modelo de negócio viável e rentável, mediando "
        "conflitos entre as diretorias e dando a palavra final em impasses."
    )
    reasoning_style = (
        "Pondera os pareceres do CTO, CMO e CFO, pesa risco contra retorno e decide mesmo "
        "sob informação incompleta, registrando a justificativa."
    )
    objectives = (
        "Definir e sustentar a visão de longo prazo da empresa",
        "Aprovar orçamentos e priorizar iniciativas",
        "Resolver impasses entre as diretorias",
    )
    decision_criteria = (
        "Veto técnico do CTO é bloqueante",
        "Proposta sem monetização só avança com condições do CFO",
        "Empate é decidido a favor do menor risco de caixa",
    )
    priority = 10
    default_complexity = TaskComplexity.CRITICAL

    def analyze(self, proposal: Proposal) -> ChiefOpinion:
        strategic = self._mentions(proposal, _STRATEGIC_SIGNALS)
        concerns: list[str] = []
        if not strategic:
            concerns.append("A proposta não conecta a iniciativa à estratégia da empresa.")
        stance = CouncilStance.APPROVE if strategic else CouncilStance.ABSTAIN
        return ChiefOpinion(
            role=self.role,
            stance=stance,
            confidence=7 if strategic else 4,
            rationale=(
                "Alinhamento estratégico identificado: " + ", ".join(strategic)
                if strategic
                else "Sem evidência de alinhamento estratégico; aguardo os pareceres técnicos."
            ),
            concerns=tuple(concerns),
        )


class CTOAgent(ChiefAgent):
    """Viabilidade técnica, arquitetura, segurança e testes."""

    role = AgentRole.CTO
    headline = "Chief Technology Officer"
    mission = (
        "Assegurar que tudo o que a empresa constrói é tecnicamente viável dentro do "
        "hardware disponível, seguro e testável."
    )
    reasoning_style = (
        "Parte das restrições físicas da infraestrutura, identifica o caminho de menor "
        "complexidade e veta o que não cabe no orçamento computacional."
    )
    objectives = (
        "Definir a arquitetura dos produtos",
        "Vetar propostas inviáveis para o hardware disponível",
        "Garantir cobertura de testes e segurança",
    )
    decision_criteria = (
        "Nada que exija treinamento de modelos ou infraestrutura em nuvem",
        "Toda entrega precisa de plano de testes",
        "Dados sensíveis exigem revisão de segurança explícita",
    )
    priority = 8
    default_complexity = TaskComplexity.COMPLEX

    def analyze(self, proposal: Proposal) -> ChiefOpinion:
        blockers = self._mentions(proposal, _INFEASIBLE_SIGNALS)
        security = self._mentions(proposal, _SECURITY_SIGNALS)
        concerns: tuple[str, ...] = (
            ("Há dados sensíveis envolvidos: exige revisão de segurança antes do primeiro "
             "commit.",)
            if security
            else ()
        )
        if blockers:
            return ChiefOpinion(
                role=self.role,
                stance=CouncilStance.REJECT,
                confidence=9,
                rationale=(
                    "Inviável para a infraestrutura atual (16 GB de RAM, 4 GB de VRAM): "
                    + ", ".join(blockers)
                ),
                concerns=concerns,
            )
        return ChiefOpinion(
            role=self.role,
            stance=CouncilStance.APPROVE,
            confidence=6 if security else 8,
            rationale="Escopo compatível com a infraestrutura local e com o stack existente.",
            concerns=concerns,
        )


class CMOAgent(ChiefAgent):
    """Mercado, concorrência, persona do cliente e posicionamento."""

    role = AgentRole.CMO
    headline = "Chief Marketing Officer"
    mission = (
        "Garantir que cada produto tenha um público definido, um posicionamento claro e "
        "uma estratégia de aquisição realista."
    )
    reasoning_style = (
        "Busca evidências de demanda e de diferenciação; sem persona definida, trata a "
        "proposta como hipótese não validada."
    )
    objectives = (
        "Mapear persona e dor do cliente",
        "Analisar concorrentes e posicionamento",
        "Definir canais de aquisição",
    )
    decision_criteria = (
        "Proposta sem público-alvo explícito não é aprovada",
        "Diferenciação precisa ser verificável",
    )
    priority = 6
    default_complexity = TaskComplexity.MODERATE

    def analyze(self, proposal: Proposal) -> ChiefOpinion:
        market = self._mentions(proposal, _MARKET_SIGNALS)
        channels = self._mentions(proposal, _CHANNEL_SIGNALS)
        if not market:
            return ChiefOpinion(
                role=self.role,
                stance=CouncilStance.REJECT,
                confidence=7,
                rationale="Nenhum público-alvo ou dor de cliente identificável na proposta.",
                concerns=("Persona do cliente indefinida.",),
            )
        concerns = () if channels else ("Canal de aquisição não especificado.",)
        return ChiefOpinion(
            role=self.role,
            stance=CouncilStance.APPROVE,
            confidence=8 if channels else 6,
            rationale="Há sinais de demanda: " + ", ".join(market),
            concerns=concerns,
        )


class CFOAgent(ChiefAgent):
    """Fluxo de caixa, precificação e monetização."""

    role = AgentRole.CFO
    headline = "Chief Financial Officer"
    mission = (
        "Proteger o caixa simulado da empresa e garantir que toda iniciativa tenha um "
        "modelo de monetização realista."
    )
    reasoning_style = (
        "Compara custo estimado contra receita projetada; na ausência de receita, aprova "
        "apenas sob condições explícitas de contenção."
    )
    objectives = (
        "Manter o fluxo de caixa positivo",
        "Definir a precificação dos produtos",
        "Rejeitar iniciativas sem retorno projetado",
    )
    decision_criteria = (
        "Sem modelo de monetização não há aprovação plena",
        "Custo declarado acima do orçamento aprovado é bloqueante",
    )
    priority = 7
    default_complexity = TaskComplexity.MODERATE

    def analyze(self, proposal: Proposal) -> ChiefOpinion:
        revenue = self._mentions(proposal, _REVENUE_SIGNALS)
        costs = self._mentions(proposal, _COST_SIGNALS)
        if not revenue:
            return ChiefOpinion(
                role=self.role,
                stance=CouncilStance.REJECT,
                confidence=8,
                rationale="A proposta não apresenta como a empresa ganha dinheiro com ela.",
                concerns=("Modelo de monetização ausente.",),
            )
        concerns = () if costs else ("Custo de execução não estimado.",)
        return ChiefOpinion(
            role=self.role,
            stance=CouncilStance.APPROVE,
            confidence=8 if costs else 6,
            rationale="Receita projetada identificada: " + ", ".join(revenue),
            concerns=concerns,
        )


class RAAgent(ChiefAgent):
    """Recursos Agênticos — não delibera sobre produto, apenas sobre capacidade."""

    role = AgentRole.RA
    headline = "Recursos Agênticos"
    mission = (
        "Ser o único agente autorizado a instanciar subagentes, traduzindo requisições dos "
        "Chiefs em metaprompts especializados dentro dos limites da Natureza."
    )
    reasoning_style = (
        "Recusa pedidos vagos, consulta o Banco de Talentos antes de redigir qualquer "
        "metaprompt e respeita integralmente os vetos da Natureza."
    )
    objectives = (
        "Estruturar requisições de contratação",
        "Reaproveitar perfis do Banco de Talentos",
        "Respeitar o orçamento de infraestrutura",
    )
    decision_criteria = (
        "Pedido vago é devolvido ao Chief com perguntas",
        "Perfil existente tem precedência sobre metaprompt novo",
    )
    priority = 4
    default_complexity = TaskComplexity.SIMPLE

    def analyze(self, proposal: Proposal) -> ChiefOpinion:
        return ChiefOpinion(
            role=self.role,
            stance=CouncilStance.ABSTAIN,
            confidence=5,
            rationale="O RA não delibera sobre produto; aguarda a requisição de contratação.",
        )


CHIEF_AGENTS: tuple[ChiefAgent, ...] = (
    CEOAgent(),
    CTOAgent(),
    CMOAgent(),
    CFOAgent(),
    RAAgent(),
)

_BY_ROLE: dict[AgentRole, ChiefAgent] = {chief.role: chief for chief in CHIEF_AGENTS}

#: Chiefs que efetivamente votam numa deliberação de produto.
VOTING_ROLES: tuple[AgentRole, ...] = (AgentRole.CTO, AgentRole.CMO, AgentRole.CFO)


def get_chief_agent(role: AgentRole) -> ChiefAgent | None:
    """Persona de um cargo do conselho."""
    return _BY_ROLE.get(role)


# --- Perfis persistidos ------------------------------------------------------


def init_profiles(session: Session) -> list[ChiefProfile]:
    """Materializa os perfis das personas em `chief_profiles`. Idempotente."""
    existing = {profile.role: profile for profile in session.scalars(select(ChiefProfile))}
    profiles: list[ChiefProfile] = []
    for chief in CHIEF_AGENTS:
        profile = existing.get(chief.role)
        agent = agent_service.get_chief(session, chief.role)
        if profile is None:
            profile = ChiefProfile(**chief.blueprint(), context_memory={"facts": []})
            session.add(profile)
        profile.agent_id = agent.id if agent else profile.agent_id
        profiles.append(profile)
    session.flush()
    logger.info("council.profiles_initialized", total=len(profiles))
    return profiles


def remember(session: Session, role: AgentRole, fact: str, *, importance: int = 5) -> ChiefProfile:
    """Acrescenta um fato à memória de contexto corporativo do Chief."""
    profile = session.scalars(select(ChiefProfile).where(ChiefProfile.role == role)).first()
    if profile is None:
        msg = f"Perfil do Chief {role.value} não inicializado."
        raise ValueError(msg)
    facts = list(profile.context_memory.get("facts", []))
    facts.append({"fact": fact, "importance": importance})
    # Mantém a memória enxuta: o contexto é reinjetado a cada deliberação.
    profile.context_memory = {"facts": facts[-25:]}
    session.flush()
    return profile


# --- Deliberação -------------------------------------------------------------


def deliberate(session: Session, proposal: Proposal) -> CouncilDecision:
    """Coleta os pareceres das diretorias e consolida o veredito do CEO."""
    thread_id = uuid.uuid4()
    opinions: list[ChiefOpinion] = []

    _record(
        session,
        thread_id,
        kind=CommunicationKind.DIRECTIVE,
        from_role=proposal.submitted_by,
        to_role=None,
        topic=proposal.topic,
        content=proposal.description,
    )

    for role in VOTING_ROLES:
        chief = _BY_ROLE[role]
        opinion = chief.analyze(proposal)
        opinions.append(opinion)
        _record(
            session,
            thread_id,
            kind=CommunicationKind.ANALYSIS,
            from_role=role,
            to_role=AgentRole.CEO,
            topic=proposal.topic,
            content=opinion.rationale,
            verdict=opinion.stance.value,
            confidence=opinion.confidence,
            payload={"concerns": list(opinion.concerns)},
        )

    ceo_opinion = _BY_ROLE[AgentRole.CEO].analyze(proposal)
    outcome, conditions, narrative = _resolve(proposal, opinions, ceo_opinion)
    opinions.append(ceo_opinion)

    _record(
        session,
        thread_id,
        kind=CommunicationKind.DECISION,
        from_role=AgentRole.CEO,
        to_role=None,
        topic=proposal.topic,
        content=narrative,
        rationale=ceo_opinion.rationale,
        verdict=outcome.value,
        confidence=ceo_opinion.confidence,
        payload={"conditions": list(conditions)},
    )

    complexity = (
        TaskComplexity.CRITICAL
        if outcome is CouncilOutcome.APPROVED_WITH_CONDITIONS
        else _BY_ROLE[AgentRole.CEO].default_complexity
    )
    decision = CouncilDecision(
        thread_id=thread_id,
        proposal=proposal,
        outcome=outcome,
        opinions=tuple(opinions),
        conditions=conditions,
        narrative=narrative,
        complexity=complexity,
    )

    audit_service.record_event(
        session,
        event_type=AuditEventType.COUNCIL_DELIBERATION,
        actor=AgentRole.CEO.value,
        decision=outcome.value,
        summary=f"{outcome.value}: {proposal.topic}",
        narrative=narrative,
        payload=decision.to_dict(),
    )
    session.flush()
    logger.info("council.deliberated", topic=proposal.topic, outcome=outcome.value)
    return decision


def _resolve(
    proposal: Proposal, opinions: list[ChiefOpinion], ceo_opinion: ChiefOpinion
) -> tuple[CouncilOutcome, tuple[str, ...], str]:
    """Aplica os critérios de decisão do CEO sobre os pareceres das diretorias."""
    by_role = {opinion.role: opinion for opinion in opinions}
    conditions = tuple(
        concern for opinion in opinions for concern in opinion.concerns
    ) + ceo_opinion.concerns

    cto = by_role.get(AgentRole.CTO)
    if cto is not None and cto.stance is CouncilStance.REJECT:
        return (
            CouncilOutcome.REJECTED,
            conditions,
            (
                f"O CEO acatou o veto técnico do CTO sobre '{proposal.topic}': {cto.rationale} "
                "A proposta foi arquivada."
            ),
        )

    approvals = [o for o in opinions if o.stance is CouncilStance.APPROVE]
    rejections = [o for o in opinions if o.stance is CouncilStance.REJECT]

    if not rejections:
        return (
            CouncilOutcome.APPROVED if not conditions else CouncilOutcome.APPROVED_WITH_CONDITIONS,
            conditions,
            (
                f"O conselho aprovou '{proposal.topic}' por unanimidade das diretorias "
                f"presentes ({len(approvals)} parecer(es) favorável(is))."
                + (f" Pendências a sanar: {len(conditions)}." if conditions else "")
            ),
        )

    if len(approvals) > len(rejections):
        return (
            CouncilOutcome.APPROVED_WITH_CONDITIONS,
            conditions,
            (
                f"O CEO desempatou a favor de '{proposal.topic}' ({len(approvals)} a favor, "
                f"{len(rejections)} contra), condicionando a execução à resolução das "
                f"{len(conditions)} ressalva(s) levantada(s)."
            ),
        )

    blockers = "; ".join(o.rationale for o in rejections)
    return (
        CouncilOutcome.REJECTED,
        conditions,
        (
            f"O CEO rejeitou '{proposal.topic}' diante de {len(rejections)} parecer(es) "
            f"contrário(s): {blockers}"
        ),
    )


def _record(
    session: Session,
    thread_id: uuid.UUID,
    *,
    kind: CommunicationKind,
    from_role: AgentRole,
    to_role: AgentRole | None,
    topic: str,
    content: str,
    rationale: str | None = None,
    verdict: str | None = None,
    confidence: int = 5,
    payload: dict[str, Any] | None = None,
) -> ChiefCommunication:
    """Persiste uma fala do conselho e espelha o evento na trilha de auditoria."""
    message = ChiefCommunication(
        thread_id=thread_id,
        kind=kind,
        from_role=from_role,
        to_role=to_role,
        topic=topic[:255],
        content=content,
        rationale=rationale,
        verdict=verdict,
        confidence=confidence,
        payload=payload or {},
    )
    session.add(message)
    audit_service.record_event(
        session,
        event_type=AuditEventType.CHIEF_COMMUNICATION,
        actor=from_role.value,
        decision=verdict,
        summary=f"{from_role.value} · {kind.value}: {topic}",
        narrative=content,
        payload={"thread_id": str(thread_id), "to_role": to_role.value if to_role else None},
    )
    return message


def list_communications(
    session: Session, *, thread_id: uuid.UUID | None = None, limit: int = 50
) -> list[ChiefCommunication]:
    """Comunicações do conselho, da mais recente para a mais antiga."""
    stmt = (
        select(ChiefCommunication)
        .order_by(ChiefCommunication.created_at.desc(), ChiefCommunication.id)
        .limit(limit)
    )
    if thread_id is not None:
        stmt = stmt.where(ChiefCommunication.thread_id == thread_id)
    return list(session.scalars(stmt))


def list_profiles(session: Session) -> list[ChiefProfile]:
    """Perfis persistidos das personas, ordenados por prioridade."""
    stmt = select(ChiefProfile).order_by(ChiefProfile.priority.desc())
    return list(session.scalars(stmt))
