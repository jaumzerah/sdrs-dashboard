"""Typed schema for lead input payload."""

from __future__ import annotations

from typing import Annotated

from langchain.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import NotRequired, TypedDict


class AgentState(TypedDict):
    """Graph state for internal agent processing cycle.

    Notes:
    - `messages` accumulates the real conversation history.
    - Scalar fields are overwritten on each node update.
    - Defaults are handled by runtime initialization.
    """

    messages: Annotated[list[AnyMessage], add_messages]
    resposta_pendente: NotRequired[str]
    tentativas_avaliacao: NotRequired[int]
    nota_avaliacao: NotRequired[float]
    feedback_avaliacao: NotRequired[str]
    sdr_origem: NotRequired[str | None]
    lead_id: NotRequired[str | None]
    chatwoot_conversation_id: NotRequired[int | None]


class LeadMetadata(TypedDict):
    """Routing metadata sent by channel connectors."""

    canal: str
    captacao: str
    origem: str


class LeadPayload(TypedDict):
    """Lead message payload used by the SDR workflow."""

    lead_id: str
    nome: str
    mensagem: str
    metadata: LeadMetadata
