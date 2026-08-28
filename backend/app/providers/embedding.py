from __future__ import annotations

import hashlib
import json
import math
import struct
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.core.config import Settings

EMBEDDING_DIMENSIONS = 1536
MAX_EMBEDDING_BATCH = 16
MAX_EMBEDDING_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_EMBEDDING_RAW_READ_BYTES = MAX_EMBEDDING_RESPONSE_BYTES + 1


@dataclass(frozen=True)
class EmbeddingUsage:
    input_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class EmbeddingResponse:
    vectors: tuple[tuple[float, ...], ...]
    usage: EmbeddingUsage


class EmbeddingError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message[:500]
        self.retryable = retryable


class EmbeddingProvider(Protocol):
    name: str
    model: str

    async def embed(self, inputs: Sequence[str]) -> EmbeddingResponse: ...


def _float32(value: float) -> float:
    return float(struct.unpack("!f", struct.pack("!f", value))[0])


def normalize_vector(raw: Sequence[Any]) -> tuple[float, ...]:
    if len(raw) != EMBEDDING_DIMENSIONS:
        raise EmbeddingError(
            "embedding_invalid_output", "Embedding returned invalid output", retryable=False
        )
    values: list[float] = []
    for item in raw:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise EmbeddingError(
                "embedding_invalid_output", "Embedding returned invalid output", retryable=False
            )
        value = float(item)
        if not math.isfinite(value) or abs(value) > 1_000_000:
            raise EmbeddingError(
                "embedding_invalid_output", "Embedding returned invalid output", retryable=False
            )
        values.append(_float32(value))
    norm = math.sqrt(math.fsum(value * value for value in values))
    if not math.isfinite(norm) or norm == 0:
        raise EmbeddingError(
            "embedding_invalid_output", "Embedding returned invalid output", retryable=False
        )
    return tuple(_float32(value / norm) for value in values)


class FakeEmbeddingProvider:
    name = "fake"

    def __init__(self, model: str = "flowtracer-fake-embedding-v1") -> None:
        self.model = model

    async def embed(self, inputs: Sequence[str]) -> EmbeddingResponse:
        if not inputs or len(inputs) > MAX_EMBEDDING_BATCH:
            raise EmbeddingError(
                "embedding_invalid_output", "Embedding input batch is invalid", retryable=False
            )
        vectors: list[tuple[float, ...]] = []
        for value in inputs:
            seed = hashlib.sha256(value.encode("utf-8")).digest()
            raw: list[float] = []
            counter = 0
            while len(raw) < EMBEDDING_DIMENSIONS:
                block = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
                raw.extend((byte - 127.5) / 127.5 for byte in block)
                counter += 1
            vectors.append(normalize_vector(raw[:EMBEDDING_DIMENSIONS]))
        tokens = sum(max(1, len(value) // 4) for value in inputs)
        return EmbeddingResponse(tuple(vectors), EmbeddingUsage(tokens, tokens))


class OpenAICompatibleEmbeddingProvider:
    name = "openai_compatible"

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        if settings.embedding_base_url is None or settings.embedding_api_key is None:
            raise ValueError("OpenAI-compatible embedding configuration is incomplete")
        self.model = settings.embedding_model
        self._url = f"{settings.embedding_base_url.rstrip('/')}/embeddings"
        self._api_key = settings.embedding_api_key.get_secret_value()
        self._client = client

    async def embed(self, inputs: Sequence[str]) -> EmbeddingResponse:
        if not inputs or len(inputs) > MAX_EMBEDDING_BATCH:
            raise EmbeddingError(
                "embedding_invalid_output", "Embedding input batch is invalid", retryable=False
            )
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(
            follow_redirects=False,
            timeout=httpx.Timeout(60.0, connect=5.0, pool=5.0),
        )
        chunks: list[bytes] = []
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
                json={
                    "model": self.model,
                    "input": list(inputs),
                    "dimensions": EMBEDDING_DIMENSIONS,
                },
            ) as response:
                _validate_status(response.status_code)
                _validate_headers(response.headers)
                size = 0
                async for chunk in response.aiter_raw(chunk_size=MAX_EMBEDDING_RAW_READ_BYTES):
                    size += len(chunk)
                    if size > MAX_EMBEDDING_RESPONSE_BYTES:
                        raise EmbeddingError(
                            "embedding_response_too_large",
                            "Embedding response is too large",
                            retryable=False,
                        )
                    chunks.append(chunk)
        except httpx.TimeoutException:
            raise EmbeddingError(
                "embedding_timeout", "Embedding request timed out", retryable=True
            ) from None
        except httpx.TransportError:
            raise EmbeddingError(
                "embedding_provider_unavailable",
                "Embedding provider is unavailable",
                retryable=True,
            ) from None
        finally:
            if owns_client:
                await client.aclose()
        return _parse_response(b"".join(chunks), len(inputs))


def _validate_status(status_code: int) -> None:
    if status_code in {401, 403}:
        raise EmbeddingError(
            "embedding_auth_failed", "Embedding authentication failed", retryable=False
        )
    if status_code == 429:
        raise EmbeddingError(
            "embedding_rate_limited", "Embedding provider rate limited", retryable=True
        )
    if status_code >= 500:
        raise EmbeddingError(
            "embedding_provider_unavailable",
            "Embedding provider is unavailable",
            retryable=True,
        )
    if status_code >= 400 or 300 <= status_code < 400:
        raise EmbeddingError(
            "embedding_provider_unavailable",
            "Embedding provider rejected the request",
            retryable=False,
        )


def _validate_headers(headers: httpx.Headers) -> None:
    encoding = headers.get("content-encoding")
    if encoding and encoding.strip().lower() != "identity":
        raise EmbeddingError(
            "embedding_invalid_output",
            "Embedding response uses unsupported content encoding",
            retryable=False,
        )
    length = headers.get("content-length")
    if length is None:
        return
    normalized = length.strip()
    if not normalized.isascii() or not normalized.isdecimal():
        raise EmbeddingError(
            "embedding_invalid_output",
            "Embedding response has an invalid content length",
            retryable=False,
        )
    if int(normalized) > MAX_EMBEDDING_RESPONSE_BYTES:
        raise EmbeddingError(
            "embedding_response_too_large", "Embedding response is too large", retryable=False
        )


def _reject_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def _usage_int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > 2_147_483_647:
        raise ValueError("invalid usage")
    return int(value)


def _parse_response(content: bytes, expected: int) -> EmbeddingResponse:
    try:
        envelope = json.loads(content.decode("utf-8"), parse_constant=_reject_constant)
        if not isinstance(envelope, dict):
            raise ValueError("invalid envelope")
        data = envelope["data"]
        if not isinstance(data, list) or len(data) != expected:
            raise ValueError("invalid count")
        indexed: dict[int, tuple[float, ...]] = {}
        for item in data:
            if not isinstance(item, dict):
                raise ValueError("invalid data item")
            index = item["index"]
            if isinstance(index, bool) or not isinstance(index, int) or index in indexed:
                raise ValueError("invalid index")
            indexed[index] = normalize_vector(item["embedding"])
        if set(indexed) != set(range(expected)):
            raise ValueError("invalid indexes")
        usage = envelope.get("usage", {})
        if not isinstance(usage, dict):
            raise ValueError("invalid usage")
        input_tokens = _usage_int(usage.get("prompt_tokens", 0))
        total_tokens = _usage_int(usage.get("total_tokens", input_tokens))
        if total_tokens < input_tokens:
            raise ValueError("invalid usage")
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        raise EmbeddingError(
            "embedding_invalid_output", "Embedding returned invalid output", retryable=False
        ) from None
    return EmbeddingResponse(
        tuple(indexed[index] for index in range(expected)),
        EmbeddingUsage(input_tokens, total_tokens),
    )


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_provider == "fake":
        return FakeEmbeddingProvider(settings.embedding_model)
    return OpenAICompatibleEmbeddingProvider(settings)
