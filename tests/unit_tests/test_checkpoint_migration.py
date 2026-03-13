from __future__ import annotations

from typing import Annotated

from langchain.messages import AnyMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from agent.db.checkpoint_migration import migrar_thread_se_necessario


class _State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def _noop(_state: _State) -> dict:
    return {}


def _build_app():
    builder = StateGraph(_State)
    builder.add_node("noop", _noop)
    builder.add_edge(START, "noop")
    builder.add_edge("noop", END)
    return builder.compile(checkpointer=InMemorySaver())


def test_sem_historico_nao_migra(monkeypatch) -> None:
    app = _build_app()

    called = {"update": False}

    original_update = app.update_state

    def _spy_update(config, values):
        called["update"] = True
        return original_update(config, values)

    monkeypatch.setattr(app, "update_state", _spy_update)

    migrar_thread_se_necessario(app, jid="552199@s.whatsapp.net", lid="abc@lid")
    assert called["update"] is False


def test_copia_historico_para_novo_thread() -> None:
    app = _build_app()
    old_cfg = {"configurable": {"thread_id": "552199@s.whatsapp.net"}}
    new_cfg = {"configurable": {"thread_id": "abc@lid"}}

    app.invoke({"messages": [HumanMessage(content="mensagem antiga")]}, config=old_cfg)

    migrar_thread_se_necessario(app, jid="552199@s.whatsapp.net", lid="abc@lid")

    estado_novo = app.get_state(new_cfg)
    assert estado_novo.values["messages"]
    assert estado_novo.values["messages"][0].content == "mensagem antiga"


def test_thread_novo_existente_nao_sobrescreve(caplog) -> None:
    app = _build_app()
    old_cfg = {"configurable": {"thread_id": "552199@s.whatsapp.net"}}
    new_cfg = {"configurable": {"thread_id": "abc@lid"}}

    app.invoke({"messages": [HumanMessage(content="hist antigo")]}, config=old_cfg)
    app.invoke({"messages": [HumanMessage(content="hist novo")]}, config=new_cfg)

    with caplog.at_level("WARNING"):
        migrar_thread_se_necessario(app, jid="552199@s.whatsapp.net", lid="abc@lid")

    estado_novo = app.get_state(new_cfg)
    assert estado_novo.values["messages"][0].content == "hist novo"
    assert any("Thread novo já existe" in rec.message for rec in caplog.records)


def test_apos_migracao_get_state_novo_retorna_historico_antigo() -> None:
    app = _build_app()
    old_cfg = {"configurable": {"thread_id": "552199@s.whatsapp.net"}}
    new_cfg = {"configurable": {"thread_id": "abc@lid"}}

    app.invoke({"messages": [HumanMessage(content="preservar este historico")]}, config=old_cfg)
    migrar_thread_se_necessario(app, jid="552199@s.whatsapp.net", lid="abc@lid")

    estado_novo = app.get_state(new_cfg)
    assert estado_novo.values["messages"][0].content == "preservar este historico"
