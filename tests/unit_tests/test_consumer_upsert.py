from __future__ import annotations

import json
from typing import Any

from agent import consumer as consumer_mod


class _FakeGraph:
    def __init__(self) -> None:
        self.last_input: dict[str, Any] | None = None
        self.last_config: dict[str, Any] | None = None

    def invoke(self, state_input: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        self.last_input = state_input
        self.last_config = config
        return {"messages": [{"content": "ok"}]}


def _setup_common(monkeypatch, classificacao: dict[str, Any]) -> _FakeGraph:
    fake_graph = _FakeGraph()

    monkeypatch.setattr(consumer_mod, "classificar_origem", lambda payload: classificacao)
    monkeypatch.setattr(consumer_mod, "preparar_entrada_supervisor", lambda c: {"messages": [{"role": "user", "content": "x"}]})
    monkeypatch.setattr(consumer_mod, "_get_graph", lambda: fake_graph)
    monkeypatch.setattr(consumer_mod, "migrar_thread_se_necessario", lambda app, jid, lid: None)
    monkeypatch.setattr(consumer_mod, "route_target_from_classificacao", lambda origem, mensagem=None: "sdr_quentes")
    monkeypatch.setattr(consumer_mod.LeadConsumer, "_build_chatwoot_client", lambda self: None)
    monkeypatch.setattr(consumer_mod.LeadConsumer, "_sync_chatwoot", lambda self, payload, classificacao, lead: None)

    return fake_graph


def test_lead_novo_sem_lid_thread_id_jid(monkeypatch) -> None:
    classificacao = {
        "origem": "organico",
        "plataforma": None,
        "campanha": None,
        "canal": "whatsapp",
        "mensagem": "oi",
        "id_lead": {
            "id_primario": "5521999@s.whatsapp.net",
            "lid": None,
            "jid": "5521999@s.whatsapp.net",
            "numero": "5521999",
            "usando_lid": False,
        },
    }
    fake_graph = _setup_common(monkeypatch, classificacao)

    monkeypatch.setattr(consumer_mod, "buscar_lead", lambda lid=None, jid=None, numero=None: None)
    monkeypatch.setattr(
        consumer_mod,
        "criar_lead",
        lambda dados: {"id": "lead-1", **dados},
    )
    monkeypatch.setattr(consumer_mod, "atualizar_lead", lambda lead_id, dados: {"id": lead_id, **dados})

    consumer = consumer_mod.LeadConsumer("amqp://guest:guest@localhost:5672/")
    result = consumer._process_payload({"dummy": True})

    assert result["thread_id"] == "5521999@s.whatsapp.net"
    assert fake_graph.last_config == {"configurable": {"thread_id": "5521999@s.whatsapp.net"}}


def test_lead_novo_com_lid_thread_id_lid(monkeypatch) -> None:
    classificacao = {
        "origem": "anuncio",
        "plataforma": "meta",
        "campanha": "c1",
        "canal": "whatsapp",
        "mensagem": "oi",
        "id_lead": {
            "id_primario": "123@lid",
            "lid": "123@lid",
            "jid": "552198@s.whatsapp.net",
            "numero": "552198",
            "usando_lid": True,
        },
    }
    fake_graph = _setup_common(monkeypatch, classificacao)

    monkeypatch.setattr(consumer_mod, "buscar_lead", lambda lid=None, jid=None, numero=None: None)
    monkeypatch.setattr(consumer_mod, "criar_lead", lambda dados: {"id": "lead-2", **dados})
    monkeypatch.setattr(consumer_mod, "atualizar_lead", lambda lead_id, dados: {"id": lead_id, **dados})

    consumer = consumer_mod.LeadConsumer("amqp://guest:guest@localhost:5672/")
    result = consumer._process_payload({"dummy": True})

    assert result["thread_id"] == "123@lid"
    assert fake_graph.last_config == {"configurable": {"thread_id": "123@lid"}}


def test_lead_existente_recebe_lid_migra_thread(monkeypatch) -> None:
    classificacao = {
        "origem": "disparo",
        "plataforma": None,
        "campanha": "reativacao",
        "canal": "whatsapp",
        "mensagem": "oi",
        "id_lead": {
            "id_primario": "novo@lid",
            "lid": "novo@lid",
            "jid": "552197@s.whatsapp.net",
            "numero": "552197",
            "usando_lid": True,
        },
    }
    fake_graph = _setup_common(monkeypatch, classificacao)

    monkeypatch.setattr(
        consumer_mod,
        "buscar_lead",
        lambda lid=None, jid=None, numero=None: {"id": "lead-3", "lid": None, "jid": "552197@s.whatsapp.net"},
    )

    calls: list[tuple[str, dict[str, Any]]] = []

    def _upd(lead_id: str, dados: dict[str, Any]) -> dict[str, Any]:
        calls.append((lead_id, dados))
        return {"id": lead_id, "lid": dados.get("lid"), "jid": "552197@s.whatsapp.net"}

    monkeypatch.setattr(consumer_mod, "atualizar_lead", _upd)
    monkeypatch.setattr(consumer_mod, "criar_lead", lambda dados: {"id": "x", **dados})

    consumer = consumer_mod.LeadConsumer("amqp://guest:guest@localhost:5672/")
    result = consumer._process_payload({"dummy": True})

    assert calls == [("lead-3", {"lid": "novo@lid", "usando_lid": True})]
    assert result["thread_id"] == "novo@lid"
    assert fake_graph.last_config == {"configurable": {"thread_id": "novo@lid"}}


def test_lead_existente_com_lid_sem_update(monkeypatch) -> None:
    classificacao = {
        "origem": "organico",
        "plataforma": None,
        "campanha": None,
        "canal": "whatsapp",
        "mensagem": "oi",
        "id_lead": {
            "id_primario": "ok@lid",
            "lid": "ok@lid",
            "jid": "552196@s.whatsapp.net",
            "numero": "552196",
            "usando_lid": True,
        },
    }
    fake_graph = _setup_common(monkeypatch, classificacao)

    monkeypatch.setattr(
        consumer_mod,
        "buscar_lead",
        lambda lid=None, jid=None, numero=None: {"id": "lead-4", "lid": "ok@lid", "jid": "552196@s.whatsapp.net"},
    )

    called = {"updated": False}

    def _upd(lead_id: str, dados: dict[str, Any]) -> dict[str, Any]:
        called["updated"] = True
        return {"id": lead_id, **dados}

    monkeypatch.setattr(consumer_mod, "atualizar_lead", _upd)
    monkeypatch.setattr(consumer_mod, "criar_lead", lambda dados: {"id": "x", **dados})

    consumer = consumer_mod.LeadConsumer("amqp://guest:guest@localhost:5672/")
    result = consumer._process_payload({"dummy": True})

    assert called["updated"] is False
    assert result["thread_id"] == "ok@lid"
    assert fake_graph.last_config == {"configurable": {"thread_id": "ok@lid"}}


def test_on_message_ignora_payload_from_me(monkeypatch) -> None:
    class _FakeChannel:
        def __init__(self) -> None:
            self.ack_tags: list[str] = []

        def basic_ack(self, delivery_tag: str) -> None:
            self.ack_tags.append(delivery_tag)

        def basic_nack(self, delivery_tag: str, requeue: bool = True) -> None:
            raise AssertionError("Nao deveria chamar basic_nack para fromMe")

    class _FakeMethod:
        delivery_tag = "tag-1"

    monkeypatch.setattr(consumer_mod.LeadConsumer, "_build_chatwoot_client", lambda self: None)

    called = {"processed": False}

    def _fake_process(payload: dict[str, Any]) -> dict[str, Any]:
        called["processed"] = True
        return {"ok": True}

    consumer = consumer_mod.LeadConsumer("amqp://guest:guest@localhost:5672/")
    monkeypatch.setattr(consumer, "_process_payload", _fake_process)

    payload = {
        "data": {
            "key": {
                "fromMe": True,
            }
        }
    }

    channel = _FakeChannel()
    consumer._on_message(channel, _FakeMethod(), None, json.dumps(payload).encode("utf-8"))

    assert called["processed"] is False
    assert channel.ack_tags == ["tag-1"]
