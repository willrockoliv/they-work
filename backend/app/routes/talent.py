"""Endpoints do Banco de Talentos."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from app.models.talent import TalentProfile
from app.routes.deps import DbSession
from app.schemas.talent import (
    TalentBankResponse,
    TalentProfileRead,
    TalentRatingRequest,
    TalentSearchResponse,
)
from app.services import talent_bank

router = APIRouter(prefix="/talent", tags=["banco de talentos"])


@router.get("/profiles", response_model=TalentBankResponse, summary="Perfis disponíveis")
def list_profiles(session: DbSession, include_inactive: bool = False) -> TalentBankResponse:
    profiles = talent_bank.list_profiles(session, include_inactive=include_inactive)
    return TalentBankResponse(
        total=len(profiles),
        profiles=[TalentProfileRead.model_validate(profile) for profile in profiles],
    )


@router.get(
    "/profiles/search",
    response_model=TalentSearchResponse,
    summary="Procura um perfil reaproveitável",
)
def search_profile(
    session: DbSession, role_title: str, specialization: str = ""
) -> TalentSearchResponse:
    """Mesma busca que o RA executa antes de redigir um metaprompt novo."""
    match = talent_bank.search(session, role_title=role_title, specialization=specialization)
    if match is None:
        return TalentSearchResponse(found=False)
    return TalentSearchResponse(
        found=True,
        matched_on=match.matched_on,
        score=match.score,
        profile=TalentProfileRead.model_validate(match.profile),
    )


@router.get(
    "/profiles/{slug}/versions",
    response_model=TalentBankResponse,
    summary="Histórico de versões de um perfil",
)
def version_history(slug: str, session: DbSession) -> TalentBankResponse:
    profiles = talent_bank.version_history(session, slug)
    if not profiles:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Perfil não encontrado.")
    return TalentBankResponse(
        total=len(profiles),
        profiles=[TalentProfileRead.model_validate(profile) for profile in profiles],
    )


@router.post(
    "/profiles/{profile_id}/rating",
    response_model=TalentProfileRead,
    summary="Avalia o desempenho de um perfil",
)
def rate_profile(
    profile_id: uuid.UUID, payload: TalentRatingRequest, session: DbSession
) -> TalentProfileRead:
    profile = session.get(TalentProfile, profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Perfil não encontrado.")
    talent_bank.rate_profile(session, profile, rating=payload.rating, feedback=payload.feedback)
    session.commit()
    return TalentProfileRead.model_validate(profile)
