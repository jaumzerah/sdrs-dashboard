"""Simple async smoke test for a running LangGraph server."""

from __future__ import annotations

import asyncio

from langgraph_sdk import get_client


async def main() -> None:
    client = get_client(url="http://127.0.0.1:2024")
    assistants = await client.assistants.search()
    assistant_id = assistants[0]["assistant_id"]
    thread = await client.threads.create()

    async for chunk in client.runs.stream(
        thread["thread_id"],
        assistant_id,
        input={
            "messages": [
                {
                    "role": "user",
                    "content": "Explique como subir um workflow LangGraph com Studio.",
                }
            ]
        },
    ):
        print(chunk.event, chunk.data)


if __name__ == "__main__":
    asyncio.run(main())
