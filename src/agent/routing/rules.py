"""Lead routing rules for the SDR supervisor."""

from __future__ import annotations

import unicodedata
from typing import Literal

TargetAgent = Literal["sdr_frios", "sdr_quentes", "sdr_anuncios", "sdr_agendamento"]


def normalize_text(value: str | None) -> str:
    """Normalize metadata text for stable routing."""
    if not value:
        return ""
    lowered = value.strip().lower()
    normalized = unicodedata.normalize("NFKD", lowered)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_text.replace("-", "_").replace(" ", "_")


def has_intencao_agendamento(mensagem: str | None) -> bool:
    """Detect scheduling intent in user message text."""
    msg = normalize_text(mensagem)
    if not msg:
        return False

    gatilhos = {
        "quero_marcar",
        "quero_agendar",
        "tem_horario",
        "agenda",
        "agendar",
        "agendamento",
        "disponibilidade",
        "marcar_reuniao",
    }
    return any(gatilho in msg for gatilho in gatilhos)


def route_target(
    canal: str | None,
    captacao: str | None,
    origem: str | None,
) -> TargetAgent:
    """Route lead to the right SDR based on metadata.

    Rules:
    - Returned from cold outreach -> sdr_frios
    - Organic from site/whatsapp -> sdr_quentes
    - Paid media from Meta/Google ads -> sdr_anuncios
    """
    canal_n = normalize_text(canal)
    captacao_n = normalize_text(captacao)
    origem_n = normalize_text(origem)

    if captacao_n in {"cold_outreach", "disparo", "retorno_disparo", "outbound"}:
        return "sdr_frios"

    if origem_n in {"meta_ads", "facebook_ads", "instagram_ads", "google_ads"}:
        return "sdr_anuncios"

    if captacao_n in {"organico", "inbound", "site", "whatsapp"}:
        return "sdr_quentes"

    if canal_n in {"site", "whatsapp"}:
        return "sdr_quentes"

    return "sdr_quentes"


def route_target_from_classificacao(origem: str | None, mensagem: str | None = None) -> TargetAgent:
    """Route target using normalized output from classificar_origem()."""
    if has_intencao_agendamento(mensagem):
        return "sdr_agendamento"

    origem_n = normalize_text(origem)
    if origem_n == "disparo":
        return "sdr_frios"
    if origem_n == "anuncio":
        return "sdr_anuncios"
    return "sdr_quentes"
