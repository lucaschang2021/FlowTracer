from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.schemas.health import DependencyStatus, ReadinessChecks

Probe = Callable[[], Awaitable[None]]


class ReadinessService:
    def __init__(
        self,
        database_probe: Probe,
        redis_probe: Probe,
        timeout_seconds: float = 2.0,
    ) -> None:
        self._database_probe = database_probe
        self._redis_probe = redis_probe
        self._timeout_seconds = min(timeout_seconds, 2.0)

    async def _run_probe(self, probe: Probe) -> DependencyStatus:
        try:
            await asyncio.wait_for(probe(), timeout=self._timeout_seconds)
        except TimeoutError:
            return "timeout"
        except Exception:
            return "unavailable"
        return "ok"

    async def check(self) -> ReadinessChecks:
        database, redis = await asyncio.gather(
            self._run_probe(self._database_probe),
            self._run_probe(self._redis_probe),
        )
        return ReadinessChecks(database=database, redis=redis)


def build_readiness_service(
    engine: AsyncEngine,
    redis_client: Redis,
    timeout_seconds: float,
) -> ReadinessService:
    async def database_probe() -> None:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    async def redis_probe() -> None:
        if not await redis_client.ping():
            raise RuntimeError("Redis did not acknowledge PING")

    return ReadinessService(database_probe, redis_probe, timeout_seconds)
