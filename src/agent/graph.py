"""Supervisor-based LangGraph workflow using OpenAI GPT-4.1 mini."""

from __future__ import annotations

import atexit
import os
import warnings
from typing import Literal
from typing import Any

from langchain.messages import AIMessage
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.constants import END, START
from langgraph.graph import StateGraph
from pydantic import SecretStr
from psycopg import OperationalError

from agent.agents import avaliar_resposta_com_timeout, build_supervisor_workflow
from agent.integrations import ChatwootClient
from agent.routing.avaliador_router import should_send
from agent.routing.rules import route_target_from_classificacao
from agent.schemas.lead import AgentState


def _build_model() -> ChatOpenAI:
    """Build a shared model instance for all agents in the graph."""
    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o"),
        temperature=0,
        api_key=SecretStr(os.getenv("OPENAI_API_KEY", "test-key")),
    )


model = _build_model()


def _build_checkpointer() -> Any | None:
    """Create Postgres checkpointer when DB URL is configured."""
    conn_string = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_CHECKPOINT_URI")
    if not conn_string:
        return None

    try:
        context_manager = PostgresSaver.from_conn_string(conn_string)
        checkpointer = context_manager.__enter__()
        checkpointer.setup()
        atexit.register(lambda: context_manager.__exit__(None, None, None))
        return checkpointer
    except OperationalError:
        warnings.warn(
            "DATABASE_URL/POSTGRES_CHECKPOINT_URI is set but Postgres connection failed. "
            "Starting without checkpointing.",
            RuntimeWarning,
            stacklevel=2,
        )
        return None


checkpointer = _build_checkpointer()

supervisor_workflow = build_supervisor_workflow(model)
supervisor_graph = supervisor_workflow.compile(name="SDR Supervisor Core")


def _extract_message_content(message: BaseMessage | dict[str, Any] | Any) -> str:
    """Extract content from message object or dict."""
    if isinstance(message, dict):
        content = message.get("content", "")
        return content if isinstance(content, str) else str(content)
    content = getattr(message, "content", "")
    return content if isinstance(content, str) else str(content)


def _ensure_defaults(state: AgentState | dict[str, Any]) -> dict[str, Any]:
    """Ensure evaluator scalar defaults exist in state updates."""
    return {
        "resposta_pendente": str(state.get("resposta_pendente", "") or ""),
        "tentativas_avaliacao": int(state.get("tentativas_avaliacao", 0) or 0),
        "nota_avaliacao": float(state.get("nota_avaliacao", 0.0) or 0.0),
        "feedback_avaliacao": str(state.get("feedback_avaliacao", "") or ""),
        "sdr_origem": state.get("sdr_origem"),
    }


def executar_supervisor(state: AgentState | dict[str, Any]) -> dict[str, Any]:
    """Run supervisor workflow and capture pending response for evaluator."""
    result = supervisor_graph.invoke({"messages": state.get("messages", [])})
    result_messages = result.get("messages") or []
    last_message = result_messages[-1] if result_messages else AIMessage(content="")
    resposta = _extract_message_content(last_message)
    tentativas_atuais = int(state.get("tentativas_avaliacao", 0) or 0)

    sdr_origem = state.get("sdr_origem")
    if not sdr_origem:
        sdr_origem = route_target_from_classificacao(state.get("origem"), state.get("mensagem"))

    return {
        "messages": [last_message],
        "resposta_pendente": resposta,
        "tentativas_avaliacao": tentativas_atuais,
        "nota_avaliacao": float(state.get("nota_avaliacao", 0.0) or 0.0),
        "feedback_avaliacao": str(state.get("feedback_avaliacao", "") or ""),
        "sdr_origem": sdr_origem,
    }


def preparar_refacao(state: AgentState | dict[str, Any]) -> dict[str, Any]:
    """Add rewrite instruction before sending back to supervisor cycle."""
    nota = float(state.get("nota_avaliacao", 0.0) or 0.0)
    feedback = str(state.get("feedback_avaliacao", "") or "")
    sdr_origem = state.get("sdr_origem") or "sdr"
    content = (
        f"Reescreva a resposta usando o mesmo SDR de origem ({sdr_origem}). "
        f"Sua resposta anterior recebeu nota {nota:.1f}/10. "
        f"Feedback do avaliador: {feedback}"
    )
    return {"messages": [AIMessage(content=content)]}


def _append_alert_note_if_possible(state: AgentState | dict[str, Any]) -> None:
    """Append warning note to Chatwoot when alert route is used."""
    conversation_id = state.get("chatwoot_conversation_id")
    if not conversation_id:
        return
    try:
        client = ChatwootClient()
        nota = float(state.get("nota_avaliacao", 0.0) or 0.0)
        feedback = str(state.get("feedback_avaliacao", "") or "")
        warning_note = (
            "⚠️ Resposta enviada sem aprovação após 3 tentativas. "
            f"Nota: {nota}. Feedback: {feedback}"
        )
        client.adicionar_nota(int(conversation_id), warning_note)
    except Exception:
        # Non-blocking side-effect for alerting only
        return


def enviar_resposta(state: AgentState | dict[str, Any]) -> dict[str, Any]:
    """Finalize response delivery path."""
    resposta = str(state.get("resposta_pendente", "") or "")
    return {"messages": [AIMessage(content=resposta)]}


def enviar_com_alerta(state: AgentState | dict[str, Any]) -> dict[str, Any]:
    """Finalize response and create warning note for human follow-up."""
    _append_alert_note_if_possible(state)
    return enviar_resposta(state)


def should_continue(state: AgentState | dict[str, Any]) -> Literal["enviar", "refazer", "enviar_com_alerta"]:
    """Route evaluator output to next internal cycle step."""
    return should_send(dict(state))


def avaliar_com_timeout(state: AgentState | dict[str, Any]) -> dict[str, Any]:
    """Evaluator node with timeout fallback protection."""
    timeout_segundos = float(os.getenv("AVALIADOR_TIMEOUT_SEGUNDOS", "30"))
    return avaliar_resposta_com_timeout(state, timeout_segundos=timeout_segundos)


builder = StateGraph(AgentState)
builder.add_node("executar_supervisor", executar_supervisor)
builder.add_node("avaliador", avaliar_com_timeout)
builder.add_node("preparar_refacao", preparar_refacao)
builder.add_node("enviar", enviar_resposta)
builder.add_node("enviar_com_alerta", enviar_com_alerta)

builder.add_edge(START, "executar_supervisor")
builder.add_edge("executar_supervisor", "avaliador")
builder.add_conditional_edges(
    "avaliador",
    should_continue,
    {
        "enviar": "enviar",
        "refazer": "preparar_refacao",
        "enviar_com_alerta": "enviar_com_alerta",
    },
)
builder.add_edge("preparar_refacao", "executar_supervisor")
builder.add_edge("enviar", END)
builder.add_edge("enviar_com_alerta", END)

if checkpointer is not None:
    graph = builder.compile(name="SDR Supervisor Workflow", checkpointer=checkpointer)
else:
    graph = builder.compile(name="SDR Supervisor Workflow")
