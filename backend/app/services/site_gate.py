"""Per-site execution gate: crawl delay, request-rate spacing, and serialization.

Executes the effective SitePolicy values instead of only deriving them: every request
passes through :meth:`SiteGate.guard`, which serializes requests per host and sleeps
out the remaining interval between consecutive requests — the crawl delay or the
requests-per-minute spacing, whichever is longer. The gate is instance-scoped (created
per routed run, or injected by tests); it holds no module-level state.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

type Sleep = Callable[[float], Awaitable[None]]
MILLISECONDS_PER_MINUTE = 60_000


@dataclass(slots=True)
class SiteGate:
    sleep: Sleep = asyncio.sleep
    enforced_in_flight: int = 1
    _locks: dict[str, asyncio.Lock] = field(default_factory=dict)
    _last_request_at: dict[str, float] = field(default_factory=dict)
    delays_applied_ms: list[int] = field(default_factory=list)

    def spacing_ms(self, *, crawl_delay_ms: int, requests_per_minute: int) -> int:
        rate_spacing = MILLISECONDS_PER_MINUTE // max(1, requests_per_minute)
        return max(0, crawl_delay_ms, rate_spacing)

    def _lock_for(self, host: str) -> asyncio.Lock:
        lock = self._locks.get(host)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[host] = lock
        return lock

    @asynccontextmanager
    async def guard(
        self,
        host: str,
        *,
        crawl_delay_ms: int,
        requests_per_minute: int,
    ) -> AsyncIterator[int]:
        """Hold the per-host slot for one request and space it from the previous one.

        Yields the applied delay in milliseconds (0 when the previous request is far
        enough in the past). The lock is held while the caller's request executes, so
        concurrent callers on the same host are serialized under the configured cap.
        """
        spacing = self.spacing_ms(
            crawl_delay_ms=crawl_delay_ms, requests_per_minute=requests_per_minute
        )
        async with self._lock_for(host):
            last = self._last_request_at.get(host)
            delay_ms = 0
            if last is not None and spacing > 0:
                elapsed_ms = (time.monotonic() - last) * 1000
                delay_ms = max(0, round(spacing - elapsed_ms))
                if delay_ms > 0:
                    self.delays_applied_ms.append(delay_ms)
                    await self.sleep(delay_ms / 1000)
            self._last_request_at[host] = time.monotonic()
            yield delay_ms
