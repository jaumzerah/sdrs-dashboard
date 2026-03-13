"""Lead origin classifier used before supervisor routing."""

from __future__ import annotations

from typing import Any

from agent.db.disparos_repo import esta_na_base_disparados
from agent.utils.identifier import extrair_id_lead


def _get_nested(data: dict[str, Any], path: list[str]) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _extract_message(payload: dict[str, Any]) -> str:
    candidates = [
        _get_nested(payload, ["message", "conversation"]),
        _get_nested(payload, ["data", "message", "conversation"]),
        _get_nested(payload, ["data", "message", "content"]),
    ]
    for item in candidates:
        if isinstance(item, str) and item.strip():
            return item.strip()
    return ""


def _extract_channel(payload: dict[str, Any]) -> str:
    for key in ("canal", "channel", "source"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            lowered = value.strip().lower()
            if lowered in {"whatsapp", "email", "instagram", "facebook", "tiktok"}:
                return lowered

    remote_jid = _get_nested(payload, ["key", "remoteJid"])
    if isinstance(remote_jid, str) and remote_jid.strip():
        return "whatsapp"
    return "whatsapp"


def _extract_external_ad_reply(payload: dict[str, Any]) -> dict[str, Any] | None:
    candidates = [
        _get_nested(payload, ["data", "contextInfo", "externalAdReply"]),
        _get_nested(payload, ["message", "contextInfo", "externalAdReply"]),
        _get_nested(payload, ["data", "message", "contextInfo", "externalAdReply"]),
    ]
    for candidate in candidates:
        if isinstance(candidate, dict):
            return candidate
    return None


def _infer_ad_platform(payload: dict[str, Any], ad_reply: dict[str, Any]) -> str:
    combined = " ".join(
        str(v).lower() for v in [payload.get("origem"), ad_reply.get("source"), ad_reply.get("title")]
    )
    if "google" in combined:
        return "google"
    return "meta"


def classificar_origem(webhook_payload: dict[str, Any]) -> dict[str, Any]:
    """Classify lead origin as anuncio, disparo, or organico."""
    id_lead = extrair_id_lead(webhook_payload)
    mensagem = _extract_message(webhook_payload)
    canal = _extract_channel(webhook_payload)

    ad_reply = _extract_external_ad_reply(webhook_payload)
    if ad_reply is not None:
        return {
            "origem": "anuncio",
            "plataforma": _infer_ad_platform(webhook_payload, ad_reply),
            "anuncio_id": ad_reply.get("sourceId") or ad_reply.get("ctwaClid") or ad_reply.get("id"),
            "campanha": ad_reply.get("title") or ad_reply.get("campaign") or ad_reply.get("body"),
            "mensagem": mensagem,
            "canal": canal,
            "id_lead": id_lead,
        }

    disparo = esta_na_base_disparados(
        lid=id_lead.get("lid"),
        jid=id_lead.get("jid"),
        numero=id_lead.get("numero"),
    )
    if disparo is not None:
        return {
            "origem": "disparo",
            "plataforma": None,
            "anuncio_id": None,
            "campanha": disparo.get("campanha"),
            "mensagem": mensagem,
            "canal": canal,
            "id_lead": id_lead,
        }

    return {
        "origem": "organico",
        "plataforma": None,
        "anuncio_id": None,
        "campanha": None,
        "mensagem": mensagem,
        "canal": canal,
        "id_lead": id_lead,
    }
