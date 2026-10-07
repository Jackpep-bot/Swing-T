"""Async token bucket used by HTTP deliverers and pollers."""
from __future__ import annotations

import asyncio
import time


class TokenBucket:
    def __init__(self, rate_per_s: float, capacity: int | None = None, clock=time.monotonic, sleeper=asyncio.sleep):
        self.rate = rate_per_s
        self.capacity = capacity if capacity is not None else max(1, int(rate_per_s))
        self._tokens = float(self.capacity)
        self._clock = clock
        self._sleep = sleeper
        self._last = clock()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = self._clock()
        self._tokens = min(self.capacity, self._tokens + (now - self._last) * self.rate)
        self._last = now

    async def acquire(self) -> float:
        """Wait until a token is available; returns seconds waited."""
        async with self._lock:
            self._refill()
            waited = 0.0
            if self._tokens < 1.0:
                waited = (1.0 - self._tokens) / self.rate
                await self._sleep(waited)
                self._refill()
            self._tokens = max(0.0, self._tokens - 1.0)
            return waited
