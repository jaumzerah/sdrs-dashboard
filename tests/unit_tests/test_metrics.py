from __future__ import annotations

import time

from agent.agents.avaliador import avaliar_resposta_com_timeout
from agent.utils.timeout import executar_com_timeout


def test_executar_com_timeout_retorna_resultado_normal() -> None:
    result = executar_com_timeout(lambda: "ok", segundos=1, fallback_fn=lambda: "fallback")
    assert result == "ok"


def test_executar_com_timeout_dispara_fallback_e_warning(caplog) -> None:
    def _slow() -> str:
        time.sleep(0.2)
        return "late"

    with caplog.at_level("WARNING"):
        result = executar_com_timeout(_slow, segundos=0.01, fallback_fn=lambda: "fallback")

    assert result == "fallback"
    assert any("Timeout excedido no ciclo de avaliação" in rec.message for rec in caplog.records)


def test_registrar_avaliacao_chamado_no_normal_e_timeout(monkeypatch) -> None:
    calls: list[dict] = []

    def _fake_registrar(**kwargs):
        calls.append(kwargs)
        return {"id": "x"}

    monkeypatch.setattr("agent.agents.avaliador.registrar_avaliacao", _fake_registrar)

    monkeypatch.setattr(
        "agent.agents.avaliador._invoke_avaliador_llm",
        lambda system_prompt, user_prompt: '{"nota": 8.0, "aprovado": true, "feedback": "ok"}',
    )

    state = {
        "lead_id": "lead-1",
        "sdr_origem": "sdr_quentes",
        "resposta_pendente": "resposta",
        "tentativas_avaliacao": 0,
        "origem": "organico",
        "canal": "whatsapp",
        "mensagem_original": "mensagem",
    }
    result_ok = avaliar_resposta_com_timeout(state, timeout_segundos=1)
    assert result_ok["nota_avaliacao"] == 8.0
    assert len(calls) == 1
    assert calls[0]["aprovado"] is True

    def _slow_llm(system_prompt, user_prompt):
        time.sleep(0.2)
        return '{"nota": 9.0, "aprovado": true, "feedback": "late"}'

    monkeypatch.setattr("agent.agents.avaliador._invoke_avaliador_llm", _slow_llm)
    state_timeout = {
        "lead_id": "lead-1",
        "sdr_origem": "sdr_quentes",
        "resposta_pendente": "resposta",
        "tentativas_avaliacao": 0,
        "origem": "organico",
        "canal": "whatsapp",
        "mensagem_original": "mensagem",
    }
    result_timeout = avaliar_resposta_com_timeout(state_timeout, timeout_segundos=0.01)
    assert result_timeout["nota_avaliacao"] == 0.0
    assert "Timeout excedido" in result_timeout["feedback_avaliacao"]
    assert len(calls) == 2
    assert calls[1]["aprovado"] is False
