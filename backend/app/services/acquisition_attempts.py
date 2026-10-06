"""Per-attempt persistence helpers shared by the legacy and routed run paths.

Lives in its own module so the routed executor stays within the architecture gate's
module budget and imports only allowed layers (models, domain ports, service types).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domains.acquisition_ports import CrawlPageRecord, SourceRuntimeFacts
from app.models.entities import (
    AcquisitionAttempt,
    AcquisitionAttemptStatus,
    BackendName,
    CollectionRun,
    CollectionRunStatus,
    SourceAcquisitionState,
)
from app.services.acquisition_types import CollectionError, RawCandidate
from app.services.change_tracking import record_page_evidence

DECISION_VERSION = "acquisition-native-v1"


async def next_attempt_ordinal(session: AsyncSession, run_id: UUID, requested: int) -> int:
    """Allocate a per-run attempt ordinal that survives re-claims and crawl layering.

    The requested ordinal is used when still free (fresh runs keep the stage number;
    crawl pages keep stage+1+n); otherwise the value moves past the current maximum,
    which keeps ``(run_id, ordinal)`` unique across crash/resume executions."""
    taken = await session.scalar(
        select(AcquisitionAttempt.id)
        .where(AcquisitionAttempt.run_id == run_id, AcquisitionAttempt.ordinal == requested)
        .limit(1)
    )
    if taken is None:
        return requested
    highest = await session.scalar(
        select(func.max(AcquisitionAttempt.ordinal)).where(AcquisitionAttempt.run_id == run_id)
    )
    return int(highest or 0) + 1


def _attempt(
    *,
    run_id: UUID,
    source_id: UUID,
    backend: BackendName,
    started_at: datetime,
    finished_at: datetime,
    status: AcquisitionAttemptStatus,
    requested_url: str,
    response_url: str | None = None,
    status_code: int | None = None,
    content_type: str | None = None,
    retry_count: int = 0,
    bytes_received: int = 0,
    error: CollectionError | None = None,
    quality_score: Decimal | None = None,
    ordinal: int = 1,
    fallback_reason: str | None = None,
    budget_used: dict[str, Any] | None = None,
    decision_version: str = DECISION_VERSION,
) -> AcquisitionAttempt:
    pages = 1 if status == AcquisitionAttemptStatus.SUCCEEDED else 0
    return AcquisitionAttempt(
        run_id=run_id,
        source_id=source_id,
        ordinal=ordinal,
        backend=backend,
        started_at=started_at,
        finished_at=finished_at,
        status=status,
        requested_url=requested_url,
        final_url=response_url,
        status_code=status_code,
        content_type=content_type,
        duration_ms=max(0, round((finished_at - started_at).total_seconds() * 1000)),
        retry_count=retry_count,
        pages=pages,
        bytes_received=bytes_received,
        budget_used=(
            budget_used
            if budget_used is not None
            else {
                "requests": retry_count + 1,
                "pages": pages,
                "bytes_received": bytes_received,
            }
        ),
        error_code=None if error is None else error.code,
        safe_error=None if error is None else error.safe_message,
        decision_version=decision_version,
        quality_score=quality_score,
        fallback_reason=fallback_reason,
    )


async def _circuit_facts(
    factory: async_sessionmaker[AsyncSession], source_id: UUID
) -> SourceRuntimeFacts | None:
    async with factory() as session:
        state = await session.scalar(
            select(SourceAcquisitionState).where(SourceAcquisitionState.source_id == source_id)
        )
        if state is None:
            return None
        return SourceRuntimeFacts(
            health_status=state.health_status.value,
            consecutive_failures=state.consecutive_failures,
            circuit_open_until=state.circuit_open_until,
            last_error_code=state.last_error_code,
            latency_ewma_ms=state.latency_ewma_ms,
        )


async def _discovery_checkpoint(
    factory: async_sessionmaker[AsyncSession], source_id: UUID
) -> dict[str, Any]:
    """Persisted discovery checkpoint for a source; empty dict when absent."""
    async with factory() as session:
        state = await session.scalar(
            select(SourceAcquisitionState).where(SourceAcquisitionState.source_id == source_id)
        )
        if state is None or not isinstance(state.checkpoint, dict):
            return {}
        return dict(state.checkpoint)


async def _record_attempt(
    factory: async_sessionmaker[AsyncSession],
    run_id: UUID,
    claim_token: UUID,
    *,
    source_id: UUID,
    ordinal: int,
    backend: BackendName,
    requested_url: str,
    started_at: datetime,
    finished_at: datetime,
    status: AcquisitionAttemptStatus,
    retry_count: int,
    error_code: str,
    safe_error: str,
    quality_score: Decimal | None = None,
    fallback_reason: str | None = None,
    budget_used: dict[str, Any] | None = None,
    bytes_received: int = 0,
    decision_version: str = DECISION_VERSION,
) -> bool:
    """Persist one intermediate route attempt without touching run or source state."""
    async with factory() as session:
        run = await session.scalar(
            select(CollectionRun)
            .where(
                CollectionRun.id == run_id,
                CollectionRun.status == CollectionRunStatus.RUNNING,
                CollectionRun.claim_token == claim_token,
            )
            .with_for_update()
        )
        if run is None:
            return False
        ordinal = await next_attempt_ordinal(session, run_id, ordinal)
        session.add(
            _attempt(
                run_id=run_id,
                source_id=source_id,
                backend=backend,
                started_at=started_at,
                finished_at=finished_at,
                status=status,
                requested_url=requested_url,
                retry_count=retry_count,
                bytes_received=bytes_received,
                error=CollectionError(error_code, safe_error),
                quality_score=quality_score,
                ordinal=ordinal,
                fallback_reason=fallback_reason,
                budget_used=budget_used,
                decision_version=decision_version,
            )
        )
        await session.commit()
        return True


def _candidate_from_evidence(payload: dict[str, Any]) -> RawCandidate:
    return RawCandidate(
        external_id=str(payload.get("external_id") or ""),
        canonical_url=str(payload.get("canonical_url") or ""),
        raw_text=str(payload.get("text") or ""),
        content_type=str(payload.get("content_type") or ""),
        title=payload.get("title"),
        published_at=payload.get("published_at"),
        metadata=dict(payload.get("metadata") or {}),
    )


async def write_crawl_page(
    session: AsyncSession,
    *,
    run: CollectionRun,
    source_id: UUID,
    page: CrawlPageRecord,
) -> None:
    """Persist one crawled page: its attempt row, and (on success) version evidence."""
    ordinal = await next_attempt_ordinal(session, run.id, page.ordinal)
    error = (
        None
        if page.error_code is None
        else CollectionError(page.error_code, page.safe_error or "Crawl target failed")
    )
    session.add(
        _attempt(
            run_id=run.id,
            source_id=source_id,
            backend=BackendName(page.backend_name),
            started_at=page.started_at,
            finished_at=page.finished_at,
            status=AcquisitionAttemptStatus(page.status),
            requested_url=page.requested_url,
            response_url=page.response_url,
            status_code=page.status_code,
            content_type=page.content_type,
            retry_count=page.retry_count,
            bytes_received=page.bytes_received,
            error=error,
            quality_score=page.quality_score,
            ordinal=ordinal,
            decision_version=page.decision_version,
            budget_used={
                "requests": max(page.requests_used, page.retry_count + 1),
                "pages": 1 if page.status == "succeeded" else 0,
                "bytes_received": page.bytes_received,
            },
        )
    )
    if page.status != "succeeded" or page.evidence is None:
        return
    await record_page_evidence(
        session,
        run=run,
        candidate=_candidate_from_evidence(page.evidence),
        body=page.evidence.get("body"),
        quality_score=page.quality_score,
        fetched_at=page.finished_at,
    )
