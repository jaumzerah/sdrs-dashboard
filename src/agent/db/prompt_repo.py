"""Repository helpers for prompt versioning and audit."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from psycopg.rows import dict_row

from src.agent.db.connection import get_connection


@dataclass(frozen=True)
class PromptVersion:
    """Domain object for prompt versions."""

    prompt_key: str
    version: int
    content: str
    status: str
    created_by: str
    notes: str | None
    created_at: datetime
    published_at: datetime | None
    rollback_of: int | None


def _ensure_prompt_tables() -> None:
    """Create prompt tables when schema migration was not executed yet."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS prompt_versions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    prompt_key TEXT NOT NULL,
                    version INT NOT NULL,
                    content TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'draft',
                    created_by TEXT NOT NULL DEFAULT 'system',
                    notes TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    published_at TIMESTAMPTZ,
                    rollback_of INT,
                    UNIQUE (prompt_key, version)
                )
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_prompt_versions_key_created ON prompt_versions(prompt_key, created_at DESC)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_prompt_versions_key_status ON prompt_versions(prompt_key, status)"
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS prompt_audit_log (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    prompt_key TEXT NOT NULL,
                    action TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    from_version INT,
                    to_version INT,
                    reason TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_prompt_audit_key_created ON prompt_audit_log(prompt_key, created_at DESC)"
            )
        conn.commit()


def _next_version(prompt_key: str) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(MAX(version), 0) FROM prompt_versions WHERE prompt_key = %s", (prompt_key,))
            row = cur.fetchone()
    return int(row[0] if row else 0) + 1


def _insert_audit(
    prompt_key: str,
    action: str,
    actor: str,
    from_version: int | None,
    to_version: int | None,
    reason: str | None,
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO prompt_audit_log (prompt_key, action, actor, from_version, to_version, reason)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (prompt_key, action, actor, from_version, to_version, reason),
            )
        conn.commit()


def _row_to_prompt(row: dict[str, Any]) -> PromptVersion:
    return PromptVersion(
        prompt_key=str(row["prompt_key"]),
        version=int(row["version"]),
        content=str(row["content"]),
        status=str(row["status"]),
        created_by=str(row["created_by"]),
        notes=str(row["notes"]) if row.get("notes") is not None else None,
        created_at=row["created_at"],
        published_at=row.get("published_at"),
        rollback_of=int(row["rollback_of"]) if row.get("rollback_of") is not None else None,
    )


def ensure_prompt_exists(prompt_key: str, content: str, actor: str = "system") -> PromptVersion:
    """Insert an initial published prompt if this key has no rows yet."""
    _ensure_prompt_tables()
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM prompt_versions WHERE prompt_key = %s ORDER BY version DESC LIMIT 1", (prompt_key,))
            existing = cur.fetchone()
            if existing:
                return _row_to_prompt(dict(existing))

            cur.execute(
                """
                INSERT INTO prompt_versions (prompt_key, version, content, status, created_by, notes, published_at)
                VALUES (%s, 1, %s, 'published', %s, %s, NOW())
                RETURNING *
                """,
                (prompt_key, content, actor, "initial seed"),
            )
            created = cur.fetchone()
        conn.commit()

    _insert_audit(prompt_key, "seed", actor, None, 1, "initial seed")
    return _row_to_prompt(dict(created or {}))


def get_published_prompt(prompt_key: str) -> PromptVersion | None:
    """Return the currently published prompt for a key."""
    _ensure_prompt_tables()
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT *
                FROM prompt_versions
                WHERE prompt_key = %s AND status = 'published'
                ORDER BY version DESC
                LIMIT 1
                """,
                (prompt_key,),
            )
            row = cur.fetchone()
    return _row_to_prompt(dict(row)) if row else None


def create_draft(prompt_key: str, content: str, actor: str, notes: str | None = None) -> PromptVersion:
    """Create a new draft version for a prompt key."""
    _ensure_prompt_tables()
    version = _next_version(prompt_key)
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO prompt_versions (prompt_key, version, content, status, created_by, notes)
                VALUES (%s, %s, %s, 'draft', %s, %s)
                RETURNING *
                """,
                (prompt_key, version, content, actor, notes),
            )
            row = cur.fetchone()
        conn.commit()

    _insert_audit(prompt_key, "draft", actor, None, version, notes)
    return _row_to_prompt(dict(row or {}))


def publish_version(prompt_key: str, version: int, actor: str, reason: str | None = None) -> PromptVersion:
    """Promote a specific version to published atomically."""
    _ensure_prompt_tables()
    with get_connection() as conn:
        with conn.transaction():
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT version FROM prompt_versions WHERE prompt_key = %s AND status = 'published' ORDER BY version DESC LIMIT 1",
                    (prompt_key,),
                )
                previous = cur.fetchone()
                previous_version = int(previous["version"]) if previous else None

                cur.execute(
                    "SELECT * FROM prompt_versions WHERE prompt_key = %s AND version = %s LIMIT 1",
                    (prompt_key, int(version)),
                )
                target = cur.fetchone()
                if not target:
                    raise ValueError(f"Versao {version} nao encontrada para {prompt_key}")

                cur.execute(
                    "UPDATE prompt_versions SET status = 'archived' WHERE prompt_key = %s AND status = 'published'",
                    (prompt_key,),
                )
                cur.execute(
                    """
                    UPDATE prompt_versions
                    SET status = 'published', published_at = NOW()
                    WHERE prompt_key = %s AND version = %s
                    RETURNING *
                    """,
                    (prompt_key, int(version)),
                )
                published = cur.fetchone()

        conn.commit()

    _insert_audit(prompt_key, "publish", actor, previous_version, int(version), reason)
    return _row_to_prompt(dict(published or {}))


def rollback_to_version(prompt_key: str, version: int, actor: str, reason: str | None = None) -> PromptVersion:
    """Create a new published version from an older version content."""
    _ensure_prompt_tables()
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT * FROM prompt_versions WHERE prompt_key = %s AND version = %s LIMIT 1",
                (prompt_key, int(version)),
            )
            source = cur.fetchone()
            if not source:
                raise ValueError(f"Versao {version} nao encontrada para {prompt_key}")
        conn.commit()

    draft = create_draft(
        prompt_key=prompt_key,
        content=str(source["content"]),
        actor=actor,
        notes=f"rollback from v{version}" if reason is None else reason,
    )

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT version FROM prompt_versions WHERE prompt_key = %s AND status = 'published' ORDER BY version DESC LIMIT 1",
                (prompt_key,),
            )
            previous = cur.fetchone()
            previous_version = int(previous["version"]) if previous else None
        conn.commit()

    published = publish_version(prompt_key, draft.version, actor, reason or f"rollback to v{version}")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE prompt_versions SET rollback_of = %s WHERE prompt_key = %s AND version = %s",
                (int(version), prompt_key, published.version),
            )
        conn.commit()

    _insert_audit(prompt_key, "rollback", actor, previous_version, published.version, reason or f"rollback to v{version}")
    return get_version(prompt_key, published.version)


def get_version(prompt_key: str, version: int) -> PromptVersion:
    """Fetch a specific prompt version."""
    _ensure_prompt_tables()
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT * FROM prompt_versions WHERE prompt_key = %s AND version = %s LIMIT 1",
                (prompt_key, int(version)),
            )
            row = cur.fetchone()
    if not row:
        raise ValueError(f"Versao {version} nao encontrada para {prompt_key}")
    return _row_to_prompt(dict(row))


def list_versions(prompt_key: str, limit: int = 50) -> list[PromptVersion]:
    """Return prompt versions from newest to oldest."""
    _ensure_prompt_tables()
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT *
                FROM prompt_versions
                WHERE prompt_key = %s
                ORDER BY version DESC
                LIMIT %s
                """,
                (prompt_key, int(limit)),
            )
            rows = cur.fetchall()
    return [_row_to_prompt(dict(row)) for row in rows]


def list_prompt_keys() -> list[str]:
    """List all known prompt keys from stored versions."""
    _ensure_prompt_tables()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT prompt_key FROM prompt_versions ORDER BY prompt_key")
            rows = cur.fetchall()
    return [str(row[0]) for row in rows]


def list_recent_audit(limit: int = 100) -> list[dict[str, Any]]:
    """List latest audit events."""
    _ensure_prompt_tables()
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT prompt_key, action, actor, from_version, to_version, reason, created_at
                FROM prompt_audit_log
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (int(limit),),
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]
