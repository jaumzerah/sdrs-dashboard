from __future__ import annotations

from typing import TypedDict


class LeadDisparo(TypedDict):
    id_primario: str
    numero: str
    mensagem: str
    campanha: str | None
