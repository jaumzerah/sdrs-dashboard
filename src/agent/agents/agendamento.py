"""SDR worker for lead registration and meeting scheduling."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from langchain_core.messages import SystemMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from agent.prompts.runtime import get_prompt_content

LEADS_CADASTRADOS_PATH = Path(__file__).resolve().parents[3] / "data" / "leads_cadastrados.json"
AGENDAMENTOS_PATH = Path(__file__).resolve().parents[3] / "data" / "agendamentos.json"
OWNER_NAME = os.getenv("OWNER_NAME", "João Andrade")

DEFAULT_PROMPT_AGENDAMENTO = """Você é Claudia, assistente de {OWNER_NAME}, especialista em automação para o setor de móveis planejados.

Este lead demonstrou intenção clara de agendar. Seu único objetivo agora é confirmar o agendamento da reunião virtual gratuita de diagnóstico com {OWNER_NAME}.

Regras:
- Vá direto ao agendamento — não faça perguntas de qualificação.
- Colete em sequência: nome completo, melhor horário (dias da semana e período manhã/tarde) e e-mail para envio do link.
- Confirme todos os dados antes de finalizar.
- Nunca invente datas ou links — informe que o link será enviado por e-mail após confirmação.
- Se perguntada se é humana, confirme que é assistente virtual.

Após confirmar o agendamento, execute esta sequência obrigatória:

PASSO 1 — Confirme os dados:
Repita nome completo, horário escolhido e informe que o link da reunião será enviado para o e-mail fornecido em até 24 horas.

PASSO 2 — Pesquisa de satisfação:
Diga: "Antes de finalizar, posso te fazer duas perguntinhas rápidas sobre o atendimento?"
Aguarde confirmação. Se positiva, pergunte:
  a) "De 0 a 10, como você avaliaria a clareza e objetividade do atendimento que acabou de ter?"
  b) "Teve algum momento em que se sentiu perdida ou sem resposta?"
Aguarde cada resposta antes de prosseguir.

PASSO 3 — Plot twist (executar somente após receber o feedback):
Envie exatamente: "Obrigada pelo feedback! Posso te contar uma coisa? Você acabou de ser atendida por um agente SDR — exatamente como os que João Andrade implementa para lojas de móveis planejados. O sistema que agendou sua reunião é o próprio produto que será apresentado a você na reunião. Até lá! 🚀"
"""


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path, root_key: str) -> dict[str, Any]:
    if not path.exists():
        return {root_key: []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {root_key: []}
    if root_key not in data or not isinstance(data.get(root_key), list):
        data[root_key] = []
    return data


def _write_json(path: Path, data: dict[str, Any]) -> None:
    _ensure_parent(path)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


@tool
def verificar_disponibilidade(data: str, hora: str) -> str:
    """Retorna disponibilidade mock para agendamento."""
    sugestoes = [
        f"{data} 09:00",
        f"{data} {hora}",
        f"{data} 15:30",
    ]
    return "Horários disponíveis: " + ", ".join(sugestoes)


@tool
def cadastrar_lead(nome: str, telefone: str, email: str | None = None, origem: str | None = None) -> str:
    """Cadastra lead em arquivo local de simulacao."""
    base = _read_json(LEADS_CADASTRADOS_PATH, "leads")
    leads = base["leads"]
    lead = {
        "nome": nome,
        "telefone": telefone,
        "email": email,
        "origem": origem,
        "cadastrado_em": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    leads.append(lead)
    _write_json(LEADS_CADASTRADOS_PATH, base)
    return f"Lead cadastrado com sucesso: {nome} ({telefone})"


@tool
def confirmar_agendamento(nome: str, data: str, hora: str, contato: str) -> str:
    """Registra agendamento em arquivo local e retorna confirmacao."""
    base = _read_json(AGENDAMENTOS_PATH, "agendamentos")
    agendamentos = base["agendamentos"]
    agendamento = {
        "nome": nome,
        "data": data,
        "hora": hora,
        "contato": contato,
        "registrado_em": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    agendamentos.append(agendamento)
    _write_json(AGENDAMENTOS_PATH, base)
    return (
        "Agendamento confirmado! "
        f"{nome}, sua reunião foi marcada para {data} às {hora}. "
        f"Contato de confirmação: {contato}."
    )


def build_prompt_agendamento(state: dict[str, Any]) -> list[SystemMessage]:
    """Build the system prompt for the scheduling specialist."""
    del state
    content = get_prompt_content(
        prompt_key="sdr_agendamento",
        fallback_content=DEFAULT_PROMPT_AGENDAMENTO,
        variables={"OWNER_NAME": OWNER_NAME},
    )
    return [
        SystemMessage(
            content=content
        )
    ]


def build_sdr_agendamento_agent(model: Any) -> Any:
    """Create scheduling SDR worker agent."""
    return create_react_agent(
        model=model,
        tools=[verificar_disponibilidade, cadastrar_lead, confirmar_agendamento],
        name="sdr_agendamento",
        prompt=build_prompt_agendamento,
    )
