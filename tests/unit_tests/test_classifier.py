from __future__ import annotations

from agent.utils import classifier


def test_classifica_como_anuncio_meta() -> None:
    payload = {
        "key": {"remoteJid": "5521988887777@s.whatsapp.net"},
        "data": {
            "contextInfo": {
                "externalAdReply": {
                    "sourceId": "ad_123",
                    "title": "Campanha Meta Maio",
                }
            }
        },
        "message": {"conversation": "Oi, vi seu anuncio"},
    }

    result = classifier.classificar_origem(payload)

    assert result["origem"] == "anuncio"
    assert result["plataforma"] == "meta"
    assert result["anuncio_id"] == "ad_123"
    assert result["campanha"] == "Campanha Meta Maio"


def test_classifica_disparo_por_lid(monkeypatch) -> None:
    monkeypatch.setattr(
        classifier,
        "esta_na_base_disparados",
        lambda lid=None, jid=None, numero=None: {
            "lid": lid,
            "jid": jid,
            "numero": numero,
            "campanha": "reativacao-maio-2025",
        },
    )

    payload = {
        "key": {
            "lid": "123456@lid",
            "remoteJid": "5521999999999@s.whatsapp.net",
        },
        "message": {"conversation": "voltei aqui"},
    }
    result = classifier.classificar_origem(payload)

    assert result["origem"] == "disparo"
    assert result["campanha"] == "reativacao-maio-2025"


def test_classifica_disparo_por_jid_fallback(monkeypatch) -> None:
    monkeypatch.setattr(
        classifier,
        "esta_na_base_disparados",
        lambda lid=None, jid=None, numero=None: {
            "campanha": "campanha-jid",
            "jid": jid,
        }
        if jid == "5521977776666@s.whatsapp.net"
        else None,
    )

    payload = {
        "key": {
            "remoteJid": "5521977776666@s.whatsapp.net",
        },
        "message": {"conversation": "respondendo disparo"},
    }
    result = classifier.classificar_origem(payload)

    assert result["origem"] == "disparo"
    assert result["campanha"] == "campanha-jid"


def test_classifica_disparo_por_numero_fallback(monkeypatch) -> None:
    monkeypatch.setattr(
        classifier,
        "esta_na_base_disparados",
        lambda lid=None, jid=None, numero=None: {
            "campanha": "campanha-numero",
            "numero": numero,
        }
        if numero == "5521966665555"
        else None,
    )

    payload = {
        "key": {"remoteJid": "55 (21) 96666-5555"},
        "message": {"conversation": "oi"},
    }
    result = classifier.classificar_origem(payload)

    assert result["origem"] == "disparo"
    assert result["campanha"] == "campanha-numero"


def test_classifica_organico_por_padrao(monkeypatch) -> None:
    monkeypatch.setattr(classifier, "esta_na_base_disparados", lambda **_: None)

    payload = {
        "key": {"remoteJid": "5521911110000@s.whatsapp.net"},
        "message": {"conversation": "vim pelo site"},
    }
    result = classifier.classificar_origem(payload)

    assert result["origem"] == "organico"
    assert result["plataforma"] is None
    assert result["canal"] == "whatsapp"
