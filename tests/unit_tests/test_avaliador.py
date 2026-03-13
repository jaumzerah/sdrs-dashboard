from agent.agents.avaliador import avaliar_resposta


def test_avaliador_aprovado_primeira_tentativa(monkeypatch) -> None:
    monkeypatch.setattr(
        "agent.agents.avaliador._invoke_avaliador_llm",
        lambda system_prompt, user_prompt: '{"nota": 8.5, "aprovado": true, "feedback": "Boa resposta."}',
    )

    state = {
        "resposta_pendente": "Olá! Posso te ajudar a agendar agora.",
        "tentativas_avaliacao": 0,
        "origem": "organico",
        "canal": "whatsapp",
        "mensagem_original": "Quero saber como funciona.",
    }

    result = avaliar_resposta(state)

    assert result["nota_avaliacao"] >= 7.0
    assert result["feedback_avaliacao"] == "Boa resposta."
    assert result["tentativas_avaliacao"] == 1


def test_avaliador_reprovado_com_feedback(monkeypatch) -> None:
    monkeypatch.setattr(
        "agent.agents.avaliador._invoke_avaliador_llm",
        lambda system_prompt, user_prompt: '{"nota": 5.2, "aprovado": false, "feedback": "Faltou CTA claro."}',
    )

    state = {
        "resposta_pendente": "Podemos conversar depois.",
        "tentativas_avaliacao": 1,
        "origem": "disparo",
        "canal": "whatsapp",
        "mensagem_original": "Ok, e agora?",
    }

    result = avaliar_resposta(state)

    assert result["nota_avaliacao"] == 5.2
    assert result["feedback_avaliacao"] == "Faltou CTA claro."
    assert result["tentativas_avaliacao"] == 2


def test_avaliador_falha_parse_json(monkeypatch) -> None:
    monkeypatch.setattr(
        "agent.agents.avaliador._invoke_avaliador_llm",
        lambda system_prompt, user_prompt: "resposta invalida sem json",
    )

    state = {
        "resposta_pendente": "Texto qualquer",
        "tentativas_avaliacao": 2,
        "origem": "anuncio",
        "canal": "instagram",
        "mensagem_original": "Me chama",
    }

    result = avaliar_resposta(state)

    assert result["nota_avaliacao"] == 0.0
    assert "Erro ao interpretar" in result["feedback_avaliacao"]
    assert result["tentativas_avaliacao"] == 3
