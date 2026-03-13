"""CLI report for SDR quality metrics."""

from __future__ import annotations

import io
import sys
from datetime import datetime
from typing import Any

from dotenv import load_dotenv

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


SDR_ORDER = [
    "sdr_frios",
    "sdr_quentes",
    "sdr_anuncios",
    "sdr_agendamento",
]


def _iter_sdr_items(values: dict[str, float]) -> list[tuple[str, float]]:
    ordered: list[tuple[str, float]] = []
    for sdr in SDR_ORDER:
        if sdr in values:
            ordered.append((sdr, float(values[sdr])))
    for sdr in sorted(values):
        if sdr not in SDR_ORDER:
            ordered.append((sdr, float(values[sdr])))
    return ordered


def _format_criado_em(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    text = str(value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return text[:16]


def main() -> None:
    load_dotenv()

    from agent.db.metricas_repo import (
        alertas_recentes,
        nota_media_por_sdr,
        taxa_aprovacao_primeira_tentativa_por_sdr,
    )

    medias = nota_media_por_sdr()
    taxas = taxa_aprovacao_primeira_tentativa_por_sdr()
    alertas = alertas_recentes(limite=20)

    print("=== RELATÓRIO DE QUALIDADE DOS SDRs ===")
    print()

    if not medias and not taxas and not alertas:
        print("Sem dados ainda.")
        return

    print("Nota média por SDR:")
    for sdr, media in _iter_sdr_items(medias):
        print(f"  {sdr + ':':<16}{media:>6.2f}")

    print()
    print("Taxa de aprovação na 1ª tentativa:")
    for sdr, taxa in _iter_sdr_items(taxas):
        print(f"  {sdr + ':':<16}{taxa:>6.1f}%")

    print()
    print("Últimos alertas (enviados sem aprovação após 3 tentativas):")
    if not alertas:
        print("  Nenhum alerta registrado.")
        return

    for alerta in alertas:
        criado_em = _format_criado_em(alerta.get("criado_em"))
        sdr = str(alerta.get("sdr_origem", ""))
        nota = float(alerta.get("nota", 0.0))
        tentativas = int(alerta.get("tentativas", 0))
        print(f"  [{criado_em}] {sdr:<13} | nota: {nota:.2f} | tentativas: {tentativas}")


if __name__ == "__main__":
    main()
