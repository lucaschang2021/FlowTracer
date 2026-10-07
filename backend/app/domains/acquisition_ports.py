from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol, TypeVar
from uuid import UUID

SourceKindT = TypeVar("SourceKindT", contravariant=True)
FetchResponseT = TypeVar("FetchResponseT", covariant=True)
AcquisitionRequestT = TypeVar("AcquisitionRequestT", contravariant=True)
AcquisitionResultT = TypeVar("AcquisitionResultT", covariant=True)
EventT = TypeVar("EventT", contravariant=True)
SourceT = TypeVar("SourceT")
PersistedResultT = TypeVar("PersistedResultT", contravariant=True)
ParsedResultT = TypeVar("ParsedResultT", contravariant=True)
PublishedEventT = TypeVar("PublishedEventT")


class ContentFetcher(Protocol[SourceKindT, FetchResponseT]):
    async def fetch(self, url: str, source_type: SourceKindT) -> FetchResponseT: ...


class AcquisitionBackend(Protocol[AcquisitionRequestT, AcquisitionResultT]):
    async def acquire(self, request: AcquisitionRequestT) -> AcquisitionResultT: ...


class EventPublisher(Protocol[EventT]):
    async def publish(self, user_id: UUID, event: EventT) -> None: ...


@dataclass(frozen=True, slots=True)
class RunClaim[SourceT]:
    run_id: UUID
    source: SourceT
    claim_token: UUID


@dataclass(frozen=True, slots=True)
class RunCompletion:
    source_id: UUID
    status: str
    fetched_count: int
    created_count: int
    duplicate_count: int
    failed_count: int
    raw_item_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class SourceRuntimeFacts:
    """Read-only projection of SourceAcquisitionState for router decisions (no I/O)."""

    health_status: str
    consecutive_failures: int
    circuit_open_until: datetime | None
    last_error_code: str | None
    latency_ewma_ms: int | None


@dataclass(frozen=True, slots=True)
class PublishedEvent[PublishedEventT]:
    user_id: UUID
    event: PublishedEventT


@dataclass(frozen=True, slots=True)
class CrawlPageRecord:
    """Primitive-only per-page record persisted atomically with its checkpoint step.

    Layer-neutral by design: the repository implementation rebuilds the service-layer
    candidate/error types from these fields. ``evidence`` (when present) carries the
    parsed page observation as ``{text, title, canonical_url, content_type,
    external_id, published_at, metadata, body}``.
    """

    requested_url: str
    ordinal: int
    status: str
    started_at: datetime
    finished_at: datetime
    backend_name: str
    decision_version: str
    status_code: int | None = None
    response_url: str | None = None
    content_type: str | None = None
    retry_count: int = 0
    bytes_received: int = 0
    requests_used: int = 0
    error_code: str | None = None
    safe_error: str | None = None
    quality_score: Decimal | None = None
    evidence: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class CrawlFetched:
    """One crawl fetch outcome from the transport port (bounded, already billed)."""

    final_url: str
    content_type: str
    body: bytes
    status_code: int
    retry_count: int
    requests_used: int


@dataclass(frozen=True, slots=True)
class CrawlStepResult:
    """One committed crawl step: the new checkpoint version and any created RawItem."""

    version: int
    raw_item_id: UUID | None = None


class CrawlTransport(Protocol):
    """Provider port for WP-5 I2 crawl fetches.

    Implementations must route every request through the SafeFetcher pipeline
    (NetworkPolicy, per-hop validation with ``validator``, hop/retry accounting);
    ``validator`` is invoked before every request including redirect hops.
    """

    async def fetch_page(
        self,
        url: str,
        *,
        validator: Callable[[str], None],
        max_requests: int,
        max_bytes: int,
        deadline_monotonic: float | None,
        max_retries: int,
        min_delay_seconds: float,
        content_types: frozenset[str] | None = None,
    ) -> CrawlFetched: ...


class AcquisitionRunRepository(Protocol[SourceT, PersistedResultT, ParsedResultT, PublishedEventT]):
    async def claim_run(
        self, run_id: UUID, *, worker_id: str, now: datetime | None = None
    ) -> RunClaim[SourceT] | None: ...

    async def heartbeat(self, run_id: UUID, claim_token: UUID) -> bool: ...

    async def finish_success(
        self,
        claim: RunClaim[SourceT],
        *,
        backend_name: str,
        attempt_started_at: datetime,
        result: PersistedResultT,
        parsed: ParsedResultT,
        quality_score: Decimal | None,
        quality_met: bool = True,
        fallback_count: int = 0,
        attempt_ordinal: int = 1,
        fallback_reason: str | None = None,
        budget_summary: dict[str, Any] | None = None,
        decision_version: str = ...,
        attempt_budget_used: dict[str, Any] | None = None,
        run_started_at: datetime | None = None,
        discovery_checkpoint: dict[str, Any] | None = None,
        crawl_pages_fetched: int = 0,
        crawl_pages_failed: int = 0,
        crawl_observed: tuple[str, ...] | None = None,
    ) -> RunCompletion | None: ...

    async def finish_failure(
        self,
        claim: RunClaim[SourceT],
        *,
        backend_name: str,
        attempt_started_at: datetime,
        retries: int,
        error_code: str,
        safe_error: str,
        run_started_at: datetime | None = None,
        attempt_ordinal: int = 1,
        fallback_count: int = 0,
        record_attempt: bool = True,
    ) -> bool: ...

    async def record_attempt(
        self,
        claim: RunClaim[SourceT],
        *,
        ordinal: int,
        backend_name: str,
        attempt_started_at: datetime,
        attempt_finished_at: datetime,
        status: str,
        retry_count: int,
        error_code: str,
        safe_error: str,
        quality_score: Decimal | None = None,
        fallback_reason: str | None = None,
        budget_used: dict[str, Any] | None = None,
        bytes_received: int = 0,
    ) -> bool: ...

    async def circuit_facts(self, source_id: UUID) -> SourceRuntimeFacts | None: ...

    async def claim_circuit_probe(self, source_id: UUID, *, now: datetime) -> bool:
        """Atomically claim the single half-open probe slot; False when one is in flight."""
        ...

    async def discovery_checkpoint(self, source_id: UUID) -> dict[str, Any]: ...

    async def crawl_checkpoint(self, source_id: UUID) -> tuple[dict[str, Any], int]:
        """Checkpoint document plus the optimistic-lock version it was read at."""
        ...

    async def commit_crawl_step(
        self,
        claim: RunClaim[SourceT],
        *,
        expected_version: int,
        checkpoint: dict[str, Any],
        page: CrawlPageRecord | None = None,
    ) -> CrawlStepResult | None:
        """CAS one crawl step: claim-guarded checkpoint write, optional page record.

        Returns the new version (plus any RawItem the page commit created), or None
        when the claim is gone or the state version no longer matches.
        """
        ...

    async def claim_alive(self, claim: RunClaim[SourceT]) -> bool:
        """True while this exact claim still owns a running run."""
        ...

    async def event_for(self, run_id: UUID) -> PublishedEvent[PublishedEventT] | None: ...
