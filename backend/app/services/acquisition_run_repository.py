from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domains.acquisition_ports import (
    PublishedEvent,
    RunClaim,
    RunCompletion,
    SourceRuntimeFacts,
)
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
    _claim_run,
    _collection_event,
    _finish_failure,
    _update_source_state,
    heartbeat_run,
)
from app.services.acquisition_attempts import (
    DECISION_VERSION,
    _attempt,
    _circuit_facts,
    _discovery_checkpoint,
    _record_attempt,
)
from app.services.acquisition_types import (
    AcquisitionResult,
    CollectionError,
    ParseResult,
)
from app.services.change_tracking import record_version_evidence


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


def _fill_run_success(
    *,
    run: CollectionRun,
    source: Source,
    backend: BackendName,
    attempt_started_at: datetime,
    result: AcquisitionResult,
    parsed: ParseResult,
    quality_score: Decimal | None,
    created_count: int,
    duplicates: int,
    quality_met: bool,
    fallback_count: int,
    budget_summary: dict[str, Any] | None,
    run_started_at: datetime | None,
    finished_at: datetime,
) -> int:
    run.fetched_count = parsed.fetched_count
    run.created_count = created_count
    run.duplicate_count = duplicates
    run.failed_count = parsed.failed_count
    run.status = (
        CollectionRunStatus.PARTIAL
        if parsed.failed_count or not quality_met
        else CollectionRunStatus.SUCCEEDED
    )
    run.finished_at = finished_at
    run.error_code = None if quality_met else "acquisition_quality_unmet"
    run.error_message = (
        None if quality_met else "Extraction quality did not reach the acceptable bucket"
    )
    run.backend = backend.value
    run.fallback_count = fallback_count
    run.pages_count = 1
    duration_from = run_started_at or attempt_started_at
    duration_ms = max(0, round((finished_at - duration_from).total_seconds() * 1000))
    run.duration_ms = duration_ms
    run.budget_summary = budget_summary if budget_summary is not None else result.budget_used
    run.quality_score = quality_score
    source.last_fetched_at = finished_at
    return duration_ms


def _add_success_attempt(
    session: AsyncSession,
    *,
    run: CollectionRun,
    source: Source,
    backend: BackendName,
    attempt_started_at: datetime,
    result: AcquisitionResult,
    quality_score: Decimal | None,
    finished_at: datetime,
    ordinal: int,
    fallback_reason: str | None,
    attempt_budget_used: dict[str, Any] | None,
    decision_version: str,
) -> None:
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
            ordinal=ordinal,
            fallback_reason=fallback_reason,
            budget_used=attempt_budget_used,
            decision_version=decision_version,
        )
    )


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
    quality_met: bool = True,
    fallback_count: int = 0,
    ordinal: int = 1,
    fallback_reason: str | None = None,
    budget_summary: dict[str, Any] | None = None,
    decision_version: str = DECISION_VERSION,
    attempt_budget_used: dict[str, Any] | None = None,
    run_started_at: datetime | None = None,
    discovery_checkpoint: dict[str, Any] | None = None,
) -> None:
    finished_at = datetime.now(UTC)
    duration_ms = _fill_run_success(
        run=run,
        source=source,
        backend=backend,
        attempt_started_at=attempt_started_at,
        result=result,
        parsed=parsed,
        quality_score=quality_score,
        created_count=len(created),
        duplicates=duplicates,
        quality_met=quality_met,
        fallback_count=fallback_count,
        budget_summary=budget_summary,
        run_started_at=run_started_at,
        finished_at=finished_at,
    )
    _add_success_attempt(
        session,
        run=run,
        source=source,
        backend=backend,
        attempt_started_at=attempt_started_at,
        result=result,
        quality_score=quality_score,
        finished_at=finished_at,
        ordinal=ordinal,
        fallback_reason=fallback_reason,
        attempt_budget_used=attempt_budget_used,
        decision_version=decision_version,
    )
    await _update_source_state(
        session,
        source_id=source.id,
        succeeded=True,
        backend=backend,
        duration_ms=duration_ms,
        error_code=None,
        quality_score=quality_score,
        now=finished_at,
        checkpoint_update=discovery_checkpoint,
    )
    # Shadow-write version evidence in the same transaction; RawItem behavior unchanged.
    await record_version_evidence(
        session,
        run=run,
        parsed=parsed,
        body=result.response.body,
        quality_score=quality_score,
        fetched_at=finished_at,
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
        quality_met: bool = True,
        fallback_count: int = 0,
        attempt_ordinal: int = 1,
        fallback_reason: str | None = None,
        budget_summary: dict[str, Any] | None = None,
        decision_version: str = DECISION_VERSION,
        attempt_budget_used: dict[str, Any] | None = None,
        run_started_at: datetime | None = None,
        discovery_checkpoint: dict[str, Any] | None = None,
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
                quality_met=quality_met,
                fallback_count=fallback_count,
                ordinal=attempt_ordinal,
                fallback_reason=fallback_reason,
                budget_summary=budget_summary,
                decision_version=decision_version,
                attempt_budget_used=attempt_budget_used,
                run_started_at=run_started_at,
                discovery_checkpoint=discovery_checkpoint,
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
        run_started_at: datetime | None = None,
        attempt_ordinal: int = 1,
        fallback_count: int = 0,
        record_attempt: bool = True,
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
            run_started_at=run_started_at,
            attempt_ordinal=attempt_ordinal,
            fallback_count=fallback_count,
            record_attempt=record_attempt,
        )

    async def record_attempt(
        self,
        claim: RunClaim[Source],
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
    ) -> bool:
        return await _record_attempt(
            self._factory,
            claim.run_id,
            claim.claim_token,
            source_id=claim.source.id,
            ordinal=ordinal,
            backend=BackendName(backend_name),
            requested_url=claim.source.normalized_url,
            started_at=attempt_started_at,
            finished_at=attempt_finished_at,
            status=AcquisitionAttemptStatus(status),
            retry_count=retry_count,
            error_code=error_code,
            safe_error=safe_error,
            quality_score=quality_score,
            fallback_reason=fallback_reason,
            budget_used=budget_used,
            bytes_received=bytes_received,
        )

    async def circuit_facts(self, source_id: UUID) -> SourceRuntimeFacts | None:
        return await _circuit_facts(self._factory, source_id)

    async def discovery_checkpoint(self, source_id: UUID) -> dict[str, Any]:
        return await _discovery_checkpoint(self._factory, source_id)

    async def event_for(self, run_id: UUID) -> PublishedEvent[Any] | None:
        return await _collection_event(self._factory, run_id)
