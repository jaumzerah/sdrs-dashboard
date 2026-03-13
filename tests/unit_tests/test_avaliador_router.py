from agent.routing.avaliador_router import should_send


def test_router_enviar_when_nota_aprovada() -> None:
    assert should_send({"nota_avaliacao": 8.0, "tentativas_avaliacao": 1}) == "enviar"


def test_router_refazer_primeira_tentativa() -> None:
    assert should_send({"nota_avaliacao": 5.0, "tentativas_avaliacao": 1}) == "refazer"


def test_router_refazer_segunda_tentativa() -> None:
    assert should_send({"nota_avaliacao": 5.0, "tentativas_avaliacao": 2}) == "refazer"


def test_router_enviar_com_alerta_terceira_tentativa() -> None:
    assert should_send({"nota_avaliacao": 5.0, "tentativas_avaliacao": 3}) == "enviar_com_alerta"


def test_router_enviar_com_alerta_nota_69_tentativa_3() -> None:
    assert should_send({"nota_avaliacao": 6.9, "tentativas_avaliacao": 3}) == "enviar_com_alerta"
