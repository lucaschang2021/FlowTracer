from __future__ import annotations

import hashlib
import json
from typing import Any

import httpx

from app.core.config import Settings
from app.domains.provider_ports import (
    AnalysisProvider,
    AnalysisRequest,
    ProviderError,
    ProviderResponse,
    ProviderUsage,
)

MAX_AI_RESPONSE_BYTES = 256 * 1024
MAX_AI_RAW_READ_BYTES = MAX_AI_RESPONSE_BYTES + 1
MAX_PROMPT_CONTENT_CHARS = 24_000

STRICT_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "summary",
        "category",
        "relevance",
        "importance",
        "novelty",
        "impact",
        "reason",
    ],
    "properties": {
        "summary": {"type": "string", "minLength": 1, "maxLength": 2000},
        "category": {"type": "string", "minLength": 1, "maxLength": 120},
        "relevance": {"type": "integer", "minimum": 0, "maximum": 100},
        "importance": {"type": "integer", "minimum": 0, "maximum": 100},
        "novelty": {"type": "integer", "minimum": 0, "maximum": 100},
        "impact": {"type": "integer", "minimum": 0, "maximum": 100},
        "reason": {"type": "string", "minLength": 1, "maxLength": 1000},
    },
}


class FakeAnalysisProvider:
    name = "fake"

    def __init__(self, model: str = "flowtracer-fake-v1") -> None:
        self.model = model

    async def analyze(
        self, request: AnalysisRequest, *, repair_error: str | None = None
    ) -> ProviderResponse:
        identity = "\n".join(
            (request.title, request.content, request.radar_name, request.radar_goal)
        ).encode("utf-8")
        digest = hashlib.sha256(identity).digest()
        scores = [40 + digest[index] % 61 for index in range(4)]
        category = request.categories[0] if request.categories else "general"
        summary = request.title.strip() or "Untitled intelligence item"
        payload = {
            "summary": summary[:2000],
            "category": category,
            "relevance": scores[0],
            "importance": scores[1],
            "novelty": scores[2],
            "impact": scores[3],
            "reason": "Deterministic local analysis for the configured radar.",
        }
        content = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        input_tokens = max(1, len(request.content) // 4)
        output_tokens = max(1, len(content) // 4)
        return ProviderResponse(
            content=content,
            usage=ProviderUsage(input_tokens, output_tokens, input_tokens + output_tokens),
        )


class OpenAICompatibleProvider:
    name = "openai_compatible"

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        if settings.ai_base_url is None or settings.ai_api_key is None:
            raise ValueError("OpenAI-compatible provider configuration is incomplete")
        self.model = settings.ai_model
        self._url = f"{settings.ai_base_url.rstrip('/')}/chat/completions"
        self._api_key = settings.ai_api_key.get_secret_value()
        self._client = client

    async def analyze(
        self, request: AnalysisRequest, *, repair_error: str | None = None
    ) -> ProviderResponse:
        system = (
            "Return only one JSON object matching the supplied strict schema. "
            "Do not include markdown or additional fields."
        )
        if repair_error:
            system += (
                f" Repair the prior response using this validation summary: {repair_error[:300]}"
            )
        user_payload = {
            "document": {
                "title": request.title,
                "content": request.content[:MAX_PROMPT_CONTENT_CHARS],
            },
            "radar": {
                "name": request.radar_name,
                "goal": request.radar_goal,
                "categories": list(request.categories),
                "keywords": list(request.keywords),
            },
        }
        body = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "flowtracer_intelligence",
                    "strict": True,
                    "schema": STRICT_OUTPUT_SCHEMA,
                },
            },
        }
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(
            follow_redirects=False,
            timeout=httpx.Timeout(60.0, connect=5.0, pool=5.0),
        )
        try:
            async with client.stream(
                "POST",
                self._url,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Accept-Encoding": "identity",
                    "Content-Type": "application/json",
                    "User-Agent": "FlowTracer/0.1",
                },
                json=body,
            ) as response:
                if response.status_code in {401, 403}:
                    raise ProviderError(
                        "ai_auth_failed", "AI authentication failed", retryable=False
                    )
                if response.status_code == 429:
                    raise ProviderError(
                        "ai_rate_limited", "AI provider rate limited", retryable=True
                    )
                if response.status_code >= 500:
                    raise ProviderError(
                        "ai_provider_unavailable", "AI provider is unavailable", retryable=True
                    )
                if response.status_code >= 400 or 300 <= response.status_code < 400:
                    raise ProviderError(
                        "ai_provider_unavailable",
                        "AI provider rejected the request",
                        retryable=False,
                    )
                content_encoding = response.headers.get("content-encoding")
                if content_encoding and content_encoding.strip().lower() != "identity":
                    raise ProviderError(
                        "ai_invalid_output",
                        "AI response uses unsupported content encoding",
                        retryable=False,
                    )
                content_length = response.headers.get("content-length")
                if content_length is not None:
                    normalized_length = content_length.strip()
                    if not normalized_length.isascii() or not normalized_length.isdecimal():
                        raise ProviderError(
                            "ai_invalid_output",
                            "AI response has an invalid content length",
                            retryable=False,
                        )
                    if int(normalized_length) > MAX_AI_RESPONSE_BYTES:
                        raise ProviderError(
                            "ai_response_too_large",
                            "AI response is too large",
                            retryable=False,
                        )
                chunks: list[bytes] = []
                size = 0
                async for chunk in response.aiter_raw(chunk_size=MAX_AI_RAW_READ_BYTES):
                    size += len(chunk)
                    if size > MAX_AI_RESPONSE_BYTES:
                        raise ProviderError(
                            "ai_response_too_large", "AI response is too large", retryable=False
                        )
                    chunks.append(chunk)
        except httpx.TimeoutException:
            raise ProviderError("ai_timeout", "AI request timed out", retryable=True) from None
        except httpx.TransportError:
            raise ProviderError(
                "ai_provider_unavailable", "AI provider is unavailable", retryable=True
            ) from None
        finally:
            if owns_client:
                await client.aclose()
        try:
            envelope = json.loads(b"".join(chunks).decode("utf-8"), parse_constant=_reject_constant)
            content = envelope["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise TypeError
            usage = envelope.get("usage", {})
            prompt = _non_negative_int(usage.get("prompt_tokens", 0))
            completion = _non_negative_int(usage.get("completion_tokens", 0))
            explicit_total = usage.get("total_tokens")
            total = (
                _non_negative_int(prompt + completion)
                if explicit_total is None
                else _non_negative_int(explicit_total)
            )
        except (
            AttributeError,
            KeyError,
            IndexError,
            TypeError,
            ValueError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ):
            raise ProviderError(
                "ai_invalid_output", "AI returned invalid output", retryable=False
            ) from None
        return ProviderResponse(content, ProviderUsage(prompt, completion, total))


def _reject_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def _non_negative_int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > 2_147_483_647:
        raise ValueError("usage must contain non-negative integers")
    return int(value)


def build_provider(settings: Settings) -> AnalysisProvider:
    if settings.ai_provider == "fake":
        return FakeAnalysisProvider(settings.ai_model)
    return OpenAICompatibleProvider(settings)
