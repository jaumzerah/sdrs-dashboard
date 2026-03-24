"""Runtime prompt loading with DB-backed versioning and cache."""

from __future__ import annotations

import os
import time
from threading import Lock

from agent.db.prompt_repo import ensure_prompt_exists, get_published_prompt

_CACHE: dict[str, tuple[float, str]] = {}
_LOCK = Lock()


def _ttl_seconds() -> int:
    raw = os.getenv("PROMPT_CACHE_TTL_SECONDS", "10")
    try:
        return max(1, int(raw))
    except ValueError:
        return 10


def _render_variables(content: str, variables: dict[str, str] | None = None) -> str:
    if not variables:
        return content
    rendered = content
    for key, value in variables.items():
        rendered = rendered.replace(f"{{{key}}}", value)
    return rendered


def get_prompt_content(prompt_key: str, fallback_content: str, variables: dict[str, str] | None = None) -> str:
    """Return prompt content from DB with fallback and short-lived cache."""
    now = time.time()
    ttl = _ttl_seconds()

    with _LOCK:
        cached = _CACHE.get(prompt_key)
        if cached and now - cached[0] <= ttl:
            return _render_variables(cached[1], variables)

    try:
        ensure_prompt_exists(prompt_key=prompt_key, content=fallback_content)
        published = get_published_prompt(prompt_key=prompt_key)
        content = published.content if published else fallback_content
    except Exception:
        content = fallback_content

    with _LOCK:
        _CACHE[prompt_key] = (now, content)

    return _render_variables(content, variables)


def invalidate_prompt_cache(prompt_key: str | None = None) -> None:
    """Invalidate prompt cache globally or for one key."""
    with _LOCK:
        if prompt_key is None:
            _CACHE.clear()
            return
        _CACHE.pop(prompt_key, None)
