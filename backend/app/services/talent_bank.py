"""Banco de Talentos — busca, versionamento e avaliação dos perfis do RA."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.logging import get_logger
from app.models.base import utcnow
from app.models.enums import TaskComplexity
from app.models.talent import TalentProfile
from app.services.complexity_classifier import normalize

logger = get_logger(__name__)

#: Palavras sem valor discriminante na busca por perfis.
_STOPWORDS: frozenset[str] = frozenset(
    {
        "de",
        "da",
        "do",
        "das",
        "dos",
        "para",
        "com",
        "em",
        "um",
        "uma",
        "e",
        "o",
        "a",
        "os",
        "as",
        "que",
        "ao",
        "no",
        "na",
        "por",
        "the",
    }
)

#: Similaridade mínima (Jaccard) para considerar um perfil reaproveitável.
MIN_MATCH_SCORE = 0.5

#: Máximo de execuções preservadas no histórico de um perfil.
MAX_HISTORY_ENTRIES = 20


@dataclass(frozen=True, slots=True)
class ProfileMatch:
    """Perfil candidato ao reaproveitamento, com o grau de aderência calculado."""

    profile: TalentProfile
    score: float
    matched_on: str


def slugify(value: str) -> str:
    """Identificador estável e legível para um cargo do Banco de Talentos."""
    normalized = normalize(value)
    slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    return slug[:160] or "perfil-sem-nome"


def extract_keywords(*parts: str) -> tuple[str, ...]:
    """Termos normalizados e deduplicados usados para casar perfis recorrentes."""
    tokens: list[str] = []
    for part in parts:
        for token in normalize(part).split():
            cleaned = re.sub(r"[^a-z0-9]", "", token)
            if len(cleaned) >= 3 and cleaned not in _STOPWORDS and cleaned not in tokens:
                tokens.append(cleaned)
    return tuple(tokens)


def find_by_slug(session: Session, slug: str) -> TalentProfile | None:
    """Versão ativa de um perfil, se existir."""
    stmt = (
        select(TalentProfile)
        .where(TalentProfile.slug == slug, TalentProfile.is_active.is_(True))
        .order_by(TalentProfile.version.desc())
    )
    return session.scalars(stmt).first()


def search(
    session: Session,
    *,
    role_title: str,
    specialization: str = "",
    complexity: TaskComplexity | None = None,
) -> ProfileMatch | None:
    """Procura um perfil reaproveitável — primeiro por slug, depois por palavras-chave.

    Evita que o RA gere um metaprompt do zero para uma vaga recorrente.
    """
    slug = slugify(role_title)
    exact = find_by_slug(session, slug)
    if exact is not None:
        return ProfileMatch(profile=exact, score=1.0, matched_on="slug")

    wanted = set(extract_keywords(role_title, specialization))
    if not wanted:
        return None

    best: ProfileMatch | None = None
    for profile in _active_profiles(session):
        if complexity is not None and profile.complexity is not complexity:
            continue
        stored = set(_keywords_of(profile))
        if not stored:
            continue
        score = len(wanted & stored) / len(wanted | stored)
        if score >= MIN_MATCH_SCORE and (best is None or score > best.score):
            best = ProfileMatch(profile=profile, score=round(score, 3), matched_on="keywords")
    return best


def create_profile(
    session: Session,
    *,
    role_title: str,
    specialization: str,
    system_prompt: str,
    complexity: TaskComplexity,
    tools: list[str] | None = None,
    recommended_model: str | None = None,
    created_by_role: str = "RA",
    keywords: tuple[str, ...] | None = None,
) -> TalentProfile:
    """Arquiva um novo metaprompt. Se o slug já existir, cria a próxima versão."""
    slug = slugify(role_title)
    previous = find_by_slug(session, slug)
    if previous is not None:
        return new_version(
            session,
            previous,
            system_prompt=system_prompt,
            specialization=specialization,
            complexity=complexity,
            tools=tools,
            recommended_model=recommended_model,
        )

    profile = TalentProfile(
        slug=slug,
        version=1,
        is_active=True,
        role_title=role_title,
        specialization=specialization,
        system_prompt=system_prompt,
        complexity=complexity,
        tools={"items": list(tools or [])},
        keywords={"terms": list(keywords or extract_keywords(role_title, specialization))},
        recommended_model=recommended_model,
        created_by_role=created_by_role,
        task_history={"entries": []},
    )
    session.add(profile)
    session.flush()
    logger.info("talent_bank.profile_created", slug=slug, complexity=complexity.value)
    return profile


def new_version(
    session: Session,
    profile: TalentProfile,
    *,
    system_prompt: str,
    specialization: str | None = None,
    complexity: TaskComplexity | None = None,
    tools: list[str] | None = None,
    recommended_model: str | None = None,
) -> TalentProfile:
    """Promove uma revisão do metaprompt, aposentando a versão anterior."""
    profile.is_active = False
    successor = TalentProfile(
        slug=profile.slug,
        version=profile.version + 1,
        is_active=True,
        supersedes_id=profile.id,
        role_title=profile.role_title,
        specialization=specialization if specialization is not None else profile.specialization,
        system_prompt=system_prompt,
        complexity=complexity or profile.complexity,
        tools={"items": list(tools)} if tools is not None else dict(profile.tools),
        keywords=dict(profile.keywords),
        recommended_model=recommended_model or profile.recommended_model,
        created_by_role=profile.created_by_role,
        # Métricas não são herdadas: cada versão é avaliada pelo próprio desempenho.
        task_history={"entries": []},
    )
    session.add(successor)
    session.flush()
    logger.info("talent_bank.profile_versioned", slug=profile.slug, version=successor.version)
    return successor


def register_usage(
    session: Session,
    profile: TalentProfile,
    *,
    job_title: str,
    requested_by: str,
    agent_id: uuid.UUID | None = None,
    model_name: str | None = None,
) -> TalentProfile:
    """Contabiliza mais uma contratação feita a partir deste perfil."""
    entry: dict[str, Any] = {
        "job_title": job_title,
        "requested_by": requested_by,
        "agent_id": str(agent_id) if agent_id else None,
        "model_name": model_name,
        "at": utcnow().isoformat(),
    }
    history = list(_history_of(profile))
    history.append(entry)
    profile.task_history = {"entries": history[-MAX_HISTORY_ENTRIES:]}
    profile.usage_count += 1
    profile.last_used_at = utcnow()
    session.flush()
    return profile


def rate_profile(
    session: Session, profile: TalentProfile, *, rating: int, feedback: str | None = None
) -> TalentProfile:
    """Registra a avaliação de desempenho (1 a 5) dada por um Chief."""
    if not 1 <= rating <= 5:
        msg = "rating deve estar entre 1 e 5"
        raise ValueError(msg)
    profile.rating_sum += rating
    profile.rating_count += 1
    if feedback:
        history = list(_history_of(profile))
        history.append({"feedback": feedback, "rating": rating, "at": utcnow().isoformat()})
        profile.task_history = {"entries": history[-MAX_HISTORY_ENTRIES:]}
    session.flush()
    logger.info(
        "talent_bank.profile_rated",
        slug=profile.slug,
        rating=rating,
        average=profile.average_rating,
    )
    return profile


def list_profiles(session: Session, *, include_inactive: bool = False) -> list[TalentProfile]:
    """Perfis arquivados, dos mais usados para os menos usados."""
    stmt = select(TalentProfile).order_by(
        TalentProfile.usage_count.desc(), TalentProfile.slug, TalentProfile.version.desc()
    )
    if not include_inactive:
        stmt = stmt.where(TalentProfile.is_active.is_(True))
    return list(session.scalars(stmt))


def version_history(session: Session, slug: str) -> list[TalentProfile]:
    """Todas as versões de um perfil, da mais antiga para a mais recente."""
    stmt = (
        select(TalentProfile)
        .where(TalentProfile.slug == slug)
        .order_by(TalentProfile.version.asc())
    )
    return list(session.scalars(stmt))


def _active_profiles(session: Session) -> list[TalentProfile]:
    stmt = select(TalentProfile).where(TalentProfile.is_active.is_(True))
    return list(session.scalars(stmt))


def _keywords_of(profile: TalentProfile) -> list[str]:
    terms = profile.keywords.get("terms", []) if profile.keywords else []
    return [str(term) for term in terms]


def _history_of(profile: TalentProfile) -> list[dict[str, Any]]:
    entries = profile.task_history.get("entries", []) if profile.task_history else []
    return [dict(entry) for entry in entries]
