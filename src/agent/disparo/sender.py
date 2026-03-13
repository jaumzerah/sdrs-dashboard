"""Send helper for cold outreach disparo worker."""

from __future__ import annotations

import logging
import os

from agent.db.disparos_repo import esta_na_base_disparados, registrar_disparo
from agent.disparo.schema import LeadDisparo
from agent.integrations.evolution import EvolutionClient

logger = logging.getLogger(__name__)


def enviar_disparo(lead: LeadDisparo) -> bool:
    """Send disparo message once and register it when successful."""
    id_primario = str(lead.get("id_primario", "") or "")
    numero = str(lead.get("numero", "") or "")
    mensagem = str(lead.get("mensagem", "") or "")
    campanha = str(lead.get("campanha") or "disparo_automatico")

    existente = esta_na_base_disparados(lid=id_primario, jid=id_primario, numero=numero)
    if existente is not None:
        logger.warning("Lead ja disparado; ignorando envio", extra={"id_primario": id_primario, "numero": numero})
        return False

    instance_disparo = os.getenv("EVOLUTION_INSTANCE_DISPARO", "")

    try:
        client = EvolutionClient(instance=instance_disparo or None)
        client.enviar_mensagem(numero=numero, texto=mensagem)
        registrar_disparo(
            lead_id=None,
            lid=id_primario,
            jid=id_primario,
            numero=numero,
            campanha=campanha,
            numero_remetente=instance_disparo or None,
        )
        logger.info("Disparo enviado com sucesso", extra={"id_primario": id_primario, "numero": numero, "campanha": campanha})
        return True
    except Exception:
        logger.exception("Falha ao enviar disparo", extra={"id_primario": id_primario, "numero": numero, "campanha": campanha})
        return False
