from __future__ import annotations

from typing import Any

from agent.disparo.sender import enviar_disparo


def _lead() -> dict[str, Any]:
    return {
        "id_primario": "5521999887766@s.whatsapp.net",
        "numero": "5521999887766",
        "mensagem": "Ola! Tenho uma sugestao para sua loja.",
        "campanha": "campanha-outubro",
    }


def test_enviar_disparo_retorna_false_quando_ja_existe(monkeypatch) -> None:
    monkeypatch.setattr("agent.disparo.sender.esta_na_base_disparados", lambda **kwargs: {"id": "d1"})

    called = {"enviado": False, "registrado": False}

    class _FakeClient:
        def enviar_mensagem(self, numero: str, texto: str) -> dict[str, Any]:
            called["enviado"] = True
            return {"ok": True}

    monkeypatch.setattr("agent.disparo.sender.EvolutionClient", lambda instance=None: _FakeClient())
    monkeypatch.setattr("agent.disparo.sender.registrar_disparo", lambda **kwargs: called.__setitem__("registrado", True))

    assert enviar_disparo(_lead()) is False
    assert called["enviado"] is False
    assert called["registrado"] is False


def test_enviar_disparo_retorna_true_e_registra(monkeypatch) -> None:
    monkeypatch.setattr("agent.disparo.sender.esta_na_base_disparados", lambda **kwargs: None)

    sent: list[tuple[str, str]] = []
    registered: list[dict[str, Any]] = []

    class _FakeClient:
        def enviar_mensagem(self, numero: str, texto: str) -> dict[str, Any]:
            sent.append((numero, texto))
            return {"ok": True}

    monkeypatch.setattr("agent.disparo.sender.EvolutionClient", lambda instance=None: _FakeClient())
    monkeypatch.setattr("agent.disparo.sender.registrar_disparo", lambda **kwargs: registered.append(kwargs) or {"id": "d2"})

    assert enviar_disparo(_lead()) is True
    assert sent == [("5521999887766", "Ola! Tenho uma sugestao para sua loja.")]
    assert len(registered) == 1
    assert registered[0]["campanha"] == "campanha-outubro"


def test_enviar_disparo_retorna_false_sem_registrar_em_falha(monkeypatch) -> None:
    monkeypatch.setattr("agent.disparo.sender.esta_na_base_disparados", lambda **kwargs: None)

    class _FakeClient:
        def enviar_mensagem(self, numero: str, texto: str) -> dict[str, Any]:
            raise RuntimeError("falha evolution")

    registered = {"called": False}

    monkeypatch.setattr("agent.disparo.sender.EvolutionClient", lambda instance=None: _FakeClient())
    monkeypatch.setattr("agent.disparo.sender.registrar_disparo", lambda **kwargs: registered.__setitem__("called", True))

    assert enviar_disparo(_lead()) is False
    assert registered["called"] is False
