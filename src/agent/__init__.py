"""Agent package entrypoints."""

from __future__ import annotations

from typing import Any

__all__ = ["graph"]


def __getattr__(name: str) -> Any:
    """Lazy-load graph to avoid import side effects on utility modules."""
    if name == "graph":
        from agent.graph import graph

        return graph
    raise AttributeError(name)
