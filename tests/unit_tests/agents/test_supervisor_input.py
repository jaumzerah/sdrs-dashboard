import logging

from agent.agents.supervisor import preparar_entrada_supervisor


def test_preparar_entrada_supervisor_loga_identificador_e_origem(caplog) -> None:
    classificacao = {
        "origem": "disparo",
        "mensagem": "Oi, recebi seu contato",
        "canal": "whatsapp",
        "id_lead": {
            "id_primario": "123@lid",
            "lid": "123@lid",
            "jid": "5521999999999@s.whatsapp.net",
            "numero": "5521999999999",
            "usando_lid": True,
        },
    }

    with caplog.at_level(logging.INFO):
        payload = preparar_entrada_supervisor(classificacao)

    assert "messages" in payload
    assert payload["messages"][0]["role"] == "user"
    assert "dados_classificacao=" in payload["messages"][0]["content"]
    assert any("Lead classificado para supervisor" in rec.message for rec in caplog.records)
