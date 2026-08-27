from __future__ import annotations

import gzip
import json
import tracemalloc
from collections.abc import AsyncIterator

import httpx
import pytest

from app.core.config import Settings
from app.providers.analysis import (
    MAX_AI_RESPONSE_BYTES,
    AnalysisRequest,
    FakeAnalysisProvider,
    OpenAICompatibleProvider,
    ProviderError,
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


def padded_success_envelope(size: int) -> bytes:
    base = json.dumps(
        {
            "choices": [{"message": {"content": "{}"}}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        },
        separators=(",", ":"),
    ).encode()
    assert len(base) <= size
    return base + b" " * (size - len(base))


def raw_response(payload: object) -> httpx.Response:
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    return httpx.Response(200, stream=TrackingStream([body]))


def request() -> AnalysisRequest:
    return AnalysisRequest(
        title="A title",
        content="Useful content",
        radar_name="Radar",
        radar_goal="Track useful things",
        categories=("technology",),
        keywords=("python",),
    )


@pytest.mark.asyncio
async def test_fake_provider_is_deterministic_and_offline() -> None:
    provider = FakeAnalysisProvider()
    first = await provider.analyze(request())
    second = await provider.analyze(request(), repair_error="safe summary")
    assert first == second
    payload = json.loads(first.content)
    assert payload["category"] == "technology"
    assert all(0 <= payload[key] <= 100 for key in ("relevance", "importance", "novelty", "impact"))
    assert first.usage.total_tokens == first.usage.input_tokens + first.usage.output_tokens


def remote_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("AI_PROVIDER", "openai_compatible")
    monkeypatch.setenv("AI_MODEL", "test-model")
    monkeypatch.setenv("AI_BASE_URL", "http://127.0.0.1:8765/v1")
    monkeypatch.setenv("AI_API_KEY", "super-secret-provider-key")
    monkeypatch.setenv("AI_INPUT_COST_PER_MILLION", "1.5")
    monkeypatch.setenv("AI_OUTPUT_COST_PER_MILLION", "2.5")
    return Settings()


@pytest.mark.asyncio
async def test_openai_compatible_wire_contract_and_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    async def handler(incoming: httpx.Request) -> httpx.Response:
        seen["request"] = incoming
        body = json.loads(incoming.content)
        seen["body"] = body
        return raw_response(
            {
                "choices": [{"message": {"content": '{"summary":"ok"}'}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 99},
            }
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleProvider(remote_settings(monkeypatch), client)
    response = await provider.analyze(request())
    await client.aclose()
    incoming = seen["request"]
    assert isinstance(incoming, httpx.Request)
    assert incoming.url.path == "/v1/chat/completions"
    assert incoming.headers["authorization"] == "Bearer super-secret-provider-key"
    assert incoming.headers["accept-encoding"] == "identity"
    assert incoming.headers["user-agent"] == "FlowTracer/0.1"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["temperature"] == 0
    assert body["response_format"]["json_schema"]["strict"] is True
    assert response.usage.total_tokens == 99


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "code", "retryable"),
    [
        (401, "ai_auth_failed", False),
        (403, "ai_auth_failed", False),
        (429, "ai_rate_limited", True),
        (500, "ai_provider_unavailable", True),
        (400, "ai_provider_unavailable", False),
        (302, "ai_provider_unavailable", False),
    ],
)
async def test_openai_status_mapping(
    monkeypatch: pytest.MonkeyPatch, status: int, code: str, retryable: bool
) -> None:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _request: httpx.Response(status))
    )
    provider = OpenAICompatibleProvider(remote_settings(monkeypatch), client)
    with pytest.raises(ProviderError) as raised:
        await provider.analyze(request())
    await client.aclose()
    assert raised.value.code == code
    assert raised.value.retryable is retryable
    assert "secret" not in raised.value.safe_message


@pytest.mark.asyncio
async def test_openai_rejects_oversized_and_invalid_envelopes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = [
        raw_response(b"x" * (MAX_AI_RESPONSE_BYTES + 1)),
        raw_response({"choices": []}),
        raw_response(
            {
                "choices": [{"message": {"content": "{}"}}],
                "usage": {"prompt_tokens": True},
            }
        ),
        raw_response(
            {
                "choices": [{"message": {"content": "{}"}}],
                "usage": {"prompt_tokens": 2_147_483_648},
            }
        ),
    ]

    async def handler(_request: httpx.Request) -> httpx.Response:
        return responses.pop(0)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleProvider(remote_settings(monkeypatch), client)
    expected = [
        "ai_response_too_large",
        "ai_invalid_output",
        "ai_invalid_output",
        "ai_invalid_output",
    ]
    for code in expected:
        with pytest.raises(ProviderError) as raised:
            await provider.analyze(request())
        assert raised.value.code == code
    await client.aclose()


@pytest.mark.asyncio
async def test_openai_raw_stream_exact_limit_and_stops_at_limit_plus_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exact_stream = TrackingStream([padded_success_envelope(MAX_AI_RESPONSE_BYTES)])
    oversized_chunks = [
        b"x" * MAX_AI_RESPONSE_BYTES,
        b"x",
        b"must-not-be-read",
    ]
    oversized_stream = TrackingStream(oversized_chunks)
    streams = [exact_stream, oversized_stream]

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=streams.pop(0))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleProvider(remote_settings(monkeypatch), client)
    assert (await provider.analyze(request())).usage.total_tokens == 0
    assert exact_stream.bytes_read == MAX_AI_RESPONSE_BYTES
    with pytest.raises(ProviderError) as raised:
        await provider.analyze(request())
    assert raised.value.code == "ai_response_too_large"
    assert oversized_stream.bytes_read == MAX_AI_RESPONSE_BYTES + 1
    assert oversized_stream.read_count == 2
    assert oversized_stream.read_count < len(oversized_chunks)
    await client.aclose()


@pytest.mark.asyncio
async def test_openai_content_length_rejects_before_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    too_large = TrackingStream([b"must-not-be-read"])
    invalid = TrackingStream([b"must-not-be-read"])
    responses = [
        httpx.Response(
            200,
            headers={"Content-Length": str(MAX_AI_RESPONSE_BYTES + 1)},
            stream=too_large,
        ),
        httpx.Response(200, headers={"Content-Length": "invalid"}, stream=invalid),
    ]

    async def handler(_request: httpx.Request) -> httpx.Response:
        return responses.pop(0)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleProvider(remote_settings(monkeypatch), client)
    for code in ("ai_response_too_large", "ai_invalid_output"):
        with pytest.raises(ProviderError) as raised:
            await provider.analyze(request())
        assert raised.value.code == code
    assert too_large.read_count == invalid.read_count == 0
    await client.aclose()


@pytest.mark.asyncio
async def test_openai_rejects_gzip_bomb_before_read_without_large_allocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    compressed = gzip.compress(b"x" * (32 * 1024 * 1024), compresslevel=9)
    assert len(compressed) < 64 * 1024
    stream = TrackingStream([compressed])

    async def handler(incoming: httpx.Request) -> httpx.Response:
        assert incoming.headers["accept-encoding"] == "identity"
        return httpx.Response(200, headers={"Content-Encoding": "gzip"}, stream=stream)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleProvider(remote_settings(monkeypatch), client)
    tracemalloc.start()
    with pytest.raises(ProviderError) as raised:
        await provider.analyze(request())
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert raised.value.code == "ai_invalid_output"
    assert stream.read_count == stream.bytes_read == 0
    assert peak < 2 * 1024 * 1024
    await client.aclose()


@pytest.mark.asyncio
async def test_openai_transport_failures_and_derived_total(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    async def handler(incoming: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ReadTimeout("private timeout detail", request=incoming)
        if calls == 2:
            raise httpx.ConnectError("private network detail", request=incoming)
        return raw_response(
            {
                "choices": [{"message": {"content": "{}"}}],
                "usage": {"prompt_tokens": 2, "completion_tokens": 3},
            }
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleProvider(remote_settings(monkeypatch), client)
    for code in ("ai_timeout", "ai_provider_unavailable"):
        with pytest.raises(ProviderError) as raised:
            await provider.analyze(request())
        assert raised.value.code == code and raised.value.retryable
        assert "private" not in raised.value.safe_message
    result = await provider.analyze(request())
    assert result.usage.total_tokens == 5
    await client.aclose()


def test_openai_configuration_is_fail_fast_and_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_PROVIDER", "openai_compatible")
    monkeypatch.setenv("AI_MODEL", "model")
    monkeypatch.setenv("AI_INPUT_COST_PER_MILLION", "0")
    monkeypatch.setenv("AI_OUTPUT_COST_PER_MILLION", "0")
    monkeypatch.delenv("AI_BASE_URL", raising=False)
    monkeypatch.delenv("AI_API_KEY", raising=False)
    with pytest.raises(ValueError) as raised:
        Settings()
    message = str(raised.value)
    assert "AI_BASE_URL" in message and "AI_API_KEY" in message
    assert "secret" not in message

    monkeypatch.setenv("AI_BASE_URL", "http://example.com/v1")
    monkeypatch.setenv("AI_API_KEY", "not-printed")
    with pytest.raises(ValueError):
        Settings()
