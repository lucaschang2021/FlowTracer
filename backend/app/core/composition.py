from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.db.session import create_database_engine, create_session_factory
from app.domains.provider_ports import AnalysisProvider, EmbeddingProvider
from app.providers.analysis import build_provider
from app.providers.embedding import build_embedding_provider
from app.services.events import EventPublisher, RedisEventPublisher
from app.services.readiness import ReadinessService, build_readiness_service

type DatabaseOperation[ResultT] = Callable[[async_sessionmaker[AsyncSession]], Awaitable[ResultT]]
type EventOperation[ResultT] = Callable[[EventPublisher], Awaitable[ResultT]]


@dataclass(frozen=True, slots=True)
class ApiDependencies:
    session_factory: async_sessionmaker[AsyncSession] | None
    redis_client: Redis | None
    event_publisher: EventPublisher | None
    readiness_service: ReadinessService
    embedding_provider: EmbeddingProvider


def build_analysis_dependency(settings: Settings) -> AnalysisProvider:
    return build_provider(settings)


def build_embedding_dependency(settings: Settings) -> EmbeddingProvider:
    return build_embedding_provider(settings)


async def with_database[ResultT](
    settings: Settings,
    operation: DatabaseOperation[ResultT],
) -> ResultT:
    engine = create_database_engine(settings)
    try:
        return await operation(create_session_factory(engine))
    finally:
        await engine.dispose()


async def with_events[ResultT](settings: Settings, operation: EventOperation[ResultT]) -> ResultT:
    redis_client = Redis.from_url(settings.redis_url.get_secret_value(), decode_responses=True)
    try:
        return await operation(RedisEventPublisher(redis_client))
    finally:
        await redis_client.aclose()


@asynccontextmanager
async def api_dependencies(
    settings: Settings,
    *,
    readiness_service: ReadinessService | None,
    embedding_provider: EmbeddingProvider,
) -> AsyncIterator[ApiDependencies]:
    if readiness_service is not None:
        yield ApiDependencies(None, None, None, readiness_service, embedding_provider)
        return

    engine: AsyncEngine = create_database_engine(settings)
    redis_client: Redis | None = None
    try:
        redis_client = Redis.from_url(
            settings.redis_url.get_secret_value(),
            decode_responses=True,
        )
        yield ApiDependencies(
            create_session_factory(engine),
            redis_client,
            RedisEventPublisher(redis_client),
            build_readiness_service(engine, redis_client, settings.dependency_timeout_seconds),
            embedding_provider,
        )
    finally:
        if redis_client is not None:
            await redis_client.aclose()
        await engine.dispose()


async def invoke_with_runtime[ResultT](
    settings: Settings,
    operation: Callable[[async_sessionmaker[AsyncSession], EventPublisher], Awaitable[ResultT]],
) -> ResultT:
    async def use_database(factory: async_sessionmaker[AsyncSession]) -> ResultT:
        return await with_events(settings, lambda publisher: operation(factory, publisher))

    return await with_database(settings, use_database)
