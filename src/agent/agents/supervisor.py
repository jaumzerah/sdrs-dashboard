"""Supervisor builder for the SDR multi-agent workflow."""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.tools import tool
from langgraph_supervisor import create_supervisor

from agent.agents.agendamento import build_sdr_agendamento_agent
from agent.agents.sdr_anuncios import build_sdr_anuncios_agent
from agent.agents.sdr_frios import build_sdr_frios_agent
from agent.agents.sdr_quentes import build_sdr_quentes_agent
from agent.routing.rules import route_target_from_classificacao

logger = logging.getLogger(__name__)


@tool
def route_lead_classificado(origem: str, mensagem: str = "") -> str:
    """Decide target SDR from classificar_origem() output."""
    target = route_target_from_classificacao(origem=origem, mensagem=mensagem)
    return f"route_target={target}"


def preparar_entrada_supervisor(classificacao: dict[str, Any]) -> dict[str, Any]:
    """Build supervisor input from classificar_origem() result.

    This keeps the supervisor interface explicit and stable.
    """
    id_lead = classificacao.get("id_lead", {})
    usando_lid = bool(id_lead.get("usando_lid"))
    id_usado = id_lead.get("lid") if usando_lid else id_lead.get("jid")
    if not id_usado:
        id_usado = id_lead.get("id_primario")

    origem = classificacao.get("origem")
    logger.info(
        "Lead classificado para supervisor",
        extra={
            "origem": origem,
            "usando_lid": usando_lid,
            "id_usado": id_usado,
        },
    )

    content = (
        "Voce recebeu um lead ja classificado. Use a ferramenta route_lead_classificado.\n"
        f"dados_classificacao={json.dumps(classificacao, ensure_ascii=False)}"
    )
    return {
        "messages": [
            {
                "role": "user",
                "content": content,
            }
        ]
    }


SUPERVISOR_PROMPT = (
    "Voce e o Supervisor SDR. Sua funcao e escolher apenas um SDR para cada lead, "
    "com base no dict recebido de classificar_origem(). "
    "Regras obrigatorias: "
    "(0) se houver intencao de agendamento na mensagem (ex: quero marcar, agenda, disponibilidade), "
    "priorize sdr_agendamento; "
    "(1) origem=disparo -> sdr_frios; "
    "(2) origem=organico -> sdr_quentes; "
    "(3) origem=anuncio -> sdr_anuncios. "
    "Antes de transferir, use a ferramenta route_lead_classificado com origem e mensagem para validar a rota. "
    "Depois transfira para o SDR correspondente e nao converse diretamente com o lead."
)


def build_supervisor_workflow(model: Any, state_schema: Any | None = None) -> Any:
    """Create supervisor workflow connected to the 3 SDR workers."""
    sdr_frios = build_sdr_frios_agent(model)
    sdr_quentes = build_sdr_quentes_agent(model)
    sdr_anuncios = build_sdr_anuncios_agent(model)
    sdr_agendamento = build_sdr_agendamento_agent(model)

    kwargs: dict[str, Any] = {
        "agents": [sdr_frios, sdr_quentes, sdr_anuncios, sdr_agendamento],
        "tools": [route_lead_classificado],
        "model": model,
        "prompt": SUPERVISOR_PROMPT,
        "supervisor_name": "supervisor_sdr",
        "output_mode": "last_message",
    }
    if state_schema is not None:
        kwargs["state_schema"] = state_schema
    return create_supervisor(**kwargs)
