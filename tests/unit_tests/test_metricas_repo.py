from __future__ import annotations

import pytest
from dotenv import load_dotenv

from agent.db.connection import get_connection, init_db
from agent.db import metricas_repo


class _NoCommitConnCtx:
    """Context manager wrapper to avoid auto-commit/close in repo functions."""

    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        return False


@pytest.fixture
def tx_db(monkeypatch):
    """Provide a transaction that is rolled back after each test."""
    load_dotenv()
    init_db()
    conn = get_connection()
    conn.execute("BEGIN")
    conn.execute("TRUNCATE TABLE avaliacao_log")

    monkeypatch.setattr(metricas_repo, "get_connection", lambda: _NoCommitConnCtx(conn))
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()


def test_metricas_banco_vazio(tx_db) -> None:
    assert metricas_repo.nota_media_por_sdr() == {}
    assert metricas_repo.taxa_aprovacao_primeira_tentativa_por_sdr() == {}
    assert metricas_repo.alertas_recentes() == []


def test_metricas_com_registros(tx_db) -> None:
    tx_db.execute(
        """
        INSERT INTO avaliacao_log (lead_id, sdr_origem, nota, tentativas, aprovado)
        VALUES
            (NULL, 'sdr_frios', 8.0, 1, true),
            (NULL, 'sdr_frios', 9.0, 1, true),
            (NULL, 'sdr_frios', 5.0, 3, false)
        """
    )

    medias = metricas_repo.nota_media_por_sdr()
    taxas = metricas_repo.taxa_aprovacao_primeira_tentativa_por_sdr()
    alertas = metricas_repo.alertas_recentes()

    assert medias["sdr_frios"] == 7.33
    assert taxas["sdr_frios"] == 66.7
    assert len(alertas) == 1
    assert alertas[0]["sdr_origem"] == "sdr_frios"
    assert float(alertas[0]["nota"]) == 5.0
    assert int(alertas[0]["tentativas"]) == 3


def test_nullif_sem_divisao_por_zero(tx_db) -> None:
    tx_db.execute(
        """
        INSERT INTO avaliacao_log (lead_id, sdr_origem, nota, tentativas, aprovado)
        VALUES
            (NULL, 'sdr_anuncios', 7.0, 2, true)
        """
    )

    taxas = metricas_repo.taxa_aprovacao_primeira_tentativa_por_sdr()

    assert "sdr_anuncios" in taxas
    assert taxas["sdr_anuncios"] == 0.0
