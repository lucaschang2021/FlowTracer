from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import AppError
from app.core.logging import get_logger
from app.domains.acquisition_ports import (
    AcquisitionBackend as AcquisitionBackendPort,
)
from app.domains.acquisition_ports import (
    AcquisitionRunRepository,
    PublishedEvent,
    RunClaim,
)
from app.models.entities import (
    AcquisitionAttempt,
    AcquisitionAttemptStatus,
    BackendName,
    CollectionRun,
    CollectionRunStatus,
    CollectionTriggerType,
    RawItem,
    RawItemStatus,
    ResourceStatus,
    Source,
    SourceAcquisitionState,
    SourceHealthStatus,
    SourceType,
)
from app.schemas.resources import AcquisitionProfileV1
from app.services.acquisition_parsers import parse_feed, parse_html
from app.services.acquisition_types import (
    AcquisitionRequest,
    AcquisitionResult,
    CollectionError,
    ParseResult,
)
from app.services.events import EventPublisher, build_event, publish_safely
from app.services.extraction import attach_extraction_observations
from app.services.extraction_quality import aggregate_quality, update_quality_ewma
from app.services.resources import get_source, resource_not_found

Dispatch = Callable[[str, str], None]
LEASE_DURATION = timedelta(minutes=10)
MAX_CLAIMS = 3
DECISION_VERSION = "acquisition-native-v1"
RunRepository = AcquisitionRunRepository[Source, AcquisitionResult, ParseResult, Any]
RunBackend = AcquisitionBackendPort[AcquisitionRequest, AcquisitionResult]


async def _collection_event(
    factory: async_sessionmaker[AsyncSession], run_id: UUID
) -> PublishedEvent[Any] | None:
    async with factory() as session:
        row = (
            await session.execute(
                select(CollectionRun, Source.user_id)
                .join(Source, Source.id == CollectionRun.source_id)
                .where(CollectionRun.id == run_id)
            )
        ).one_or_none()
        if row is None:
            return None
        run, user_id = row
        event = build_event(
            "collection.updated",
            run.id,
            f"{run.status.value}:{run.updated_at.isoformat()}",
            {
                "collection_run_id": run.id,
                "source_id": run.source_id,
                "status": run.status,
                "fetched_count": run.fetched_count,
                "created_count": run.created_count,
                "duplicate_count": run.duplicate_count,
                "failed_count": run.failed_count,
            },
            occurred_at=run.updated_at,
        )
        return PublishedEvent(user_id, event)


async def publish_collection_updated(
    factory: async_sessionmaker[AsyncSession],
    run_id: UUID,
    publisher: EventPublisher | None,
) -> bool:
    published = await _collection_event(factory, run_id)
    if published is None:
        return False
    return await publish_safely(
        publisher,
        user_id=published.user_id,
        event=published.event,
        resource_id=run_id,
    )


def validate_idempotency_key(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not 1 <= len(normalized) <= 128 or any(
        ord(character) < 32 or ord(character) > 126 for character in normalized
    ):
        raise AppError(status_code=422, code="invalid_request", message="Invalid Idempotency-Key")
    return normalized


async def create_manual_run(
    session: AsyncSession,
    *,
    user_id: UUID,
    source_id: UUID,
    idempotency_key: str | None,
) -> tuple[CollectionRun, bool]:
    source = await get_source(session, user_id=user_id, source_id=source_id)
    if source.status != ResourceStatus.ACTIVE:
        raise AppError(status_code=409, code="source_not_active", message="Source is not active")
    if source.source_type == SourceType.API:
        raise AppError(
            status_code=422,
            code="unsupported_source_type",
            message="Source type is not supported",
        )
    key = validate_idempotency_key(idempotency_key)
    owned_source_id = source.id
    if key is not None:
        existing = await session.scalar(
            select(CollectionRun).where(
                CollectionRun.source_id == owned_source_id,
                CollectionRun.idempotency_key == key,
            )
        )
        if existing is not None:
            return existing, False
    run = CollectionRun(
        source_id=owned_source_id,
        triggered_by_user_id=user_id,
        trigger_type=CollectionTriggerType.MANUAL,
        status=CollectionRunStatus.QUEUED,
        idempotency_key=key,
    )
    session.add(run)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        if key is None:
            raise
        existing = await session.scalar(
            select(CollectionRun).where(
                CollectionRun.source_id == owned_source_id,
                CollectionRun.idempotency_key == key,
            )
        )
        if existing is None:
            raise
        return existing, False
    await session.refresh(run)
    return run, True


async def mark_queue_failure(session: AsyncSession, run_id: UUID) -> None:
    run = await session.get(CollectionRun, run_id)
    if run is not None and run.status == CollectionRunStatus.QUEUED:
        run.error_code = "queue_unavailable"
        run.error_message = "Collection queue is temporarily unavailable"
        await session.commit()


async def get_owned_run(session: AsyncSession, *, user_id: UUID, run_id: UUID) -> CollectionRun:
    run = await session.scalar(
        select(CollectionRun)
        .join(Source, Source.id == CollectionRun.source_id)
        .where(
            CollectionRun.id == run_id,
            Source.user_id == user_id,
            Source.deleted_at.is_(None),
        )
    )
    if run is None:
        raise resource_not_found()
    return run


async def create_retry_run(
    session: AsyncSession, *, user_id: UUID, original_run_id: UUID
) -> tuple[CollectionRun, bool]:
    original = await session.scalar(
        select(CollectionRun)
        .join(Source, Source.id == CollectionRun.source_id)
        .where(
            CollectionRun.id == original_run_id,
            Source.user_id == user_id,
            Source.deleted_at.is_(None),
        )
        .with_for_update(of=CollectionRun)
    )
    if original is None:
        raise resource_not_found()
    source = await session.scalar(
        select(Source).where(Source.id == original.source_id).with_for_update()
    )
    if source is None or source.deleted_at is not None or source.user_id != user_id:
        raise resource_not_found()
    if source.status != ResourceStatus.ACTIVE:
        raise AppError(status_code=409, code="source_not_active", message="Source is not active")
    if original.status not in {CollectionRunStatus.FAILED, CollectionRunStatus.PARTIAL}:
        raise AppError(
            status_code=409,
            code="collection_run_not_retryable",
            message="Collection run cannot be retried",
        )
    key = f"retry:{original.id}"
    existing = await session.scalar(
        select(CollectionRun).where(
            CollectionRun.source_id == original.source_id,
            CollectionRun.idempotency_key == key,
        )
    )
    if existing is not None:
        await session.commit()
        return existing, False
    child = CollectionRun(
        source_id=original.source_id,
        triggered_by_user_id=user_id,
        trigger_type=CollectionTriggerType.MANUAL,
        status=CollectionRunStatus.QUEUED,
        idempotency_key=key,
    )
    session.add(child)
    await session.commit()
    await session.refresh(child)
    return child, True


async def list_source_runs(
    session: AsyncSession,
    *,
    user_id: UUID,
    source_id: UUID,
    page: int,
    page_size: int,
    status: CollectionRunStatus | None,
    trigger_type: CollectionTriggerType | None,
) -> tuple[list[CollectionRun], int]:
    await get_source(session, user_id=user_id, source_id=source_id)
    predicates = [CollectionRun.source_id == source_id]
    if status is not None:
        predicates.append(CollectionRun.status == status)
    if trigger_type is not None:
        predicates.append(CollectionRun.trigger_type == trigger_type)
    total = int(
        await session.scalar(select(func.count()).select_from(CollectionRun).where(*predicates))
        or 0
    )
    runs = list(
        (
            await session.scalars(
                select(CollectionRun)
                .where(*predicates)
                .order_by(CollectionRun.created_at.desc(), CollectionRun.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    return runs, total


async def list_run_items(
    session: AsyncSession,
    *,
    user_id: UUID,
    run_id: UUID,
    page: int,
    page_size: int,
    status: RawItemStatus | None,
) -> tuple[list[RawItem], int]:
    await get_owned_run(session, user_id=user_id, run_id=run_id)
    predicates = [RawItem.collection_run_id == run_id]
    if status is not None:
        predicates.append(RawItem.status == status)
    total = int(
        await session.scalar(select(func.count()).select_from(RawItem).where(*predicates)) or 0
    )
    items = list(
        (
            await session.scalars(
                select(RawItem)
                .where(*predicates)
                .order_by(RawItem.created_at.desc(), RawItem.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    return items, total


async def schedule_due_sources(
    factory: async_sessionmaker[AsyncSession],
    *,
    batch_size: int = 100,
    now: datetime | None = None,
    publisher: EventPublisher | None = None,
) -> int:
    current = now or datetime.now(UTC)
    bucket = current.replace(second=0, microsecond=0).isoformat()
    async with factory() as session:
        sources = list(
            (
                await session.scalars(
                    select(Source)
                    .where(
                        Source.status == ResourceStatus.ACTIVE,
                        Source.source_type.in_([SourceType.RSS, SourceType.URL]),
                        Source.deleted_at.is_(None),
                        or_(Source.next_fetch_at.is_(None), Source.next_fetch_at <= current),
                    )
                    .order_by(Source.next_fetch_at.asc().nullsfirst(), Source.id.asc())
                    .with_for_update(skip_locked=True)
                    .limit(batch_size)
                )
            ).all()
        )
        created_ids: list[UUID] = []
        for source in sources:
            key = f"schedule:{bucket}"
            existing = await session.scalar(
                select(CollectionRun.id).where(
                    CollectionRun.source_id == source.id,
                    CollectionRun.idempotency_key == key,
                )
            )
            if existing is None:
                run = CollectionRun(
                    source_id=source.id,
                    trigger_type=CollectionTriggerType.SCHEDULE,
                    status=CollectionRunStatus.QUEUED,
                    idempotency_key=key,
                )
                session.add(run)
                await session.flush()
                created_ids.append(run.id)
            source.next_fetch_at = current + timedelta(minutes=source.poll_interval_minutes)
        await session.commit()
    for run_id in created_ids:
        await publish_collection_updated(factory, run_id, publisher)
    return len(created_ids)


async def dispatch_queued_runs(
    factory: async_sessionmaker[AsyncSession], dispatch: Dispatch, *, batch_size: int = 100
) -> int:
    await recover_stale_runs(factory, batch_size=batch_size)
    async with factory() as session:
        runs = list(
            (
                await session.scalars(
                    select(CollectionRun)
                    .where(CollectionRun.status == CollectionRunStatus.QUEUED)
                    .order_by(CollectionRun.created_at.asc(), CollectionRun.id.asc())
                    .with_for_update(skip_locked=True)
                    .limit(batch_size)
                )
            ).all()
        )
        dispatched = 0
        for run in runs:
            try:
                dispatch(str(run.id), str(uuid.uuid4()))
            except Exception:
                run.error_code = "queue_unavailable"
                run.error_message = "Collection queue is temporarily unavailable"
            else:
                run.error_code = None
                run.error_message = None
                dispatched += 1
        await session.commit()
        return dispatched


async def recover_stale_runs(
    factory: async_sessionmaker[AsyncSession],
    *,
    batch_size: int = 100,
    now: datetime | None = None,
) -> int:
    current = now or datetime.now(UTC)
    async with factory() as session:
        runs = list(
            (
                await session.scalars(
                    select(CollectionRun)
                    .where(
                        CollectionRun.status == CollectionRunStatus.RUNNING,
                        CollectionRun.lease_expires_at <= current,
                    )
                    .order_by(CollectionRun.lease_expires_at.asc(), CollectionRun.id.asc())
                    .with_for_update(skip_locked=True)
                    .limit(batch_size)
                )
            ).all()
        )
        for run in runs:
            if run.claim_count >= MAX_CLAIMS:
                run.status = CollectionRunStatus.FAILED
                run.finished_at = current
                run.failed_count = max(run.failed_count, 1)
                run.error_code = "run_lease_exhausted"
                run.error_message = "Collection run lease recovery is exhausted"
            else:
                run.status = CollectionRunStatus.QUEUED
                run.error_code = "lease_expired"
                run.error_message = "Collection run lease expired and was requeued"
        await session.commit()
        return len(runs)


async def heartbeat_run(
    factory: async_sessionmaker[AsyncSession],
    run_id: UUID,
    claim_token: UUID,
    *,
    now: datetime | None = None,
) -> bool:
    current = now or datetime.now(UTC)
    async with factory() as session:
        result = await session.execute(
            update(CollectionRun)
            .where(
                CollectionRun.id == run_id,
                CollectionRun.status == CollectionRunStatus.RUNNING,
                CollectionRun.claim_token == claim_token,
            )
            .values(heartbeat_at=current, lease_expires_at=current + LEASE_DURATION)
        )
        await session.commit()
        return bool(getattr(result, "rowcount", 0))


async def _heartbeat_loop(
    factory: async_sessionmaker[AsyncSession], run_id: UUID, claim_token: UUID
) -> None:
    while True:
        await asyncio.sleep(60)
        if not await heartbeat_run(factory, run_id, claim_token):
            return


async def _claim_run(
    factory: async_sessionmaker[AsyncSession],
    run_id: UUID,
    *,
    worker_id: str,
    now: datetime | None = None,
) -> tuple[Source, UUID] | None:
    current = now or datetime.now(UTC)
    async with factory() as session:
        run = await session.scalar(
            select(CollectionRun).where(CollectionRun.id == run_id).with_for_update()
        )
        if run is None or run.status != CollectionRunStatus.QUEUED:
            await session.rollback()
            return None
        if run.claim_count >= MAX_CLAIMS:
            run.status = CollectionRunStatus.FAILED
            run.finished_at = current
            run.failed_count = max(run.failed_count, 1)
            run.error_code = "run_lease_exhausted"
            run.error_message = "Collection run lease recovery is exhausted"
            await session.commit()
            return None
        source = await session.get(Source, run.source_id)
        if source is None or source.deleted_at is not None or source.source_type == SourceType.API:
            run.status = CollectionRunStatus.FAILED
            run.finished_at = current
            run.failed_count = 1
            run.error_code = "internal_collection_error"
            run.error_message = "Source is unavailable"
            await session.commit()
            return None
        run.status = CollectionRunStatus.RUNNING
        run.started_at = run.started_at or current
        run.claimed_at = current
        run.heartbeat_at = current
        run.lease_expires_at = current + LEASE_DURATION
        run.worker_id = worker_id[:160]
        run.claim_token = uuid.uuid4()
        run.claim_count += 1
        run.error_code = None
        run.error_message = None
        await session.commit()
        claim_token = run.claim_token
        if claim_token is None:
            raise RuntimeError("Collection run claim token was not created")
        session.expunge(source)
        return source, claim_token


async def _update_source_state(
    session: AsyncSession,
    *,
    source_id: UUID,
    succeeded: bool,
    backend: BackendName,
    duration_ms: int,
    error_code: str | None,
    quality_score: Decimal | None = None,
    now: datetime,
) -> None:
    state = await session.scalar(
        select(SourceAcquisitionState)
        .where(SourceAcquisitionState.source_id == source_id)
        .with_for_update()
    )
    if state is None:
        state = SourceAcquisitionState(
            source_id=source_id,
            health_status=SourceHealthStatus.HEALTHY,
            success_count=0,
            failure_count=0,
            consecutive_failures=0,
            checkpoint={},
            version=1,
        )
        session.add(state)
    else:
        state.version += 1
    state.last_backend = backend
    state.latency_ewma_ms = (
        duration_ms
        if state.latency_ewma_ms is None
        else round(state.latency_ewma_ms * 0.8 + duration_ms * 0.2)
    )
    state.quality_ewma = update_quality_ewma(state.quality_ewma, quality_score)
    if succeeded:
        state.success_count += 1
        state.consecutive_failures = 0
        state.last_success_at = now
        state.last_error_code = None
        state.health_status = (
            SourceHealthStatus.CIRCUIT_OPEN
            if state.circuit_open_until is not None and state.circuit_open_until > now
            else SourceHealthStatus.HEALTHY
        )
    else:
        state.failure_count += 1
        state.consecutive_failures += 1
        state.last_failure_at = now
        state.last_error_code = error_code
        state.health_status = (
            SourceHealthStatus.CIRCUIT_OPEN
            if state.circuit_open_until is not None and state.circuit_open_until > now
            else (
                SourceHealthStatus.UNHEALTHY
                if state.consecutive_failures >= 5
                else SourceHealthStatus.DEGRADED
            )
        )


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
) -> AcquisitionAttempt:
    return AcquisitionAttempt(
        run_id=run_id,
        source_id=source_id,
        ordinal=1,
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
        pages=1 if status == AcquisitionAttemptStatus.SUCCEEDED else 0,
        bytes_received=bytes_received,
        budget_used={
            "requests": retry_count + 1,
            "pages": 1 if status == AcquisitionAttemptStatus.SUCCEEDED else 0,
            "bytes_received": bytes_received,
        },
        error_code=None if error is None else error.code,
        safe_error=None if error is None else error.safe_message,
        decision_version=DECISION_VERSION,
        quality_score=quality_score,
    )


async def _finish_failure(
    factory: async_sessionmaker[AsyncSession],
    run_id: UUID,
    claim_token: UUID,
    source: Source,
    backend: BackendName,
    attempt_started_at: datetime,
    retries: int,
    error: CollectionError,
) -> bool:
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
        finished_at = datetime.now(UTC)
        run.status = CollectionRunStatus.FAILED
        run.finished_at = finished_at
        run.failed_count = 1
        run.error_code = error.code
        run.error_message = error.safe_message
        run.duration_ms = max(0, round((finished_at - attempt_started_at).total_seconds() * 1000))
        backend_selected = error.code not in {
            "acquisition_mode_unsupported",
            "source_profile_invalid",
        }
        if backend_selected:
            run.backend = backend.value
        blocked_codes = {
            "network_policy_denied",
            "site_policy_denied",
            "acquisition_budget_exhausted",
            "ssrf_blocked",
            "unsupported_port",
        }
        if backend_selected:
            session.add(
                _attempt(
                    run_id=run.id,
                    source_id=source.id,
                    backend=backend,
                    started_at=attempt_started_at,
                    finished_at=finished_at,
                    status=(
                        AcquisitionAttemptStatus.BLOCKED
                        if error.code in blocked_codes
                        else AcquisitionAttemptStatus.FAILED
                    ),
                    requested_url=source.normalized_url,
                    retry_count=retries,
                    error=error,
                )
            )
        if backend_selected:
            await _update_source_state(
                session,
                source_id=source.id,
                succeeded=False,
                backend=backend,
                duration_ms=run.duration_ms,
                error_code=error.code,
                now=finished_at,
            )
        await session.commit()
        return True


async def _repository_heartbeat_loop(repository: RunRepository, claim: RunClaim[Source]) -> None:
    while True:
        await asyncio.sleep(60)
        if not await repository.heartbeat(claim.run_id, claim.claim_token):
            return


async def _publish_repository_event(
    repository: RunRepository,
    run_id: UUID,
    publisher: EventPublisher | None,
) -> None:
    published = await repository.event_for(run_id)
    if published is not None:
        await publish_safely(
            publisher,
            user_id=published.user_id,
            event=published.event,
            resource_id=run_id,
        )


async def execute_run(
    repository: RunRepository,
    run_id: UUID,
    *,
    backend: RunBackend,
    correlation_id: str | None = None,
    task_id: str | None = None,
    raw_dispatch: Dispatch | None = None,
    publisher: EventPublisher | None = None,
) -> bool:
    started = time.monotonic()
    worker_id = (task_id or correlation_id or f"worker-{uuid.uuid4()}").strip()
    claimed = await repository.claim_run(run_id, worker_id=worker_id)
    if claimed is None:
        await _publish_repository_event(repository, run_id, publisher)
        return False
    source = claimed.source
    backend_name = (
        BackendName.RSS if source.source_type == SourceType.RSS else BackendName.NATIVE_HTTP
    )
    attempt_started_at = datetime.now(UTC)
    heartbeat_task = asyncio.create_task(_repository_heartbeat_loop(repository, claimed))
    await _publish_repository_event(repository, run_id, publisher)
    retries = 0
    try:
        try:
            profile = AcquisitionProfileV1.model_validate(source.acquisition_profile)
        except ValueError:
            raise CollectionError(
                "source_profile_invalid", "Source acquisition profile is invalid"
            ) from None
        result = await backend.acquire(
            AcquisitionRequest(
                source_id=source.id,
                run_id=run_id,
                target_url=source.normalized_url,
                source_type=source.source_type,
                source_family=source.source_family,
                mode=source.acquisition_mode,
                discovery_mode=source.discovery_mode,
                profile=profile,
                correlation_id=correlation_id,
            )
        )
        response = result.response
        retries = result.retry_count
        parsed = (
            parse_feed(response)
            if source.source_type == SourceType.RSS
            else parse_html(response, source.normalized_url)
        )
        result = attach_extraction_observations(
            result,
            family=source.source_family,
            content_profile=profile.content_profile.value,
            source_type=source.source_type,
            parsed=parsed,
        )
        aggregate = aggregate_quality(
            [observation.evidence.quality_score for observation in result.observations]
        )
        completion = await repository.finish_success(
            claimed,
            backend_name=backend_name.value,
            attempt_started_at=attempt_started_at,
            result=result,
            parsed=parsed,
            quality_score=aggregate,
        )
        if completion is None:
            return False
        await _publish_repository_event(repository, run_id, publisher)
        if raw_dispatch is not None:
            for raw_item_id in completion.raw_item_ids:
                try:
                    raw_dispatch(str(raw_item_id), correlation_id or str(raw_item_id))
                except Exception:
                    get_logger().warning(
                        "cleaning_queue_unavailable",
                        message="Cleaning queue is temporarily unavailable",
                        raw_item_id=str(raw_item_id),
                        correlation_id=correlation_id,
                        error_code="analysis_queue_unavailable",
                    )
        get_logger().info(
            "collection_completed",
            message="Collection run completed",
            run_id=str(run_id),
            source_id=str(source.id),
            correlation_id=correlation_id,
            task_id=task_id,
            status=completion.status,
            fetched_count=completion.fetched_count,
            created_count=completion.created_count,
            duplicate_count=completion.duplicate_count,
            failed_count=completion.failed_count,
            retry_count=retries,
            duration_ms=round((time.monotonic() - started) * 1000),
        )
        return True
    except CollectionError as exc:
        retries = exc.retry_count
        updated = await repository.finish_failure(
            claimed,
            backend_name=backend_name.value,
            attempt_started_at=attempt_started_at,
            retries=retries,
            error_code=exc.code,
            safe_error=exc.safe_message,
        )
        await _publish_repository_event(repository, run_id, publisher)
        if not updated:
            return False
        get_logger().warning(
            "collection_failed",
            message=exc.safe_message,
            run_id=str(run_id),
            source_id=str(source.id),
            correlation_id=correlation_id,
            task_id=task_id,
            status="failed",
            error_code=exc.code,
            fetched_count=0,
            created_count=0,
            duplicate_count=0,
            failed_count=1,
            retry_count=retries,
            duration_ms=round((time.monotonic() - started) * 1000),
        )
        return False
    except Exception:
        error = CollectionError("internal_collection_error", "Collection failed unexpectedly")
        updated = await repository.finish_failure(
            claimed,
            backend_name=backend_name.value,
            attempt_started_at=attempt_started_at,
            retries=retries,
            error_code=error.code,
            safe_error=error.safe_message,
        )
        await _publish_repository_event(repository, run_id, publisher)
        if not updated:
            return False
        get_logger().error(
            "collection_failed",
            message=error.safe_message,
            run_id=str(run_id),
            source_id=str(source.id),
            correlation_id=correlation_id,
            task_id=task_id,
            status="failed",
            error_code=error.code,
            fetched_count=0,
            created_count=0,
            duplicate_count=0,
            failed_count=1,
            retry_count=retries,
            duration_ms=round((time.monotonic() - started) * 1000),
        )
        return False
    finally:
        heartbeat_task.cancel()
        with suppress(asyncio.CancelledError):
            await heartbeat_task
