"""Lead identifier extraction for WhatsApp transition (LID/JID)."""

from __future__ import annotations

import re
from typing import Any


def _clean_phone(raw: str | None) -> str | None:
    """Normalize phone-like values to digits only."""
    if not raw:
        return None
    local = raw.split("@", maxsplit=1)[0]
    digits = re.sub(r"\D+", "", local)
    return digits or None


def extrair_id_lead(webhook_payload: dict[str, Any]) -> dict[str, Any]:
    """Extract LID/JID identifiers from incoming webhook payload.

    Priority:
    - id_primario = LID (if available)
    - fallback to JID
    """
    key = webhook_payload.get("key") or {}
    lid = key.get("lid") or key.get("participant_lid")
    jid = key.get("remoteJid")
    numero = _clean_phone(jid)

    return {
        "id_primario": lid or jid,
        "lid": lid,
        "jid": jid,
        "numero": numero,
        "usando_lid": bool(lid),
    }
