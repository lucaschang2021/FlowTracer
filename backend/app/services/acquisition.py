from __future__ import annotations

import hashlib
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import AppError
from app.core.logging import get_logger
from app.models.entities import (
    CollectionRun,
    CollectionRunStatus,
    CollectionTriggerType,
    RawItem,
    RawItemStatus,
    ResourceStatus,
    Source,
    SourceType,
)
from app.services.acquisition_parsers import parse_feed, parse_html
from app.services.acquisition_types import CollectionError
from app.services.resources import get_source, resource_not_found
from app.services.safe_fetcher import SafeFetcher, fetch_with_retries

Dispatch = Callable[[str, str], None]


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
    factory: async_sessionmaker[AsyncSession], *, batch_size: int = 100, now: datetime | None = None
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
        created = 0
        for source in sources:
            key = f"schedule:{bucket}"
            existing = await session.scalar(
                select(CollectionRun.id).where(
                    CollectionRun.source_id == source.id,
                    CollectionRun.idempotency_key == key,
                )
            )
            if existing is None:
                session.add(
                    CollectionRun(
                        source_id=source.id,
                        trigger_type=CollectionTriggerType.SCHEDULE,
                        status=CollectionRunStatus.QUEUED,
                        idempotency_key=key,
                    )
                )
                created += 1
            source.next_fetch_at = current + timedelta(minutes=source.poll_interval_minutes)
        await session.commit()
        return created


async def dispatch_queued_runs(
    factory: async_sessionmaker[AsyncSession], dispatch: Dispatch, *, batch_size: int = 100
) -> int:
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


async def _claim_run(factory: async_sessionmaker[AsyncSession], run_id: UUID) -> Source | None:
    async with factory() as session:
        run = await session.scalar(
            select(CollectionRun).where(CollectionRun.id == run_id).with_for_update()
        )
        if run is None or run.status != CollectionRunStatus.QUEUED:
            await session.rollback()
            return None
        source = await session.get(Source, run.source_id)
        if source is None or source.deleted_at is not None or source.source_type == SourceType.API:
            run.status = CollectionRunStatus.FAILED
            run.finished_at = datetime.now(UTC)
            run.failed_count = 1
            run.error_code = "internal_collection_error"
            run.error_message = "Source is unavailable"
            await session.commit()
            return None
        run.status = CollectionRunStatus.RUNNING
        run.started_at = datetime.now(UTC)
        run.error_code = None
        run.error_message = None
        await session.commit()
        session.expunge(source)
        return source


async def _finish_failure(
    factory: async_sessionmaker[AsyncSession], run_id: UUID, error: CollectionError
) -> None:
    async with factory() as session:
        run = await session.get(CollectionRun, run_id)
        if run is None or run.status != CollectionRunStatus.RUNNING:
            return
        run.status = CollectionRunStatus.FAILED
        run.finished_at = datetime.now(UTC)
        run.failed_count = 1
        run.error_code = error.code
        run.error_message = error.safe_message
        await session.commit()


async def execute_run(
    factory: async_sessionmaker[AsyncSession],
    run_id: UUID,
    *,
    fetcher: SafeFetcher | None = None,
    correlation_id: str | None = None,
    task_id: str | None = None,
) -> bool:
    started = time.monotonic()
    source = await _claim_run(factory, run_id)
    if source is None:
        return False
    retries = 0
    try:
        response, retries = await fetch_with_retries(
            fetcher or SafeFetcher(), source.normalized_url, source.source_type
        )
        parsed = (
            parse_feed(response)
            if source.source_type == SourceType.RSS
            else parse_html(response, source.normalized_url)
        )
        async with factory() as session:
            locked_source = await session.scalar(
                select(Source).where(Source.id == source.id).with_for_update()
            )
            run = await session.get(CollectionRun, run_id)
            if locked_source is None or run is None or run.status != CollectionRunStatus.RUNNING:
                await session.rollback()
                return False
            created = 0
            duplicates = 0
            for candidate in parsed.candidates:
                content_hash = hashlib.sha256(candidate.raw_text.encode("utf-8")).hexdigest()
                dedupe_predicates = [RawItem.external_id == candidate.external_id]
                if candidate.dedupe_by_canonical:
                    dedupe_predicates.append(RawItem.canonical_url == candidate.canonical_url)
                dedupe_predicates.append(RawItem.content_hash == content_hash)
                duplicate = await session.scalar(
                    select(RawItem.id).where(
                        RawItem.source_id == source.id,
                        or_(*dedupe_predicates),
                    )
                )
                if duplicate is not None:
                    duplicates += 1
                    continue
                session.add(
                    RawItem(
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
                )
                created += 1
            run.fetched_count = parsed.fetched_count
            run.created_count = created
            run.duplicate_count = duplicates
            run.failed_count = parsed.failed_count
            run.status = (
                CollectionRunStatus.PARTIAL
                if parsed.failed_count
                else CollectionRunStatus.SUCCEEDED
            )
            run.finished_at = datetime.now(UTC)
            run.error_code = None
            run.error_message = None
            locked_source.last_fetched_at = run.finished_at
            await session.commit()
        get_logger().info(
            "collection_completed",
            message="Collection run completed",
            run_id=str(run_id),
            source_id=str(source.id),
            correlation_id=correlation_id,
            task_id=task_id,
            status=run.status.value,
            fetched_count=parsed.fetched_count,
            created_count=created,
            duplicate_count=duplicates,
            failed_count=parsed.failed_count,
            retry_count=retries,
            duration_ms=round((time.monotonic() - started) * 1000),
        )
        return True
    except CollectionError as exc:
        await _finish_failure(factory, run_id, exc)
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
        await _finish_failure(factory, run_id, error)
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
