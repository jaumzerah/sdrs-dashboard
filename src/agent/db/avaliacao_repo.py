"""Repository for evaluator quality metrics."""

from __future__ import annotations

from typing import Any

from psycopg.rows import dict_row

from agent.db.connection import get_connection


def registrar_avaliacao(
    lead_id: str | None,
    sdr_origem: str,
    nota: float,
    tentativas: int,
    aprovado: bool,
) -> dict[str, Any]:
    """Persist evaluator log row and return inserted record."""
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO avaliacao_log (lead_id, sdr_origem, nota, tentativas, aprovado)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING *
                """,
                (lead_id, sdr_origem, float(nota), int(tentativas), bool(aprovado)),
            )
            row = cur.fetchone()
        conn.commit()
    return dict(row or {})
