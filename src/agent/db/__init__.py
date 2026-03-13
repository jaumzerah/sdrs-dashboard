"""Database connection and repositories."""

from agent.db.avaliacao_repo import registrar_avaliacao
from agent.db.connection import get_connection, init_db
from agent.db.disparos_repo import esta_na_base_disparados, registrar_disparo
from agent.db.leads_repo import atualizar_lead, buscar_lead, criar_lead
from agent.db.metricas_repo import alertas_recentes, nota_media_por_sdr, taxa_aprovacao_primeira_tentativa_por_sdr

__all__ = [
    "atualizar_lead",
    "buscar_lead",
    "criar_lead",
    "esta_na_base_disparados",
    "get_connection",
    "init_db",
    "nota_media_por_sdr",
    "registrar_avaliacao",
    "registrar_disparo",
    "taxa_aprovacao_primeira_tentativa_por_sdr",
    "alertas_recentes",
]
