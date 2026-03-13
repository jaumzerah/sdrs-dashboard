"""Repository queries for SDR quality dashboard metrics."""

from __future__ import annotations

from typing import Any

from psycopg.rows import dict_row

from agent.db.connection import get_connection


def nota_media_por_sdr() -> dict[str, float]:
    """Return average score by SDR origin."""
    query = """
        SELECT sdr_origem, ROUND(AVG(nota)::numeric, 2) AS media
        FROM avaliacao_log
        GROUP BY sdr_origem
        ORDER BY sdr_origem
    """
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query)
            rows = cur.fetchall()

    if not rows:
        return {}
    return {str(row["sdr_origem"]): float(row["media"]) for row in rows}


def taxa_aprovacao_primeira_tentativa_por_sdr() -> dict[str, float]:
    """Return first-attempt approval rate (% ) by SDR origin."""
    query = """
        SELECT
          sdr_origem,
          ROUND(
            COUNT(*) FILTER (WHERE tentativas = 1 AND aprovado = true)::numeric
            / NULLIF(COUNT(*), 0) * 100, 1
          ) AS taxa
        FROM avaliacao_log
        GROUP BY sdr_origem
        ORDER BY sdr_origem
    """
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query)
            rows = cur.fetchall()

    if not rows:
        return {}
    return {str(row["sdr_origem"]): float(row["taxa"] or 0.0) for row in rows}


def alertas_recentes(limite: int = 20) -> list[dict[str, Any]]:
    """Return recent alerts sent without approval after 3 attempts."""
    query = """
        SELECT id, lead_id, sdr_origem, nota, tentativas, criado_em
        FROM avaliacao_log
        WHERE aprovado = false AND tentativas >= 3
        ORDER BY criado_em DESC
        LIMIT %(limite)s
    """
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, {"limite": int(limite)})
            rows = cur.fetchall()

    return [dict(row) for row in rows] if rows else []
