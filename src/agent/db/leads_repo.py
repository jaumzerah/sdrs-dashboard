"""Repository helpers for leads table operations."""

from __future__ import annotations

from typing import Any

from psycopg import sql
from psycopg.rows import dict_row

from .connection import get_connection

ALLOWED_FIELDS = {
    "lid",
    "jid",
    "numero",
    "usando_lid",
    "nome",
    "email",
    "origem",
    "plataforma",
    "campanha",
    "canal",
    "chatwoot_contact_id",
}


def _sanitize_fields(dados: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in dados.items() if k in ALLOWED_FIELDS}


def buscar_lead(lid: str | None = None, jid: str | None = None, numero: str | None = None) -> dict[str, Any] | None:
    """Find lead by LID first, then JID, then number."""
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            if lid:
                cur.execute("SELECT * FROM leads WHERE lid = %s LIMIT 1", (lid,))
                row = cur.fetchone()
                if row:
                    return dict(row)

            if jid:
                cur.execute("SELECT * FROM leads WHERE jid = %s LIMIT 1", (jid,))
                row = cur.fetchone()
                if row:
                    return dict(row)

            if numero:
                cur.execute("SELECT * FROM leads WHERE numero = %s LIMIT 1", (numero,))
                row = cur.fetchone()
                if row:
                    return dict(row)

    return None


def criar_lead(dados: dict[str, Any]) -> dict[str, Any]:
    """Insert lead row and return inserted record."""
    clean = _sanitize_fields(dados)
    if "lid" in clean and clean.get("lid") and "usando_lid" not in clean:
        clean["usando_lid"] = True

    if not clean:
        raise ValueError("Nenhum campo valido para criar lead")

    fields = list(clean.keys())
    values = [clean[k] for k in fields]

    query = sql.SQL("INSERT INTO leads ({fields}) VALUES ({values}) RETURNING *").format(
        fields=sql.SQL(", ").join(sql.Identifier(field) for field in fields),
        values=sql.SQL(", ").join(sql.Placeholder() for _ in fields),
    )

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, values)
            row = cur.fetchone()
        conn.commit()

    return dict(row or {})


def atualizar_lead(lead_id: str, dados: dict[str, Any]) -> dict[str, Any]:
    """Update lead and return updated row.

    If a new LID arrives for a lead that had only JID, this function marks
    `usando_lid=True` automatically.
    """
    clean = _sanitize_fields(dados)
    if not clean:
        raise ValueError("Nenhum campo valido para atualizar lead")

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM leads WHERE id = %s LIMIT 1", (lead_id,))
            current = cur.fetchone()
            if not current:
                raise ValueError(f"Lead nao encontrado: {lead_id}")

            if clean.get("lid") and not current.get("lid"):
                clean["usando_lid"] = True

            set_parts = [
                sql.SQL("{} = {}").format(sql.Identifier(field), sql.Placeholder())
                for field in clean.keys()
            ]
            values = list(clean.values())

            update_query = sql.SQL(
                "UPDATE leads SET {set_clause}, atualizado_em = NOW() WHERE id = %s RETURNING *"
            ).format(set_clause=sql.SQL(", ").join(set_parts))

            cur.execute(update_query, [*values, lead_id])
            updated = cur.fetchone()
        conn.commit()

    return dict(updated or {})
