from __future__ import annotations

from typing import Any

from agent import consumer as consumer_mod


class _FakeGraph:
    def invoke(self, state_input: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        return {"messages": [{"content": "ok"}]}


class _FakeChatwootClient:
    def __init__(self) -> None:
        self.inbox_id = 1
        self.buscar_calls: list[dict[str, Any]] = []
        self.conversa_calls: list[tuple[int, int]] = []
        self.label_calls: list[tuple[int, list[str]]] = []
        self.nota_calls: list[tuple[int, str]] = []

    def buscar_ou_criar_contato(self, id_lead: dict[str, Any], nome: str | None = None) -> dict[str, Any]:
        self.buscar_calls.append({"id_lead": id_lead, "nome": nome})
        return {"id": 77}

    def criar_conversa(self, contact_id: int, inbox_id: int) -> dict[str, Any]:
        self.conversa_calls.append((contact_id, inbox_id))
        return {"id": 999}

    def adicionar_label(self, conversation_id: int, labels: list[str]) -> None:
        self.label_calls.append((conversation_id, labels))

    def adicionar_nota(self, conversation_id: int, nota: str) -> None:
        self.nota_calls.append((conversation_id, nota))


def _base_classificacao(origem: str, plataforma: str | None = None) -> dict[str, Any]:
    return {
        "origem": origem,
        "plataforma": plataforma,
        "campanha": "campanha-x",
        "canal": "whatsapp",
        "mensagem": "oi",
        "id_lead": {
            "id_primario": "lead@id",
            "lid": "lead@id",
            "jid": "552199@s.whatsapp.net",
            "numero": "552199",
            "usando_lid": True,
        },
    }


def _prepare_common(monkeypatch, classificacao: dict[str, Any], lead: dict[str, Any], chatwoot_client: _FakeChatwootClient) -> None:
    monkeypatch.setattr(consumer_mod, "classificar_origem", lambda payload: classificacao)
    monkeypatch.setattr(consumer_mod, "preparar_entrada_supervisor", lambda c: {"messages": [{"role": "user", "content": "x"}]})
    monkeypatch.setattr(consumer_mod, "_get_graph", lambda: _FakeGraph())
    monkeypatch.setattr(consumer_mod, "route_target_from_classificacao", lambda origem, mensagem=None: "sdr_quentes")
    monkeypatch.setattr(consumer_mod.LeadConsumer, "_build_chatwoot_client", lambda self: chatwoot_client)
    monkeypatch.setattr(
        consumer_mod.LeadConsumer,
        "_upsert_lead",
        lambda self, c, app: (lead, c["id_lead"]["id_primario"]),
    )


def test_lead_novo_chatwoot_cria_contato_conversa_label(monkeypatch) -> None:
    classificacao = _base_classificacao("organico", None)
    lead = {"id": "lead-1", "chatwoot_contact_id": None}
    chatwoot = _FakeChatwootClient()
    _prepare_common(monkeypatch, classificacao, lead, chatwoot)

    updates: list[tuple[str, dict[str, Any]]] = []

    def _upd(lead_id: str, dados: dict[str, Any]) -> dict[str, Any]:
        updates.append((lead_id, dados))
        return {"id": lead_id, **dados}

    monkeypatch.setattr(consumer_mod, "atualizar_lead", _upd)

    consumer = consumer_mod.LeadConsumer("amqp://guest:guest@localhost:5672/")
    consumer._process_payload({"pushName": "Lead Nome"})

    assert len(chatwoot.buscar_calls) == 1
    assert chatwoot.conversa_calls == [(77, 1)]
    assert chatwoot.label_calls == [(999, ["lead_quente"])]
    assert updates == [("lead-1", {"chatwoot_contact_id": 77})]
    assert "Lead recebido via whatsapp" in chatwoot.nota_calls[0][1]


def test_lead_com_contact_id_nao_chama_buscar_ou_criar(monkeypatch) -> None:
    classificacao = _base_classificacao("disparo", None)
    lead = {"id": "lead-2", "chatwoot_contact_id": 1234}
    chatwoot = _FakeChatwootClient()
    _prepare_common(monkeypatch, classificacao, lead, chatwoot)

    monkeypatch.setattr(consumer_mod, "atualizar_lead", lambda lead_id, dados: {"id": lead_id, **dados})

    consumer = consumer_mod.LeadConsumer("amqp://guest:guest@localhost:5672/")
    consumer._process_payload({"pushName": "Lead Nome"})

    assert chatwoot.buscar_calls == []
    assert chatwoot.conversa_calls == [(1234, 1)]
    assert chatwoot.label_calls == [(999, ["lead_frio"])]


def test_label_correto_para_origem_plataforma(monkeypatch) -> None:
    casos = [
        ("disparo", None, ["lead_frio"]),
        ("organico", None, ["lead_quente"]),
        ("anuncio", "meta", ["anuncio_meta"]),
        ("anuncio", "google", ["anuncio_google"]),
    ]

    for origem, plataforma, expected_label in casos:
        classificacao = _base_classificacao(origem, plataforma)
        lead = {"id": "lead-3", "chatwoot_contact_id": 2000}
        chatwoot = _FakeChatwootClient()
        _prepare_common(monkeypatch, classificacao, lead, chatwoot)
        monkeypatch.setattr(consumer_mod, "atualizar_lead", lambda lead_id, dados: {"id": lead_id, **dados})

        consumer = consumer_mod.LeadConsumer("amqp://guest:guest@localhost:5672/")
        consumer._process_payload({"pushName": "Lead Nome"})

        assert chatwoot.label_calls == [(999, expected_label)]
