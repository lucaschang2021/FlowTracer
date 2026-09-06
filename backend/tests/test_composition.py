from __future__ import annotations

from typing import Any

import pytest

from app.core import composition
from app.core.config import Settings
from app.domains.provider_ports import EmbeddingProvider
from app.main import create_app
from app.providers.embedding import FakeEmbeddingProvider
from app.services.events import RedisEventPublisher
from app.services.readiness import ReadinessService


async def healthy_probe() -> None:
    return None


class Engine:
    def __init__(self) -> None:
        self.disposed = False

    async def dispose(self) -> None:
        self.disposed = True


class RedisClient:
    def __init__(self) -> None:
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_shared_worker_composition_closes_database_and_redis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings()
    engine = Engine()
    redis_client = RedisClient()
    factory = object()
    monkeypatch.setattr(composition, "create_database_engine", lambda _settings: engine)
    monkeypatch.setattr(composition, "create_session_factory", lambda _engine: factory)
    monkeypatch.setattr(
        composition.Redis,
        "from_url",
        lambda *_args, **_kwargs: redis_client,
    )

    assert await composition.with_database(settings, lambda value: _return(value)) is factory
    assert engine.disposed
    publisher = await composition.with_events(settings, lambda value: _return(value))
    assert isinstance(publisher, RedisEventPublisher)
    assert redis_client.closed


async def _return(value: Any) -> Any:
    return value


@pytest.mark.asyncio
async def test_injected_readiness_mode_constructs_no_external_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def blocked(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("external runtime was constructed")

    monkeypatch.setattr(composition, "create_database_engine", blocked)
    monkeypatch.setattr(composition.Redis, "from_url", blocked)
    settings = Settings()
    readiness = ReadinessService(healthy_probe, healthy_probe)
    embedding: EmbeddingProvider = FakeEmbeddingProvider(settings.embedding_model)

    async with composition.api_dependencies(
        settings,
        readiness_service=readiness,
        embedding_provider=embedding,
    ) as dependencies:
        assert dependencies.session_factory is None
        assert dependencies.redis_client is None
        assert dependencies.event_publisher is None
        assert dependencies.readiness_service is readiness
        assert dependencies.embedding_provider is embedding


@pytest.mark.asyncio
async def test_api_composition_wires_and_closes_runtime_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings()
    engine = Engine()
    redis_client = RedisClient()
    factory = object()
    readiness = ReadinessService(healthy_probe, healthy_probe)
    embedding: EmbeddingProvider = FakeEmbeddingProvider(settings.embedding_model)
    monkeypatch.setattr(composition, "create_database_engine", lambda _settings: engine)
    monkeypatch.setattr(composition, "create_session_factory", lambda _engine: factory)
    monkeypatch.setattr(
        composition.Redis,
        "from_url",
        lambda *_args, **_kwargs: redis_client,
    )
    monkeypatch.setattr(
        composition,
        "build_readiness_service",
        lambda *_args, **_kwargs: readiness,
    )

    async with composition.api_dependencies(
        settings,
        readiness_service=None,
        embedding_provider=embedding,
    ) as dependencies:
        assert dependencies.session_factory is factory
        assert dependencies.redis_client is redis_client
        assert isinstance(dependencies.event_publisher, RedisEventPublisher)
        assert dependencies.readiness_service is readiness
        assert dependencies.embedding_provider is embedding
        assert not engine.disposed
        assert not redis_client.closed

    assert engine.disposed
    assert redis_client.closed


@pytest.mark.asyncio
async def test_api_composition_disposes_engine_when_redis_construction_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings()
    engine = Engine()
    embedding: EmbeddingProvider = FakeEmbeddingProvider(settings.embedding_model)

    def fail_redis(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("redis construction failed")

    monkeypatch.setattr(composition, "create_database_engine", lambda _settings: engine)
    monkeypatch.setattr(composition.Redis, "from_url", fail_redis)

    with pytest.raises(RuntimeError, match="redis construction failed"):
        async with composition.api_dependencies(
            settings,
            readiness_service=None,
            embedding_provider=embedding,
        ):
            pytest.fail("composition unexpectedly started")

    assert engine.disposed


def test_create_app_preserves_state_and_composes_embedding_provider() -> None:
    settings = Settings()
    readiness = ReadinessService(healthy_probe, healthy_probe)
    application = create_app(settings, readiness_service=readiness)

    assert application.state.settings is settings
    assert application.state.readiness_service is readiness
    assert application.state.redis_client is None
    assert application.state.event_publisher is None
    assert isinstance(application.state.embedding_provider, FakeEmbeddingProvider)
