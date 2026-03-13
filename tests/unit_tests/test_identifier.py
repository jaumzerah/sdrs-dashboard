from agent.utils.identifier import extrair_id_lead


def test_extrai_lid_como_id_primario() -> None:
    payload = {
        "key": {
            "lid": "123456@lid",
            "remoteJid": "5521988887777@s.whatsapp.net",
        }
    }

    result = extrair_id_lead(payload)

    assert result["id_primario"] == "123456@lid"
    assert result["lid"] == "123456@lid"
    assert result["jid"] == "5521988887777@s.whatsapp.net"
    assert result["numero"] == "5521988887777"
    assert result["usando_lid"] is True


def test_extrai_participant_lid_como_fallback_de_lid() -> None:
    payload = {
        "key": {
            "participant_lid": "abcxyz@lid",
            "remoteJid": "5521999990000@s.whatsapp.net",
        }
    }

    result = extrair_id_lead(payload)

    assert result["id_primario"] == "abcxyz@lid"
    assert result["lid"] == "abcxyz@lid"
    assert result["jid"] == "5521999990000@s.whatsapp.net"
    assert result["numero"] == "5521999990000"
    assert result["usando_lid"] is True


def test_fallback_para_jid_quando_nao_tem_lid() -> None:
    payload = {"key": {"remoteJid": "5521999@s.whatsapp.net"}}

    result = extrair_id_lead(payload)

    assert result["id_primario"] == "5521999@s.whatsapp.net"
    assert result["lid"] is None
    assert result["jid"] == "5521999@s.whatsapp.net"
    assert result["numero"] == "5521999"
    assert result["usando_lid"] is False


def test_normaliza_numero_sem_sufixo() -> None:
    payload = {"key": {"remoteJid": "+55 (21) 98888-7777"}}

    result = extrair_id_lead(payload)

    assert result["id_primario"] == "+55 (21) 98888-7777"
    assert result["numero"] == "5521988887777"
    assert result["usando_lid"] is False


def test_payload_sem_key_retorna_nulos() -> None:
    result = extrair_id_lead({})

    assert result["id_primario"] is None
    assert result["lid"] is None
    assert result["jid"] is None
    assert result["numero"] is None
    assert result["usando_lid"] is False
