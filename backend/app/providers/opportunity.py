"""Opportunity evaluation providers: deterministic fake and OpenAI-compatible HTTP.

Prompt/schema version ``opportunity-eval-v1`` (docs/24 §5). Requests carry only
bounded opportunity facts plus radar goal/skills; source configs, user profiles,
cookies, tokens and browser traces never leave the application. Outputs must be one
strict JSON object with the eight integer dimensions and a bounded reason.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import httpx

from app.core.config import Settings
from app.domains.opportunity_policy import ALL_DIMENSIONS
from app.domains.provider_ports import (
    OpportunityEvaluationProvider,
    OpportunityEvaluationRequest,
    ProviderError,
    ProviderResponse,
    ProviderUsage,
)
from app.providers.analysis import _non_negative_int, _reject_constant

MAX_AI_RESPONSE_BYTES = 256 * 1024
MAX_AI_RAW_READ_BYTES = MAX_AI_RESPONSE_BYTES + 1
MAX_PROMPT_DESCRIPTION_CHARS = 8_000
MAX_PROMPT_SKILLS = 50


def _strict_output_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [*ALL_DIMENSIONS, "reason"],
        "properties": {
            **{name: {"type": "integer", "minimum": 0, "maximum": 100} for name in ALL_DIMENSIONS},
            "reason": {"type": "string", "minLength": 1, "maxLength": 1000},
        },
    }


class FakeOpportunityEvaluationProvider:
    name = "fake"

    def __init__(self, model: str = "flowtracer-fake-v1") -> None:
        self.model = model

    async def evaluate(
        self,
        request: OpportunityEvaluationRequest,
        *,
        repair_error: str | None = None,
    ) -> ProviderResponse:
        identity = "\n".join(
            (
                request.title,
                request.description[:400],
                request.radar_name,
                request.radar_goal,
                repair_error or "",
            )
        ).encode("utf-8")
        digest = hashlib.sha256(identity).digest()
        payload: dict[str, Any] = {
            name: 40 + digest[index] % 61 for index, name in enumerate(ALL_DIMENSIONS)
        }
        payload["reason"] = "Deterministic local opportunity evaluation."
        content = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        input_tokens = max(1, len(request.description) // 4)
        output_tokens = max(1, len(content) // 4)
        return ProviderResponse(
            content=content,
            usage=ProviderUsage(input_tokens, output_tokens, input_tokens + output_tokens),
        )


class OpenAICompatibleOpportunityProvider:
    name = "openai_compatible"

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        if settings.ai_base_url is None or settings.ai_api_key is None:
            raise ValueError("OpenAI-compatible provider configuration is incomplete")
        self.model = settings.ai_model
        self._url = f"{settings.ai_base_url.rstrip('/')}/chat/completions"
        self._api_key = settings.ai_api_key.get_secret_value()
        self._client = client

    async def evaluate(
        self,
        request: OpportunityEvaluationRequest,
        *,
        repair_error: str | None = None,
    ) -> ProviderResponse:
        body = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": _system_message(repair_error)},
                {
                    "role": "user",
                    "content": json.dumps(
                        _user_payload(request), ensure_ascii=False, separators=(",", ":")
                    ),
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "flowtracer_opportunity",
                    "strict": True,
                    "schema": _strict_output_schema(),
                },
            },
        }
        chunks = await self._post(body)
        return _parse_response(chunks)

    async def _post(self, body: dict[str, Any]) -> list[bytes]:
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
                _raise_for_status(response)
                _check_headers(response)
                chunks: list[bytes] = []
                size = 0
                async for chunk in response.aiter_raw(chunk_size=MAX_AI_RAW_READ_BYTES):
                    size += len(chunk)
                    if size > MAX_AI_RESPONSE_BYTES:
                        raise ProviderError(
                            "ai_response_too_large", "AI response is too large", retryable=False
                        )
                    chunks.append(chunk)
                return chunks
        except httpx.TimeoutException:
            raise ProviderError("ai_timeout", "AI request timed out", retryable=True) from None
        except httpx.TransportError:
            raise ProviderError(
                "ai_provider_unavailable", "AI provider is unavailable", retryable=True
            ) from None
        finally:
            if owns_client:
                await client.aclose()


def _system_message(repair_error: str | None) -> str:
    system = (
        "Return only one JSON object matching the supplied strict schema. "
        "Do not include markdown or additional fields."
    )
    if repair_error:
        system += f" Repair the prior response using this validation summary: {repair_error[:300]}"
    return system


def _user_payload(request: OpportunityEvaluationRequest) -> dict[str, Any]:
    return {
        "opportunity": {
            "title": request.title,
            "description": request.description[:MAX_PROMPT_DESCRIPTION_CHARS],
            "platform": request.platform,
            "budget_min": None if request.budget_min is None else str(request.budget_min),
            "budget_max": None if request.budget_max is None else str(request.budget_max),
            "currency": request.currency,
            "skills": list(request.skills[:MAX_PROMPT_SKILLS]),
            "deadline": None if request.deadline is None else request.deadline.isoformat(),
            "published_at": (
                None if request.published_at is None else request.published_at.isoformat()
            ),
            "estimated_effort_hours": (
                None
                if request.estimated_effort_hours is None
                else str(request.estimated_effort_hours)
            ),
            "delivery_type": request.delivery_type,
        },
        "radar": {
            "name": request.radar_name,
            "goal": request.radar_goal,
            "keywords": list(request.radar_keywords),
        },
    }


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code in {401, 403}:
        raise ProviderError("ai_auth_failed", "AI authentication failed", retryable=False)
    if response.status_code == 429:
        raise ProviderError("ai_rate_limited", "AI provider rate limited", retryable=True)
    if response.status_code >= 500:
        raise ProviderError("ai_provider_unavailable", "AI provider is unavailable", retryable=True)
    if response.status_code >= 400 or 300 <= response.status_code < 400:
        raise ProviderError(
            "ai_provider_unavailable", "AI provider rejected the request", retryable=False
        )


def _check_headers(response: httpx.Response) -> None:
    content_encoding = response.headers.get("content-encoding")
    if content_encoding and content_encoding.strip().lower() != "identity":
        raise ProviderError(
            "ai_invalid_output", "AI response uses unsupported content encoding", retryable=False
        )
    content_length = response.headers.get("content-length")
    if content_length is None:
        return
    normalized = content_length.strip()
    if not normalized.isascii() or not normalized.isdecimal():
        raise ProviderError(
            "ai_invalid_output", "AI response has an invalid content length", retryable=False
        )
    if int(normalized) > MAX_AI_RESPONSE_BYTES:
        raise ProviderError("ai_response_too_large", "AI response is too large", retryable=False)


def _parse_response(chunks: list[bytes]) -> ProviderResponse:
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


def build_opportunity_provider(settings: Settings) -> OpportunityEvaluationProvider:
    if settings.ai_provider == "fake":
        return FakeOpportunityEvaluationProvider(settings.ai_model)
    return OpenAICompatibleOpportunityProvider(settings)
