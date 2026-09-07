from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol, TypeVar
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
class PublishedEvent[PublishedEventT]:
    user_id: UUID
    event: PublishedEventT


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
    ) -> bool: ...

    async def event_for(self, run_id: UUID) -> PublishedEvent[PublishedEventT] | None: ...
