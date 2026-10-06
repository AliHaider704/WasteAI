# server/app/concurrency.py
"""Global inference limiter: 2 slots, wait up to 5 s, then 503 `overloaded`."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

MAX_CONCURRENT = 2
MAX_WAIT_S = 5.0


class OverloadedError(Exception):
    code = "overloaded"
    status = 503


class Limiter:
    def __init__(self, slots: int = MAX_CONCURRENT, wait_s: float = MAX_WAIT_S) -> None:
        self._sem = asyncio.Semaphore(slots)
        self._wait_s = wait_s

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        try:
            await asyncio.wait_for(self._sem.acquire(), timeout=self._wait_s)
        except asyncio.TimeoutError:
            raise OverloadedError() from None
        try:
            yield
        finally:
            self._sem.release()


limiter = Limiter()
