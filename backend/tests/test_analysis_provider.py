from __future__ import annotations

import json

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
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"summary":"ok"}'}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 99},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleProvider(remote_settings(monkeypatch), client)
    response = await provider.analyze(request())
    await client.aclose()
    incoming = seen["request"]
    assert isinstance(incoming, httpx.Request)
    assert incoming.url.path == "/v1/chat/completions"
    assert incoming.headers["authorization"] == "Bearer super-secret-provider-key"
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
        httpx.Response(200, content=b"x" * (MAX_AI_RESPONSE_BYTES + 1)),
        httpx.Response(200, json={"choices": []}),
        httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "{}"}}],
                "usage": {"prompt_tokens": True},
            },
        ),
        httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "{}"}}],
                "usage": {"prompt_tokens": 2_147_483_648},
            },
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
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "{}"}}],
                "usage": {"prompt_tokens": 2, "completion_tokens": 3},
            },
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
