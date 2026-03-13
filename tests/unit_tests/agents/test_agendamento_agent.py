import json

from agent.agents import agendamento


def test_verificar_disponibilidade_retorna_horarios() -> None:
    result = agendamento.verificar_disponibilidade.invoke({"data": "2026-03-20", "hora": "10:00"})
    assert "Horários disponíveis" in result
    assert "2026-03-20 10:00" in result


def test_cadastrar_lead_salva_em_json(tmp_path, monkeypatch) -> None:
    leads_file = tmp_path / "leads_cadastrados.json"
    monkeypatch.setattr(agendamento, "LEADS_CADASTRADOS_PATH", leads_file)

    result = agendamento.cadastrar_lead.invoke(
        {
            "nome": "Joao",
            "telefone": "5521999991111",
            "email": "joao@email.com",
            "origem": "organico",
        }
    )

    assert "Lead cadastrado com sucesso" in result
    data = json.loads(leads_file.read_text(encoding="utf-8"))
    assert data["leads"][0]["nome"] == "Joao"
    assert data["leads"][0]["telefone"] == "5521999991111"


def test_confirmar_agendamento_salva_em_json(tmp_path, monkeypatch) -> None:
    ag_file = tmp_path / "agendamentos.json"
    monkeypatch.setattr(agendamento, "AGENDAMENTOS_PATH", ag_file)

    result = agendamento.confirmar_agendamento.invoke(
        {
            "nome": "Maria",
            "data": "2026-03-22",
            "hora": "14:30",
            "contato": "5521988880000",
        }
    )

    assert "Agendamento confirmado" in result
    data = json.loads(ag_file.read_text(encoding="utf-8"))
    assert data["agendamentos"][0]["nome"] == "Maria"
    assert data["agendamentos"][0]["data"] == "2026-03-22"
