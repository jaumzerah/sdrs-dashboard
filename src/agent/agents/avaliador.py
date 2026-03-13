"""Quality evaluator node for SDR responses."""

from __future__ import annotations

import json
import os
from typing import Any

from langchain.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from agent.db.avaliacao_repo import registrar_avaliacao
from agent.schemas.lead import AgentState
from agent.utils.timeout import executar_com_timeout

AVALIADOR_SYSTEM_PROMPT = (
    "Você é um avaliador de qualidade de respostas de SDR. "
    "Avalie a resposta com nota de 0 a 10 considerando: "
    "1. Tom adequado ao tipo de lead (frio/quente/anuncio) — peso 3; "
    "2. Clareza e objetividade — peso 2; "
    "3. CTA claro (próximo passo definido para o lead) — peso 3; "
    "4. Sem informações inventadas ou incorretas — peso 2. "
    "Nota mínima para aprovação: 7.0. "
    "Responda APENAS em JSON válido, sem texto extra: "
    '{"nota": 8.5, "aprovado": true, "feedback": "..."}'
)


def _build_model() -> ChatOpenAI:
    """Build evaluator LLM model."""
    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o"),
        temperature=0,
        api_key=SecretStr(os.getenv("OPENAI_API_KEY", "test-key")),
    )


def _extract_mensagem_original(state: AgentState | dict[str, Any]) -> str:
    """Extract original lead message from state."""
    if isinstance(state.get("mensagem_original"), str):
        return state["mensagem_original"]
    if isinstance(state.get("mensagem"), str):
        return state["mensagem"]
    return ""


def _invoke_avaliador_llm(system_prompt: str, user_prompt: str) -> str:
    """Invoke LLM and return raw content string."""
    model = _build_model()
    response = model.invoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
    )
    content = response.content
    if isinstance(content, str):
        return content
    return json.dumps(content, ensure_ascii=False)


def _parse_json_safe(raw_text: str) -> dict[str, Any]:
    """Parse JSON from model output safely."""
    text = raw_text.strip()
    if not text:
        raise ValueError("resposta vazia do avaliador")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def _registrar_avaliacao_safe(
    state: AgentState | dict[str, Any],
    nota: float,
    tentativas: int,
    aprovado: bool,
) -> None:
    """Persist evaluator metrics without breaking runtime on DB failures."""
    try:
        registrar_avaliacao(
            lead_id=state.get("lead_id"),
            sdr_origem=str(state.get("sdr_origem") or "desconhecido"),
            nota=nota,
            tentativas=tentativas,
            aprovado=aprovado,
        )
    except Exception:
        return


def _computar_avaliacao(state: AgentState | dict[str, Any]) -> dict[str, Any]:
    """Compute evaluator score/feedback fields from current state."""
    resposta = str(state.get("resposta_pendente", "") or "")
    origem = str(state.get("origem", "") or "")
    canal = str(state.get("canal", "") or "")
    mensagem_original = _extract_mensagem_original(state)
    tentativas = int(state.get("tentativas_avaliacao", 0) or 0) + 1

    user_prompt = (
        "Contexto para avaliação:\n"
        f"- origem: {origem}\n"
        f"- canal: {canal}\n"
        f"- mensagem_original: {mensagem_original}\n"
        "- resposta_sdr:\n"
        f"{resposta}"
    )

    try:
        raw = _invoke_avaliador_llm(AVALIADOR_SYSTEM_PROMPT, user_prompt)
        parsed = _parse_json_safe(raw)
        nota = float(parsed.get("nota", 0.0) or 0.0)
        feedback = str(parsed.get("feedback", "") or "")
    except Exception:
        nota = 0.0
        feedback = "Erro ao interpretar avaliacao do LLM."

    return {
        "nota_avaliacao": nota,
        "feedback_avaliacao": feedback,
        "tentativas_avaliacao": tentativas,
    }


def avaliar_resposta(state: AgentState | dict[str, Any]) -> dict[str, Any]:
    """Evaluate pending SDR response quality and update evaluator fields."""
    result = _computar_avaliacao(state)
    nota = float(result["nota_avaliacao"])
    tentativas = int(result["tentativas_avaliacao"])
    _registrar_avaliacao_safe(state, nota, tentativas, aprovado=nota >= 7.0)
    return result


def avaliar_resposta_com_timeout(
    state: AgentState | dict[str, Any],
    timeout_segundos: float,
) -> dict[str, Any]:
    """Evaluate response with timeout fallback and metrics logging."""

    def _fallback() -> dict[str, Any]:
        tentativas = max(3, int(state.get("tentativas_avaliacao", 0) or 0) + 1)
        return {
            "nota_avaliacao": 0.0,
            "feedback_avaliacao": "Timeout excedido no ciclo de avaliação",
            "tentativas_avaliacao": tentativas,
        }

    result = executar_com_timeout(
        fn=lambda: _computar_avaliacao(state),
        segundos=timeout_segundos,
        fallback_fn=_fallback,
    )
    nota = float(result["nota_avaliacao"])
    tentativas = int(result["tentativas_avaliacao"])
    _registrar_avaliacao_safe(state, nota, tentativas, aprovado=nota >= 7.0)
    return result
