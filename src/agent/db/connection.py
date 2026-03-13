"""Postgres connection helpers and DB initialization."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from psycopg import Connection, connect


def get_database_url() -> str:
    """Return DATABASE_URL from environment."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL nao configurado")
    return database_url


def get_connection(database_url: str | None = None) -> Connection[Any]:
    """Create and return a psycopg connection."""
    url = database_url or get_database_url()
    return connect(url)


def init_db(database_url: str | None = None) -> None:
    """Initialize database objects using schema.sql.

    The schema is idempotent (`IF NOT EXISTS`), so running this multiple
    times is safe.
    """
    schema_path = Path(__file__).with_name("schema.sql")
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema não encontrado em {schema_path}")

    schema_sql = schema_path.read_text(encoding="utf-8")
    with get_connection(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(schema_sql)
        conn.commit()
