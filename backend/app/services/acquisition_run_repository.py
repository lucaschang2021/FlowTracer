from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domains.acquisition_ports import PublishedEvent, RunClaim, RunCompletion
from app.models.entities import (
    AcquisitionAttemptStatus,
    BackendName,
    CollectionRun,
    CollectionRunStatus,
    RawItem,
    RawItemStatus,
    Source,
)
from app.services.acquisition import (
    _attempt,
    _claim_run,
    _collection_event,
    _finish_failure,
    _update_source_state,
    heartbeat_run,
)
from app.services.acquisition_types import (
    AcquisitionResult,
    CollectionError,
    ParseResult,
)


async def _persist_candidates(
    session: AsyncSession,
    *,
    source: Source,
    run: CollectionRun,
    parsed: ParseResult,
) -> tuple[list[RawItem], int]:
    created: list[RawItem] = []
    duplicates = 0
    for candidate in parsed.candidates:
        content_hash = hashlib.sha256(candidate.raw_text.encode("utf-8")).hexdigest()
        predicates = [RawItem.external_id == candidate.external_id]
        if candidate.dedupe_by_canonical:
            predicates.append(RawItem.canonical_url == candidate.canonical_url)
        predicates.append(RawItem.content_hash == content_hash)
        duplicate = await session.scalar(
            select(RawItem.id).where(RawItem.source_id == source.id, or_(*predicates))
        )
        if duplicate is not None:
            duplicates += 1
            continue
        item = RawItem(
            source_id=source.id,
            collection_run_id=run.id,
            external_id=candidate.external_id,
            canonical_url=candidate.canonical_url,
            title=candidate.title,
            published_at=candidate.published_at,
            fetched_at=datetime.now(UTC),
            content_type=candidate.content_type,
            raw_text=candidate.raw_text,
            content_hash=content_hash,
            item_metadata=candidate.metadata,
            status=RawItemStatus.FETCHED,
        )
        session.add(item)
        created.append(item)
    return created, duplicates


async def _record_success(
    session: AsyncSession,
    *,
    source: Source,
    run: CollectionRun,
    backend: BackendName,
    attempt_started_at: datetime,
    result: AcquisitionResult,
    parsed: ParseResult,
    quality_score: Decimal | None,
    created: list[RawItem],
    duplicates: int,
) -> None:
    run.fetched_count = parsed.fetched_count
    run.created_count = len(created)
    run.duplicate_count = duplicates
    run.failed_count = parsed.failed_count
    run.status = (
        CollectionRunStatus.PARTIAL if parsed.failed_count else CollectionRunStatus.SUCCEEDED
    )
    finished_at = datetime.now(UTC)
    run.finished_at = finished_at
    run.error_code = None
    run.error_message = None
    run.backend = backend.value
    run.pages_count = 1
    run.duration_ms = max(0, round((finished_at - attempt_started_at).total_seconds() * 1000))
    run.budget_summary = result.budget_used
    run.quality_score = quality_score
    source.last_fetched_at = finished_at
    session.add(
        _attempt(
            run_id=run.id,
            source_id=source.id,
            backend=backend,
            started_at=attempt_started_at,
            finished_at=finished_at,
            status=AcquisitionAttemptStatus.SUCCEEDED,
            requested_url=source.normalized_url,
            response_url=result.response.final_url,
            status_code=result.response.status_code,
            content_type=result.response.content_type,
            retry_count=result.retry_count,
            bytes_received=len(result.response.body),
            quality_score=quality_score,
        )
    )
    await _update_source_state(
        session,
        source_id=source.id,
        succeeded=True,
        backend=backend,
        duration_ms=run.duration_ms,
        error_code=None,
        quality_score=quality_score,
        now=finished_at,
    )


class SqlAlchemyAcquisitionRunRepository:
    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    async def claim_run(
        self, run_id: UUID, *, worker_id: str, now: datetime | None = None
    ) -> RunClaim[Source] | None:
        claimed = await _claim_run(self._factory, run_id, worker_id=worker_id, now=now)
        if claimed is None:
            return None
        source, claim_token = claimed
        return RunClaim(run_id, source, claim_token)

    async def heartbeat(self, run_id: UUID, claim_token: UUID) -> bool:
        return await heartbeat_run(self._factory, run_id, claim_token)

    async def finish_success(
        self,
        claim: RunClaim[Source],
        *,
        backend_name: str,
        attempt_started_at: datetime,
        result: AcquisitionResult,
        parsed: ParseResult,
        quality_score: Decimal | None,
    ) -> RunCompletion | None:
        async with self._factory() as session:
            source = await session.scalar(
                select(Source).where(Source.id == claim.source.id).with_for_update()
            )
            run = await session.scalar(
                select(CollectionRun)
                .where(
                    CollectionRun.id == claim.run_id,
                    CollectionRun.status == CollectionRunStatus.RUNNING,
                    CollectionRun.claim_token == claim.claim_token,
                )
                .with_for_update()
            )
            if source is None or run is None:
                await session.rollback()
                return None
            created, duplicates = await _persist_candidates(
                session, source=source, run=run, parsed=parsed
            )
            await _record_success(
                session,
                source=source,
                run=run,
                backend=BackendName(backend_name),
                attempt_started_at=attempt_started_at,
                result=result,
                parsed=parsed,
                quality_score=quality_score,
                created=created,
                duplicates=duplicates,
            )
            await session.commit()
            return RunCompletion(
                source.id,
                run.status.value,
                run.fetched_count,
                run.created_count,
                run.duplicate_count,
                run.failed_count,
                tuple(item.id for item in created),
            )

    async def finish_failure(
        self,
        claim: RunClaim[Source],
        *,
        backend_name: str,
        attempt_started_at: datetime,
        retries: int,
        error_code: str,
        safe_error: str,
    ) -> bool:
        return await _finish_failure(
            self._factory,
            claim.run_id,
            claim.claim_token,
            claim.source,
            BackendName(backend_name),
            attempt_started_at,
            retries,
            CollectionError(error_code, safe_error),
        )

    async def event_for(self, run_id: UUID) -> PublishedEvent[Any] | None:
        return await _collection_event(self._factory, run_id)
