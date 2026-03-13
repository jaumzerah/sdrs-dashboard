from __future__ import annotations

from typing import Any

from agent.integrations.evolution import EvolutionClient


class _FakeResponse:
    def __init__(self, data: Any) -> None:
        self._data = data
        self.content = b"ok"

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        return self._data


def test_configurar_rabbitmq_instancia_monta_body_e_header(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def _fake_request(method: str, url: str, headers: dict[str, str], timeout: int, **kwargs: Any):
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = headers
        captured["timeout"] = timeout
        captured["json"] = kwargs.get("json")
        return _FakeResponse({"ok": True})

    monkeypatch.setattr("agent.integrations.evolution.requests.request", _fake_request)
    client = EvolutionClient(
        base_url="http://localhost:8080",
        api_key="token-123",
        instance="instancia-a",
    )

    result = client.configurar_rabbitmq_instancia()

    assert result == {"ok": True}
    assert captured["method"] == "POST"
    assert captured["url"] == "http://localhost:8080/rabbitmq/set/instancia-a"
    assert captured["headers"]["apikey"] == "token-123"
    assert captured["json"] == {"enabled": True, "events": ["MESSAGES_UPSERT"]}


def test_enviar_mensagem_monta_numero_e_texto(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def _fake_request(method: str, url: str, headers: dict[str, str], timeout: int, **kwargs: Any):
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = headers
        captured["timeout"] = timeout
        captured["json"] = kwargs.get("json")
        return _FakeResponse({"id": "msg-1"})

    monkeypatch.setattr("agent.integrations.evolution.requests.request", _fake_request)
    client = EvolutionClient(
        base_url="http://localhost:8080",
        api_key="token-123",
        instance="instancia-a",
    )

    result = client.enviar_mensagem(numero="5521999887766", texto="Ola, lead")

    assert result == {"id": "msg-1"}
    assert captured["method"] == "POST"
    assert captured["url"] == "http://localhost:8080/message/sendText/instancia-a"
    assert captured["json"] == {"number": "5521999887766", "text": "Ola, lead"}


def test_obter_status_instancia_chama_endpoint_correto(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def _fake_request(method: str, url: str, headers: dict[str, str], timeout: int, **kwargs: Any):
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = headers
        captured["timeout"] = timeout
        captured["kwargs"] = kwargs
        return _FakeResponse([{"name": "instancia-a", "connectionStatus": "open"}])

    monkeypatch.setattr("agent.integrations.evolution.requests.request", _fake_request)
    client = EvolutionClient(
        base_url="http://localhost:8080",
        api_key="token-123",
        instance="instancia-a",
    )

    result = client.obter_status_instancia()

    assert captured["method"] == "GET"
    assert captured["url"] == "http://localhost:8080/instance/fetchInstances"
    assert result == {"data": [{"name": "instancia-a", "connectionStatus": "open"}]}
