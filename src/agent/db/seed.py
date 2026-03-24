"""Seed helpers to load initial disparos from JSON into Postgres."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .connection import get_connection, init_db
from .disparos_repo import registrar_disparo
from .leads_repo import buscar_lead, criar_lead

SEED_JSON_PATH = Path(__file__).resolve().parents[3] / "data" / "leads_disparados.json"


def _load_seed_rows(seed_path: Path) -> list[dict[str, Any]]:
    if not seed_path.exists():
        return []
    data = json.loads(seed_path.read_text(encoding="utf-8"))
    leads = data.get("leads", [])
    if not isinstance(leads, list):
        return []
    return [row for row in leads if isinstance(row, dict)]


def _disparos_count() -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM disparos")
            row = cur.fetchone()
    return int(row[0]) if row else 0


def seed_disparos_if_empty(seed_path: Path | None = None) -> int:
    """Seed disparos table from JSON if it is currently empty.

    Returns number of inserted rows.
    """
    init_db()
    if _disparos_count() > 0:
        return 0

    path = seed_path or SEED_JSON_PATH
    rows = _load_seed_rows(path)
    inserted = 0

    for row in rows:
        lid = row.get("lid")
        jid = row.get("jid")
        numero = row.get("numero")
        campanha = row.get("campanha")
        numero_remetente = row.get("numero_remetente")
        if not campanha:
            continue

        lead = buscar_lead(lid=lid, jid=jid, numero=numero)
        if lead is None:
            lead = criar_lead(
                {
                    "lid": lid,
                    "jid": jid,
                    "numero": numero,
                    "usando_lid": bool(lid),
                }
            )

        registrar_disparo(
            lead_id=lead.get("id"),
            lid=lid,
            jid=jid,
            numero=numero,
            campanha=campanha,
            numero_remetente=numero_remetente,
        )
        inserted += 1

    return inserted


def main() -> None:
    """CLI entrypoint for DB seeding."""
    inserted = seed_disparos_if_empty()
    print(f"seed_disparos_if_empty: inserted={inserted}")


if __name__ == "__main__":
    main()
