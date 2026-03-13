from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from agent import consumer as consumer_mod


class _FakeGraph:
    def __init__(self, messages: list[Any]) -> None:
        self._messages = messages

    def invoke(self, state_input: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        return {"messages": self._messages}


class _FakeEvolutionClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def enviar_mensagem(self, numero: str, texto: str) -> dict[str, Any]:
        self.calls.append((numero, texto))
        return {"status": "ok"}


def _base_classificacao(numero: str | None) -> dict[str, Any]:
    return {
        "origem": "organico",
        "plataforma": None,
        "campanha": None,
        "canal": "whatsapp",
        "mensagem": "oi",
        "id_lead": {
            "id_primario": "lead-123@lid",
            "lid": "lead-123@lid",
            "jid": "5521999@s.whatsapp.net",
            "numero": numero,
            "usando_lid": True,
        },
    }


def _prepare_common(
    monkeypatch,
    classificacao: dict[str, Any],
    messages: list[Any],
    evolution_client: _FakeEvolutionClient,
) -> None:
    monkeypatch.setattr(consumer_mod, "classificar_origem", lambda payload: classificacao)
    monkeypatch.setattr(consumer_mod, "preparar_entrada_supervisor", lambda c: {"messages": [{"role": "user", "content": "x"}]})
    monkeypatch.setattr(consumer_mod, "_get_graph", lambda: _FakeGraph(messages))
    monkeypatch.setattr(consumer_mod, "route_target_from_classificacao", lambda origem, mensagem=None: "sdr_quentes")
    monkeypatch.setattr(consumer_mod.LeadConsumer, "_build_chatwoot_client", lambda self: None)
    monkeypatch.setattr(consumer_mod.LeadConsumer, "_build_evolution_client", lambda self: evolution_client)
    monkeypatch.setattr(
        consumer_mod.LeadConsumer,
        "_upsert_lead",
        lambda self, c, app: ({"id": "lead-1", "chatwoot_contact_id": None}, c["id_lead"]["id_primario"]),
    )


def test_envio_resposta_usa_ultima_ai_message(monkeypatch) -> None:
    classificacao = _base_classificacao("5521999887766")
    evolution = _FakeEvolutionClient()
    messages = [
        HumanMessage(content="mensagem do lead"),
        AIMessage(content="rascunho"),
        AIMessage(content="resposta final"),
    ]
    _prepare_common(monkeypatch, classificacao, messages, evolution)

    consumer = consumer_mod.LeadConsumer("amqp://guest:guest@localhost:5672/")
    result = consumer._process_payload({"pushName": "Lead"})

    assert evolution.calls == [("5521999887766", "resposta final")]
    assert result["resposta"] == "resposta final"


def test_envio_resposta_numero_e_texto_corretos(monkeypatch) -> None:
    classificacao = _base_classificacao("5521000000000")
    evolution = _FakeEvolutionClient()
    messages = [AIMessage(content="ola! tudo bem?")]
    _prepare_common(monkeypatch, classificacao, messages, evolution)

    consumer = consumer_mod.LeadConsumer("amqp://guest:guest@localhost:5672/")
    consumer._process_payload({"pushName": "Lead"})

    assert len(evolution.calls) == 1
    assert evolution.calls[0][0] == "5521000000000"
    assert evolution.calls[0][1] == "ola! tudo bem?"


def test_lead_sem_numero_loga_warning_sem_excecao(monkeypatch, caplog) -> None:
    classificacao = _base_classificacao(None)
    evolution = _FakeEvolutionClient()
    messages = [AIMessage(content="resposta sem numero")]
    _prepare_common(monkeypatch, classificacao, messages, evolution)

    consumer = consumer_mod.LeadConsumer("amqp://guest:guest@localhost:5672/")

    with caplog.at_level("WARNING"):
        result = consumer._process_payload({"pushName": "Lead"})

    assert result["thread_id"] == "lead-123@lid"
    assert evolution.calls == []
    assert any("Lead lead-123@lid sem número — resposta não enviada" in rec.message for rec in caplog.records)
