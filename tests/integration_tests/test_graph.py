import os

import pytest

from agent import graph

pytestmark = pytest.mark.anyio


async def test_agent_simple_passthrough() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY is not set")

    inputs = {
        "messages": [
            {"role": "user", "content": "Some 2 e 3 e responda em portugues."}
        ]
    }
    res = await graph.ainvoke(inputs)
    assert res is not None
    assert "messages" in res
