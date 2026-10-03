"""Banco de Talentos: busca, versionamento, uso e avaliação de perfis."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.models import TaskComplexity
from app.models.talent import TalentProfile
from app.services import talent_bank


def _criar(session: Session, **kwargs: object) -> TalentProfile:
    defaults: dict[str, object] = {
        "role_title": "Analista de Dados",
        "specialization": "métricas de produto",
        "system_prompt": "Você é um analista de dados.",
        "complexity": TaskComplexity.MODERATE,
        "tools": ["planilha"],
    }
    defaults.update(kwargs)
    return talent_bank.create_profile(session, **defaults)  # type: ignore[arg-type]


class TestSlugEKeywords:
    def test_slug_normaliza_acentos_e_espacos(self) -> None:
        assert talent_bank.slugify("Analista de Dados Sênior") == "analista-de-dados-senior"

    def test_slug_tem_fallback(self) -> None:
        assert talent_bank.slugify("!!!") == "perfil-sem-nome"

    def test_keywords_descartam_stopwords_e_duplicatas(self) -> None:
        termos = talent_bank.extract_keywords("Analista de Dados", "dados de mercado")

        assert "de" not in termos
        assert termos.count("dados") == 1


class TestBusca:
    def test_encontra_por_slug_exato(self, db_session: Session) -> None:
        perfil = _criar(db_session)

        match = talent_bank.search(db_session, role_title="Analista de Dados")

        assert match is not None
        assert match.profile.id == perfil.id
        assert match.matched_on == "slug"
        assert match.score == 1.0

    def test_encontra_por_palavras_chave_aproximadas(self, db_session: Session) -> None:
        _criar(db_session, role_title="Analista de Dados", specialization="métricas")

        match = talent_bank.search(
            db_session, role_title="Analista Dados", specialization="métricas"
        )

        assert match is not None
        assert match.matched_on == "keywords"
        assert match.score >= talent_bank.MIN_MATCH_SCORE

    def test_nao_encontra_perfil_sem_aderencia(self, db_session: Session) -> None:
        _criar(db_session)

        assert talent_bank.search(db_session, role_title="Redator Publicitario") is None

    def test_busca_vazia_sem_palavras_uteis(self, db_session: Session) -> None:
        _criar(db_session)

        assert talent_bank.search(db_session, role_title="de") is None


class TestVersionamento:
    def test_recriar_slug_gera_nova_versao_e_aposenta_anterior(
        self, db_session: Session
    ) -> None:
        primeiro = _criar(db_session)
        segundo = _criar(db_session, system_prompt="Prompt revisado.")

        assert segundo.version == 2
        assert segundo.supersedes_id == primeiro.id
        assert segundo.is_active is True
        assert primeiro.is_active is False

    def test_busca_retorna_apenas_a_versao_ativa(self, db_session: Session) -> None:
        _criar(db_session)
        atual = _criar(db_session, system_prompt="v2")

        match = talent_bank.search(db_session, role_title="Analista de Dados")

        assert match is not None
        assert match.profile.id == atual.id

    def test_historico_lista_todas_as_versoes(self, db_session: Session) -> None:
        _criar(db_session)
        _criar(db_session, system_prompt="v2")

        historico = talent_bank.version_history(db_session, "analista-de-dados")

        assert [perfil.version for perfil in historico] == [1, 2]

    def test_nova_versao_nao_herda_metricas(self, db_session: Session) -> None:
        primeiro = _criar(db_session)
        talent_bank.rate_profile(db_session, primeiro, rating=5)

        segundo = _criar(db_session, system_prompt="v2")

        assert segundo.rating_count == 0
        assert segundo.average_rating is None


class TestUsoEAvaliacao:
    def test_registra_uso_e_historico(self, db_session: Session) -> None:
        perfil = _criar(db_session)

        talent_bank.register_usage(
            db_session, perfil, job_title="Analista de Dados", requested_by="CTO"
        )

        assert perfil.usage_count == 1
        assert perfil.last_used_at is not None
        assert perfil.task_history["entries"][-1]["requested_by"] == "CTO"

    def test_historico_e_limitado(self, db_session: Session) -> None:
        perfil = _criar(db_session)

        for _ in range(talent_bank.MAX_HISTORY_ENTRIES + 5):
            talent_bank.register_usage(db_session, perfil, job_title="X", requested_by="CTO")

        assert len(perfil.task_history["entries"]) == talent_bank.MAX_HISTORY_ENTRIES

    def test_media_das_avaliacoes(self, db_session: Session) -> None:
        perfil = _criar(db_session)

        talent_bank.rate_profile(db_session, perfil, rating=4)
        talent_bank.rate_profile(db_session, perfil, rating=5, feedback="excelente")

        assert perfil.rating_count == 2
        assert perfil.average_rating == 4.5

    def test_avaliacao_fora_do_intervalo_e_rejeitada(self, db_session: Session) -> None:
        perfil = _criar(db_session)

        with pytest.raises(ValueError, match="entre 1 e 5"):
            talent_bank.rate_profile(db_session, perfil, rating=9)


class TestListagem:
    def test_lista_ignora_versoes_aposentadas(self, db_session: Session) -> None:
        _criar(db_session)
        _criar(db_session, system_prompt="v2")

        assert len(talent_bank.list_profiles(db_session)) == 1
        assert len(talent_bank.list_profiles(db_session, include_inactive=True)) == 2
