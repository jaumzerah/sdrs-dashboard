from __future__ import annotations

import uuid
from typing import Any

from langchain.messages import AIMessage, HumanMessage

from agent.graph import graph as app_graph


class _FakeSupervisorGraph:
    def __init__(self, respostas: list[str]) -> None:
        self._respostas = respostas
        self.calls = 0

    def invoke(self, _state: dict[str, Any]) -> dict[str, Any]:
        idx = self.calls if self.calls < len(self._respostas) else len(self._respostas) - 1
        self.calls += 1
        return {"messages": [AIMessage(content=self._respostas[idx])]}


def _config(thread_prefix: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": f"{thread_prefix}-{uuid.uuid4()}"}}


def test_fluxo_aprovado_primeira_tentativa(monkeypatch) -> None:
    fake_supervisor = _FakeSupervisorGraph(["Resposta SDR Quentes aprovada"]) 
    monkeypatch.setattr("agent.graph.supervisor_graph", fake_supervisor)
    monkeypatch.setattr(
        "agent.agents.avaliador._invoke_avaliador_llm",
        lambda system_prompt, user_prompt: '{"nota": 8.2, "aprovado": true, "feedback": "ok"}',
    )

    result = app_graph.invoke(
        {
            "messages": [HumanMessage(content="Oi, vim pelo site e quero detalhes")],
            "origem": "organico",
            "canal": "whatsapp",
            "mensagem": "Oi, vim pelo site e quero detalhes",
            "mensagem_original": "Oi, vim pelo site e quero detalhes",
            "tentativas_avaliacao": 0,
            "nota_avaliacao": 0.0,
            "feedback_avaliacao": "",
        },
        config=_config("it-avaliador-1"),
    )

    assert fake_supervisor.calls == 1
    assert result["messages"][-1].content == "Resposta SDR Quentes aprovada"
    assert result["nota_avaliacao"] >= 7.0
    assert result["tentativas_avaliacao"] == 1


def test_fluxo_reprova_e_aprova_na_segunda(monkeypatch) -> None:
    fake_supervisor = _FakeSupervisorGraph(["Resposta inicial fraca", "Resposta reescrita aprovada"])
    monkeypatch.setattr("agent.graph.supervisor_graph", fake_supervisor)

    respostas_avaliador = iter(
        [
            '{"nota": 5.0, "aprovado": false, "feedback": "Faltou CTA"}',
            '{"nota": 8.0, "aprovado": true, "feedback": "Agora ficou claro"}',
        ]
    )
    monkeypatch.setattr(
        "agent.agents.avaliador._invoke_avaliador_llm",
        lambda system_prompt, user_prompt: next(respostas_avaliador),
    )

    result = app_graph.invoke(
        {
            "messages": [HumanMessage(content="Recebi seu contato, e agora?")],
            "origem": "disparo",
            "canal": "whatsapp",
            "mensagem": "Recebi seu contato, e agora?",
            "mensagem_original": "Recebi seu contato, e agora?",
            "tentativas_avaliacao": 0,
            "nota_avaliacao": 0.0,
            "feedback_avaliacao": "",
        },
        config=_config("it-avaliador-2"),
    )

    assert fake_supervisor.calls == 2
    assert result["messages"][-1].content == "Resposta reescrita aprovada"
    assert result["nota_avaliacao"] == 8.0
    assert result["tentativas_avaliacao"] == 2


def test_fluxo_tres_reprovacoes_envia_com_alerta(monkeypatch) -> None:
    fake_supervisor = _FakeSupervisorGraph(
        [
            "Resposta anuncio tentativa 1",
            "Resposta anuncio tentativa 2",
            "Resposta anuncio tentativa 3",
        ]
    )
    monkeypatch.setattr("agent.graph.supervisor_graph", fake_supervisor)

    respostas_avaliador = iter(
        [
            '{"nota": 5.0, "aprovado": false, "feedback": "Muito genérico"}',
            '{"nota": 5.0, "aprovado": false, "feedback": "Ainda sem CTA"}',
            '{"nota": 5.0, "aprovado": false, "feedback": "Continua fraco"}',
        ]
    )
    monkeypatch.setattr(
        "agent.agents.avaliador._invoke_avaliador_llm",
        lambda system_prompt, user_prompt: next(respostas_avaliador),
    )

    notes: list[tuple[int, str]] = []

    class _FakeChatwootClient:
        def adicionar_nota(self, conversation_id: int, nota: str) -> None:
            notes.append((conversation_id, nota))

    monkeypatch.setattr("agent.graph.ChatwootClient", _FakeChatwootClient)

    result = app_graph.invoke(
        {
            "messages": [HumanMessage(content="Vi o anuncio, mas ainda estou em dúvida")],
            "origem": "anuncio",
            "canal": "instagram",
            "mensagem": "Vi o anuncio, mas ainda estou em dúvida",
            "mensagem_original": "Vi o anuncio, mas ainda estou em dúvida",
            "chatwoot_conversation_id": 321,
            "tentativas_avaliacao": 0,
            "nota_avaliacao": 0.0,
            "feedback_avaliacao": "",
        },
        config=_config("it-avaliador-3"),
    )

    assert fake_supervisor.calls == 3
    assert result["messages"][-1].content == "Resposta anuncio tentativa 3"
    assert result["tentativas_avaliacao"] == 3
    assert notes
    assert notes[0][0] == 321
    assert "sem aprovação após 3 tentativas" in notes[0][1]
