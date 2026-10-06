from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domains.acquisition_ports import (
    CrawlPageRecord,
    CrawlStepResult,
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
    Source,
    SourceAcquisitionState,
)
from app.models.raw_item import RawItem
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
    next_attempt_ordinal,
    persist_snapshot_items,
    write_crawl_page,
)
from app.services.acquisition_types import (
    AcquisitionResult,
    CollectionError,
    ParseResult,
)
from app.services.change_tracking import EvidenceResult, record_version_evidence
from app.services.opportunity_ingest import record_opportunity_items

CIRCUIT_PROBE_LEASE_SECONDS = 60


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
    quality_met: bool = True,
    fallback_count: int = 0,
    ordinal: int = 1,
    fallback_reason: str | None = None,
    budget_summary: dict[str, Any] | None = None,
    decision_version: str = DECISION_VERSION,
    attempt_budget_used: dict[str, Any] | None = None,
    run_started_at: datetime | None = None,
    discovery_checkpoint: dict[str, Any] | None = None,
    crawl_pages_fetched: int = 0,
    crawl_pages_failed: int = 0,
    crawl_observed: tuple[str, ...] | None = None,
) -> list[RawItem]:
    """Version evidence first, then qualifying RawItems, then run/state bookkeeping.

    The I2 writer creates a RawItem only for qualifying snapshots (created /
    content_changed); the rest of the observation contributes to duplicate_count."""
    finished_at = datetime.now(UTC)
    created, duplicates = await _write_evidence_and_items(
        session,
        source=source,
        run=run,
        parsed=parsed,
        body=result.response.body,
        quality_score=quality_score,
        finished_at=finished_at,
        crawl_observed=crawl_observed,
    )
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
    await _record_success_bookkeeping(
        session,
        source=source,
        run=run,
        backend=backend,
        attempt_started_at=attempt_started_at,
        result=result,
        quality_score=quality_score,
        finished_at=finished_at,
        duration_ms=duration_ms,
        ordinal=ordinal,
        fallback_reason=fallback_reason,
        attempt_budget_used=attempt_budget_used,
        decision_version=decision_version,
        discovery_checkpoint=discovery_checkpoint,
        crawl_pages_fetched=crawl_pages_fetched,
        crawl_pages_failed=crawl_pages_failed,
    )
    return created


async def _record_success_bookkeeping(
    session: AsyncSession,
    *,
    source: Source,
    run: CollectionRun,
    backend: BackendName,
    attempt_started_at: datetime,
    result: AcquisitionResult,
    quality_score: Decimal | None,
    finished_at: datetime,
    duration_ms: int,
    ordinal: int,
    fallback_reason: str | None,
    attempt_budget_used: dict[str, Any] | None,
    decision_version: str,
    discovery_checkpoint: dict[str, Any] | None,
    crawl_pages_fetched: int,
    crawl_pages_failed: int,
) -> None:
    """Crawl totals, the accepted-stage attempt row, and the source state update."""
    if crawl_pages_fetched or crawl_pages_failed:
        # Crawl pages extend the run totals; any failed target makes the run partial.
        run.fetched_count += crawl_pages_fetched
        run.failed_count += crawl_pages_failed
        if crawl_pages_failed:
            run.status = CollectionRunStatus.PARTIAL
    attempt_ordinal = await next_attempt_ordinal(session, run.id, ordinal)
    _add_success_attempt(
        session,
        run=run,
        source=source,
        backend=backend,
        attempt_started_at=attempt_started_at,
        result=result,
        quality_score=quality_score,
        finished_at=finished_at,
        ordinal=attempt_ordinal,
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


async def _write_evidence_and_items(
    session: AsyncSession,
    *,
    source: Source,
    run: CollectionRun,
    parsed: ParseResult,
    body: bytes,
    quality_score: Decimal | None,
    finished_at: datetime,
    crawl_observed: tuple[str, ...] | None,
) -> tuple[list[RawItem], int]:
    """Version evidence, qualifying RawItems, and opportunity ingest for one success."""
    evidence = await _write_run_evidence(
        session,
        run=run,
        parsed=parsed,
        body=body,
        quality_score=quality_score,
        fetched_at=finished_at,
        crawl_observed=crawl_observed,
    )
    created, duplicates = await persist_snapshot_items(
        session,
        source_id=source.id,
        run_id=run.id,
        writes=evidence.writes,
        fetched_at=finished_at,
    )
    # Opportunity items exist only for opportunity-family sources; other sources untouched.
    await record_opportunity_items(session, source=source, evidence=evidence, body=body)
    return created, duplicates


async def _write_run_evidence(
    session: AsyncSession,
    *,
    run: CollectionRun,
    parsed: ParseResult,
    body: bytes,
    quality_score: Decimal | None,
    fetched_at: datetime,
    crawl_observed: tuple[str, ...] | None,
) -> EvidenceResult:
    """Shadow-write version evidence; a crawl run suppresses removal detection.

    The frontier is consumed once per target (docs/61 §7), so a crawl cycle is not
    a repeated full-observation cycle of the artifact set; miss-streak removal stays
    with the feed/single-page paths that observe every artifact each run."""
    crawl_ran = crawl_observed is not None
    return await record_version_evidence(
        session,
        run=run,
        parsed=parsed,
        body=body,
        quality_score=quality_score,
        fetched_at=fetched_at,
        mark_missing=not crawl_ran,
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
        crawl_pages_fetched: int = 0,
        crawl_pages_failed: int = 0,
        crawl_observed: tuple[str, ...] | None = None,
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
            created = await _record_success(
                session,
                source=source,
                run=run,
                backend=BackendName(backend_name),
                attempt_started_at=attempt_started_at,
                result=result,
                parsed=parsed,
                quality_score=quality_score,
                quality_met=quality_met,
                fallback_count=fallback_count,
                ordinal=attempt_ordinal,
                fallback_reason=fallback_reason,
                budget_summary=budget_summary,
                decision_version=decision_version,
                attempt_budget_used=attempt_budget_used,
                run_started_at=run_started_at,
                discovery_checkpoint=discovery_checkpoint,
                crawl_pages_fetched=crawl_pages_fetched,
                crawl_pages_failed=crawl_pages_failed,
                crawl_observed=crawl_observed,
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

    async def claim_circuit_probe(self, source_id: UUID, *, now: datetime) -> bool:
        async with self._factory() as session:
            result = await session.execute(
                update(SourceAcquisitionState)
                .where(
                    SourceAcquisitionState.source_id == source_id,
                    SourceAcquisitionState.circuit_open_until.is_not(None),
                    SourceAcquisitionState.circuit_open_until <= now,
                )
                .values(
                    circuit_open_until=now + timedelta(seconds=CIRCUIT_PROBE_LEASE_SECONDS),
                    version=SourceAcquisitionState.version + 1,
                )
                .returning(SourceAcquisitionState.source_id)
            )
            claimed = result.scalar_one_or_none() is not None
            await session.commit()
            return claimed

    async def discovery_checkpoint(self, source_id: UUID) -> dict[str, Any]:
        return await _discovery_checkpoint(self._factory, source_id)

    async def crawl_checkpoint(self, source_id: UUID) -> tuple[dict[str, Any], int]:
        async with self._factory() as session:
            state = await session.scalar(
                select(SourceAcquisitionState).where(SourceAcquisitionState.source_id == source_id)
            )
            if state is None or not isinstance(state.checkpoint, dict):
                return {}, 0
            return dict(state.checkpoint), state.version

    async def commit_crawl_step(
        self,
        claim: RunClaim[Source],
        *,
        expected_version: int,
        checkpoint: dict[str, Any],
        page: CrawlPageRecord | None = None,
    ) -> CrawlStepResult | None:
        """Claim-guarded CAS write for one crawl step (reserve/release or page record).

        The state row lock serializes the version check; a claim that is no longer the
        running token (re-claimed or requeued) or a version bumped by another writer
        both return None so the caller stops consuming the frontier."""
        async with self._factory() as session:
            run = await session.scalar(
                select(CollectionRun)
                .where(
                    CollectionRun.id == claim.run_id,
                    CollectionRun.status == CollectionRunStatus.RUNNING,
                    CollectionRun.claim_token == claim.claim_token,
                )
                .with_for_update()
            )
            if run is None:
                return None
            state = await session.scalar(
                select(SourceAcquisitionState)
                .where(SourceAcquisitionState.source_id == claim.source.id)
                .with_for_update()
            )
            if state is None or state.version != expected_version:
                await session.rollback()
                return None
            raw_item_id = None
            if page is not None:
                raw_item_id = await write_crawl_page(
                    session, run=run, source_id=claim.source.id, page=page
                )
            state.checkpoint = checkpoint
            state.version += 1
            await session.commit()
            return CrawlStepResult(expected_version + 1, raw_item_id)

    async def claim_alive(self, claim: RunClaim[Source]) -> bool:
        async with self._factory() as session:
            run_id = await session.scalar(
                select(CollectionRun.id).where(
                    CollectionRun.id == claim.run_id,
                    CollectionRun.status == CollectionRunStatus.RUNNING,
                    CollectionRun.claim_token == claim.claim_token,
                )
            )
            return run_id is not None

    async def event_for(self, run_id: UUID) -> PublishedEvent[Any] | None:
        return await _collection_event(self._factory, run_id)
