from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from app.models.entities import AcquisitionMode, DiscoveryMode, SourceFamily, SourceType
from app.schemas.resources import AcquisitionProfileV1


class CollectionError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message[:500]
        self.retryable = retryable
        self.retry_count = 0


@dataclass(frozen=True, slots=True)
class FetchResponse:
    final_url: str
    content_type: str
    body: bytes
    status_code: int = 200


class AcquisitionFetcher(Protocol):
    async def fetch(self, url: str, source_type: SourceType) -> FetchResponse: ...


@dataclass(frozen=True, slots=True)
class AcquisitionRequest:
    source_id: UUID
    run_id: UUID
    target_url: str
    source_type: SourceType
    source_family: SourceFamily
    mode: AcquisitionMode
    discovery_mode: DiscoveryMode
    profile: AcquisitionProfileV1
    correlation_id: str | None


@dataclass(frozen=True, slots=True)
class AcquisitionResult:
    response: FetchResponse
    retry_count: int
    budget_used: dict[str, int]


class AcquisitionBackend(Protocol):
    async def acquire(self, request: AcquisitionRequest) -> AcquisitionResult: ...


@dataclass(frozen=True, slots=True)
class RawCandidate:
    external_id: str
    canonical_url: str
    raw_text: str
    content_type: str
    title: str | None = None
    published_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    dedupe_by_canonical: bool = True


@dataclass(frozen=True, slots=True)
class ParseResult:
    candidates: list[RawCandidate]
    failed_count: int = 0

    @property
    def fetched_count(self) -> int:
        return len(self.candidates) + self.failed_count
