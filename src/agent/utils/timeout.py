"""Timeout utility for sync execution paths."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Callable, TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)


def executar_com_timeout(fn: Callable[[], T], segundos: float, fallback_fn: Callable[[], T]) -> T:
    """Execute a function with timeout and fallback on timeout.

    If fn exceeds the timeout, logs a warning and returns fallback_fn().
    """
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(fn)
        try:
            return future.result(timeout=segundos)
        except TimeoutError:
            logger.warning("Timeout excedido no ciclo de avaliação")
            return fallback_fn()
