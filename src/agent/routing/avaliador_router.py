"""Routing decision for evaluator output."""

from __future__ import annotations

from typing import Literal


def should_send(state: dict) -> Literal["enviar", "refazer", "enviar_com_alerta"]:
    """Decide next step after evaluator note.

    Rules:
    - nota >= 7.0 -> enviar
    - nota < 7.0 and tentativas < 3 -> refazer
    - nota < 7.0 and tentativas >= 3 -> enviar_com_alerta
    """
    nota = float(state.get("nota_avaliacao", 0.0) or 0.0)
    tentativas = int(state.get("tentativas_avaliacao", 0) or 0)

    if nota >= 7.0:
        return "enviar"
    if tentativas < 3:
        return "refazer"
    return "enviar_com_alerta"
