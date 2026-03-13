"""Helpers to migrate LangGraph checkpoint state between thread IDs."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# TODO: get_state() e update_state() são síncronos.
# Se o consumer migrar para async, criar versão
# async de migrar_thread_se_necessario() usando
# os métodos assíncronos equivalentes do checkpointer.


def _extract_messages(values: dict[str, Any] | None) -> list[Any]:
    """Extract messages list from state values safely."""
    if not isinstance(values, dict):
        return []
    messages = values.get("messages")
    if isinstance(messages, list):
        return messages
    return []


def migrar_thread_se_necessario(app: Any, jid: str, lid: str) -> None:
    """Migrate checkpoint state from JID thread to LID thread when needed.

    - If old thread has no history, do nothing.
    - If new thread already has history, do not overwrite and log warning.
    - Otherwise, copy old state to new thread via update_state.
    """
    if not jid or not lid or jid == lid:
        return

    config_antigo = {"configurable": {"thread_id": jid}}
    config_novo = {"configurable": {"thread_id": lid}}

    try:
        estado_antigo = app.get_state(config_antigo)
        old_values = getattr(estado_antigo, "values", None)
    except Exception:
        return

    old_messages = _extract_messages(old_values)
    if not old_messages:
        return

    try:
        estado_novo = app.get_state(config_novo)
        new_values = getattr(estado_novo, "values", None)
    except Exception:
        new_values = None

    new_messages = _extract_messages(new_values)
    if new_messages:
        logger.warning("Thread novo já existe, migração ignorada: %s -> %s", jid, lid)
        return

    app.update_state(config_novo, old_values)
    logger.info("Thread migrado: %s -> %s | %s mensagens preservadas", jid, lid, len(old_messages))
