from __future__ import annotations

import math
import struct
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

EMBEDDING_DIMENSIONS = 1536
MAX_EMBEDDING_BATCH = 16


@dataclass(frozen=True)
class AnalysisRequest:
    title: str
    content: str
    radar_name: str
    radar_goal: str
    categories: tuple[str, ...]
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class ProviderUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class ProviderResponse:
    content: str
    usage: ProviderUsage


class ProviderError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message[:500]
        self.retryable = retryable


class AnalysisProvider(Protocol):
    name: str
    model: str

    async def analyze(
        self, request: AnalysisRequest, *, repair_error: str | None = None
    ) -> ProviderResponse: ...


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
