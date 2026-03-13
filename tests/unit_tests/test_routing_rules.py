from agent.routing.rules import has_intencao_agendamento, route_target, route_target_from_classificacao


def test_route_to_sdr_frios_for_cold_outreach() -> None:
    assert route_target("whatsapp", "cold_outreach", "lista_prospeccao") == "sdr_frios"


def test_route_to_sdr_quentes_for_organic_site() -> None:
    assert route_target("site", "organico", "blog") == "sdr_quentes"


def test_route_to_sdr_anuncios_for_meta_ads() -> None:
    assert route_target("instagram", "inbound", "meta_ads") == "sdr_anuncios"


def test_route_target_from_classificacao_values() -> None:
    assert route_target_from_classificacao("disparo") == "sdr_frios"
    assert route_target_from_classificacao("anuncio") == "sdr_anuncios"
    assert route_target_from_classificacao("organico") == "sdr_quentes"


def test_prioriza_agendamento_sobre_origem() -> None:
    assert route_target_from_classificacao("disparo", "quero marcar uma reuniao") == "sdr_agendamento"
    assert route_target_from_classificacao("anuncio", "tem horario essa semana?") == "sdr_agendamento"


def test_detecta_intencao_agendamento_com_acentos() -> None:
    assert has_intencao_agendamento("Quero agendar, tem disponibilidade?") is True
    assert has_intencao_agendamento("Apenas queria saber o preco") is False
