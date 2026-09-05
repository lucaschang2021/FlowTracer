from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence
from typing import cast
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.domains.acquisition_ports import AcquisitionBackend, ContentFetcher, EventPublisher
from app.models.entities import AcquisitionMode, DiscoveryMode, SourceFamily, SourceType
from app.providers.analysis import (
    AnalysisProvider,
    AnalysisRequest,
    FakeAnalysisProvider,
    OpenAICompatibleProvider,
    ProviderError,
    build_provider,
)
from app.providers.embedding import (
    EmbeddingError,
    EmbeddingProvider,
    FakeEmbeddingProvider,
    OpenAICompatibleEmbeddingProvider,
    build_embedding_provider,
)
from app.schemas.events import EventEnvelope
from app.schemas.resources import AcquisitionProfileV1
from app.services.acquisition_types import (
    AcquisitionRequest,
    AcquisitionResult,
    FetchResponse,
)
from app.services.events import build_event


class StubFetcher:
    async def fetch(self, url: str, source_type: SourceType) -> FetchResponse:
        return FetchResponse(url, "text/html", b"fixture")


class StubBackend:
    async def acquire(self, request: AcquisitionRequest) -> AcquisitionResult:
        response = FetchResponse(request.target_url, "text/html", b"fixture")
        return AcquisitionResult(response, retry_count=0, budget_used={})


class StubPublisher:
    def __init__(self) -> None:
        self.events: list[EventEnvelope] = []

    async def publish(self, user_id: object, event: EventEnvelope) -> None:
        del user_id
        self.events.append(event)


class OneChunkStream(httpx.AsyncByteStream):
    def __init__(self, content: bytes) -> None:
        self.content = content

    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield self.content

    async def aclose(self) -> None:
        return None


async def _fetch(port: ContentFetcher[SourceType, FetchResponse]) -> FetchResponse:
    return await port.fetch("https://example.test/", SourceType.URL)


async def _acquire(
    port: AcquisitionBackend[AcquisitionRequest, AcquisitionResult],
    request: AcquisitionRequest,
) -> AcquisitionResult:
    return await port.acquire(request)


async def _publish(port: EventPublisher[EventEnvelope], event: EventEnvelope) -> None:
    await port.publish(uuid4(), event)


def _provider_names(providers: Sequence[AnalysisProvider | EmbeddingProvider]) -> list[str]:
    return [provider.name for provider in providers]


def test_provider_factories_swap_fake_and_production_without_external_calls() -> None:
    settings = Settings()
    assert isinstance(build_provider(settings), FakeAnalysisProvider)
    assert isinstance(build_embedding_provider(settings), FakeEmbeddingProvider)

    with pytest.raises(ValueError, match="configuration is incomplete"):
        OpenAICompatibleProvider(settings)
    with pytest.raises(ValueError, match="configuration is incomplete"):
        OpenAICompatibleEmbeddingProvider(settings)

    configured = settings.model_copy(
        update={
            "ai_provider": "openai_compatible",
            "ai_base_url": "https://analysis.example.test/v1",
            "ai_api_key": SecretStr("test-only"),
            "embedding_provider": "openai_compatible",
            "embedding_base_url": "https://embedding.example.test/v1",
            "embedding_api_key": SecretStr("test-only"),
        }
    )
    assert isinstance(build_provider(configured), OpenAICompatibleProvider)
    assert isinstance(build_embedding_provider(configured), OpenAICompatibleEmbeddingProvider)


@pytest.mark.asyncio
async def test_production_provider_validation_remains_substitutable_offline() -> None:
    settings = Settings().model_copy(
        update={
            "ai_base_url": "https://analysis.example.test/v1",
            "ai_api_key": SecretStr("test-only"),
            "embedding_base_url": "https://embedding.example.test/v1",
            "embedding_api_key": SecretStr("test-only"),
        }
    )

    def invalid_usage(_request: httpx.Request) -> httpx.Response:
        content = json.dumps(
            {
                "choices": [{"message": {"content": "{}"}}],
                "usage": {"prompt_tokens": -1},
            }
        ).encode()
        return httpx.Response(
            200,
            stream=OneChunkStream(content),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(invalid_usage)) as client:
        provider = OpenAICompatibleProvider(settings, client)
        request = AnalysisRequest("Title", "Content", "Radar", "Goal", (), ())
        with pytest.raises(ProviderError, match="invalid output"):
            await provider.analyze(request, repair_error="schema mismatch")

    embedding = OpenAICompatibleEmbeddingProvider(settings)
    with pytest.raises(EmbeddingError, match="input batch is invalid"):
        await embedding.embed([])


@pytest.mark.asyncio
async def test_analysis_and_embedding_fakes_are_deterministic_substitutes() -> None:
    analysis = cast(AnalysisProvider, FakeAnalysisProvider())
    request = AnalysisRequest("Title", "Content", "Radar", "Goal", (), ())
    assert await analysis.analyze(request) == await analysis.analyze(request)

    embedding = cast(EmbeddingProvider, FakeEmbeddingProvider())
    assert await embedding.embed(["Content"]) == await embedding.embed(["Content"])
    assert _provider_names([analysis, embedding]) == ["fake", "fake"]


@pytest.mark.asyncio
async def test_acquisition_fetcher_backend_and_event_publisher_are_structural_ports() -> None:
    request = AcquisitionRequest(
        source_id=uuid4(),
        run_id=uuid4(),
        target_url="https://example.test/",
        source_type=SourceType.URL,
        source_family=SourceFamily.GENERIC_WEB,
        mode=AcquisitionMode.NATIVE,
        discovery_mode=DiscoveryMode.SINGLE_PAGE,
        profile=AcquisitionProfileV1(),
        correlation_id=None,
    )
    response = await _fetch(StubFetcher())
    result = await _acquire(StubBackend(), request)
    publisher = StubPublisher()
    collection_run_id = uuid4()
    event = build_event(
        "collection.updated",
        collection_run_id,
        "1",
        {
            "collection_run_id": collection_run_id,
            "source_id": request.source_id,
            "status": "succeeded",
            "fetched_count": 1,
            "created_count": 1,
            "duplicate_count": 0,
            "failed_count": 0,
        },
    )
    await _publish(publisher, event)

    assert response.body == b"fixture"
    assert result.response.final_url == request.target_url
    assert publisher.events == [event]
