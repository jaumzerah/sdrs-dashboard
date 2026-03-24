"""Repository helpers for disparos table operations."""

from __future__ import annotations

from typing import Any

from psycopg.rows import dict_row

from .connection import get_connection


def registrar_disparo(
    lead_id: str | None,
    lid: str | None,
    jid: str | None,
    numero: str | None,
    campanha: str,
    numero_remetente: str | None,
) -> dict[str, Any]:
    """Insert a disparo record and return inserted row."""
    if not campanha:
        raise ValueError("campanha e obrigatoria para registrar disparo")

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO disparos (lead_id, lid, jid, numero, campanha, numero_remetente)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (lead_id, lid, jid, numero, campanha, numero_remetente),
            )
            row = cur.fetchone()
        conn.commit()

    return dict(row or {})


def esta_na_base_disparados(
    lid: str | None = None,
    jid: str | None = None,
    numero: str | None = None,
) -> dict[str, Any] | None:
    """Find disparo with priority: LID -> JID -> numero."""
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            if lid:
                cur.execute(
                    """
                    SELECT * FROM disparos
                    WHERE lid = %s
                    ORDER BY disparado_em DESC
                    LIMIT 1
                    """,
                    (lid,),
                )
                row = cur.fetchone()
                if row:
                    return dict(row)

            if jid:
                cur.execute(
                    """
                    SELECT * FROM disparos
                    WHERE jid = %s
                    ORDER BY disparado_em DESC
                    LIMIT 1
                    """,
                    (jid,),
                )
                row = cur.fetchone()
                if row:
                    return dict(row)

            if numero:
                cur.execute(
                    """
                    SELECT * FROM disparos
                    WHERE numero = %s
                    ORDER BY disparado_em DESC
                    LIMIT 1
                    """,
                    (numero,),
                )
                row = cur.fetchone()
                if row:
                    return dict(row)

    return None
