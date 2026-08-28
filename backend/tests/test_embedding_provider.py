from __future__ import annotations

import gzip
import json
import math
import tracemalloc
from collections.abc import AsyncIterator

import httpx
import pytest

from app.core.config import Settings
from app.providers.embedding import (
    EMBEDDING_DIMENSIONS,
    MAX_EMBEDDING_RESPONSE_BYTES,
    EmbeddingError,
    FakeEmbeddingProvider,
    OpenAICompatibleEmbeddingProvider,
)


class TrackingStream(httpx.AsyncByteStream):
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks
        self.read_count = 0
        self.bytes_read = 0

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for chunk in self.chunks:
            self.read_count += 1
            self.bytes_read += len(chunk)
            yield chunk

    async def aclose(self) -> None:
        return None


def vector(value: float = 1.0) -> list[float]:
    return [value] + [0.0] * (EMBEDDING_DIMENSIONS - 1)


def envelope(vectors: list[list[float]] | None = None) -> dict[str, object]:
    resolved = vectors or [vector()]
    return {
        "data": [
            {"index": index, "embedding": embedding} for index, embedding in enumerate(resolved)
        ],
        "usage": {"prompt_tokens": 7, "total_tokens": 7},
    }


def remote_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai_compatible")
    monkeypatch.setenv("EMBEDDING_MODEL", "embedding-test-model")
    monkeypatch.setenv("EMBEDDING_BASE_URL", "http://127.0.0.1:8765/v1")
    monkeypatch.setenv("EMBEDDING_API_KEY", "synthetic-secret-key")
    return Settings()


@pytest.mark.asyncio
async def test_fake_embedding_is_deterministic_ordered_normalized_and_offline() -> None:
    provider = FakeEmbeddingProvider()
    first = await provider.embed(["alpha", "beta"])
    second = await provider.embed(["alpha", "beta"])
    assert first == second
    assert first.vectors[0] != first.vectors[1]
    assert all(len(item) == EMBEDDING_DIMENSIONS for item in first.vectors)
    assert all(
        math.isclose(math.sqrt(math.fsum(v * v for v in item)), 1, rel_tol=1e-6)
        for item in first.vectors
    )


@pytest.mark.asyncio
async def test_openai_embedding_wire_contract_and_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["request"] = request
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, stream=TrackingStream([json.dumps(envelope()).encode()]))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleEmbeddingProvider(remote_settings(monkeypatch), client)
    result = await provider.embed(["private query"])
    await client.aclose()
    request = seen["request"]
    assert isinstance(request, httpx.Request)
    assert request.url.path == "/v1/embeddings"
    assert request.headers["accept-encoding"] == "identity"
    assert request.headers["authorization"] == "Bearer synthetic-secret-key"
    assert seen["body"] == {
        "model": "embedding-test-model",
        "input": ["private query"],
        "dimensions": EMBEDDING_DIMENSIONS,
    }
    assert result.usage.input_tokens == result.usage.total_tokens == 7
    assert result.vectors[0][0] == 1.0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "code", "retryable"),
    [
        (401, "embedding_auth_failed", False),
        (403, "embedding_auth_failed", False),
        (429, "embedding_rate_limited", True),
        (500, "embedding_provider_unavailable", True),
        (400, "embedding_provider_unavailable", False),
        (302, "embedding_provider_unavailable", False),
    ],
)
async def test_openai_embedding_status_mapping(
    monkeypatch: pytest.MonkeyPatch, status_code: int, code: str, retryable: bool
) -> None:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _request: httpx.Response(status_code))
    )
    provider = OpenAICompatibleEmbeddingProvider(remote_settings(monkeypatch), client)
    with pytest.raises(EmbeddingError) as raised:
        await provider.embed(["content"])
    await client.aclose()
    assert raised.value.code == code and raised.value.retryable is retryable
    assert "secret" not in raised.value.safe_message


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid",
    [
        [],
        [0.0] * EMBEDDING_DIMENSIONS,
        [True] + [0.0] * (EMBEDDING_DIMENSIONS - 1),
        [float("nan")] + [0.0] * (EMBEDDING_DIMENSIONS - 1),
        [float("inf")] + [0.0] * (EMBEDDING_DIMENSIONS - 1),
        [1_000_001.0] + [0.0] * (EMBEDDING_DIMENSIONS - 1),
        [1.0],
    ],
)
async def test_openai_embedding_rejects_invalid_vectors(
    monkeypatch: pytest.MonkeyPatch, invalid: list[float]
) -> None:
    payload = envelope([invalid])
    body = json.dumps(payload, allow_nan=True).encode()
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, stream=TrackingStream([body]))
        )
    )
    provider = OpenAICompatibleEmbeddingProvider(remote_settings(monkeypatch), client)
    with pytest.raises(EmbeddingError) as raised:
        await provider.embed(["content"])
    await client.aclose()
    assert raised.value.code == "embedding_invalid_output"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {"data": []},
        {"data": [None]},
        {"data": [[]]},
        {"data": [{"index": 1, "embedding": vector()}]},
        {"data": [{"index": True, "embedding": vector()}]},
        {
            "data": [
                {"index": 0, "embedding": vector()},
                {"index": 0, "embedding": vector()},
            ]
        },
        {"data": [{"index": 0, "embedding": vector()}], "usage": {"prompt_tokens": True}},
        {
            "data": [{"index": 0, "embedding": vector()}],
            "usage": {"prompt_tokens": 2, "total_tokens": 1},
        },
        {"data": [{"index": 0, "embedding": vector()}], "usage": None},
        {"data": [{"index": 0, "embedding": vector()}], "usage": []},
        {"data": [{"index": 0, "embedding": vector()}], "usage": "invalid"},
    ],
)
async def test_openai_embedding_rejects_count_index_and_usage_contract(
    monkeypatch: pytest.MonkeyPatch, payload: object
) -> None:
    body = json.dumps(payload).encode()
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, stream=TrackingStream([body]))
        )
    )
    provider = OpenAICompatibleEmbeddingProvider(remote_settings(monkeypatch), client)
    with pytest.raises(EmbeddingError) as raised:
        await provider.embed(["content"])
    await client.aclose()
    assert raised.value.code == "embedding_invalid_output"
    assert raised.value.retryable is False
    assert raised.value.safe_message == "Embedding returned invalid output"


@pytest.mark.asyncio
async def test_embedding_transport_failures_and_batch_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ReadTimeout("private timeout", request=request)
        raise httpx.ConnectError("private connection", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleEmbeddingProvider(remote_settings(monkeypatch), client)
    for code in ("embedding_timeout", "embedding_provider_unavailable"):
        with pytest.raises(EmbeddingError) as raised:
            await provider.embed(["content"])
        assert raised.value.code == code and raised.value.retryable
        assert "private" not in raised.value.safe_message
    await client.aclose()
    with pytest.raises(EmbeddingError):
        await FakeEmbeddingProvider().embed(["x"] * 17)


@pytest.mark.asyncio
async def test_embedding_raw_limit_exact_plus_one_and_content_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = json.dumps(envelope(), separators=(",", ":")).encode()
    exact = TrackingStream([base + b" " * (MAX_EMBEDDING_RESPONSE_BYTES - len(base))])
    oversized_parts = [
        b"x" * MAX_EMBEDDING_RESPONSE_BYTES,
        b"x",
        b"must-not-be-read",
    ]
    oversized = TrackingStream(oversized_parts)
    declared = TrackingStream([b"must-not-be-read"])
    invalid_length = TrackingStream([b"must-not-be-read"])
    responses = [
        httpx.Response(200, stream=exact),
        httpx.Response(200, stream=oversized),
        httpx.Response(
            200,
            headers={"Content-Length": str(MAX_EMBEDDING_RESPONSE_BYTES + 1)},
            stream=declared,
        ),
        httpx.Response(
            200,
            headers={"Content-Length": "invalid"},
            stream=invalid_length,
        ),
    ]

    async def handler(_request: httpx.Request) -> httpx.Response:
        return responses.pop(0)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleEmbeddingProvider(remote_settings(monkeypatch), client)
    assert (await provider.embed(["content"])).usage.total_tokens == 7
    expected_codes = (
        "embedding_response_too_large",
        "embedding_response_too_large",
        "embedding_invalid_output",
    )
    for code in expected_codes:
        with pytest.raises(EmbeddingError) as raised:
            await provider.embed(["content"])
        assert raised.value.code == code
    assert exact.bytes_read == MAX_EMBEDDING_RESPONSE_BYTES
    assert oversized.bytes_read == MAX_EMBEDDING_RESPONSE_BYTES + 1
    assert oversized.read_count == 2 < len(oversized_parts)
    assert declared.read_count == 0
    assert invalid_length.read_count == 0
    await client.aclose()


@pytest.mark.asyncio
async def test_embedding_rejects_gzip_bomb_before_read_without_large_allocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    compressed = gzip.compress(b"x" * (32 * 1024 * 1024), compresslevel=9)
    assert len(compressed) < 64 * 1024
    stream = TrackingStream([compressed])

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["accept-encoding"] == "identity"
        return httpx.Response(200, headers={"Content-Encoding": "gzip"}, stream=stream)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleEmbeddingProvider(remote_settings(monkeypatch), client)
    tracemalloc.start()
    with pytest.raises(EmbeddingError) as raised:
        await provider.embed(["content"])
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    await client.aclose()
    assert raised.value.code == "embedding_invalid_output"
    assert stream.read_count == stream.bytes_read == 0
    assert peak < 2 * 1024 * 1024
