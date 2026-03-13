from agent.agents import (
    build_sdr_anuncios_agent,
    build_sdr_frios_agent,
    build_sdr_quentes_agent,
)


def test_sdr_agent_builders_are_callable() -> None:
    assert callable(build_sdr_frios_agent)
    assert callable(build_sdr_quentes_agent)
    assert callable(build_sdr_anuncios_agent)
