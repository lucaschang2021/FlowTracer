from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import delete, exists, func, literal, or_, select, text, true
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.errors import AppError
from app.core.logging import get_logger
from app.domains.provider_ports import (
    MAX_EMBEDDING_BATCH,
    EmbeddingError,
    EmbeddingProvider,
    EmbeddingResponse,
    normalize_vector,
)
from app.models.entities import (
    AIUsageRecord,
    Analysis,
    AnalysisStatus,
    Bookmark,
    Document,
    DocumentChunk,
    DocumentStatus,
    Radar,
    RawItem,
    Source,
)
from app.services.chunking import chunk_text

EMBEDDING_BUDGET_SECONDS = 90.0


def _advisory_key(document_id: UUID) -> int:
    return int.from_bytes(document_id.bytes[:8], "big", signed=True)


def calculate_embedding_cost(input_tokens: int, settings: Settings) -> Decimal:
    value = Decimal(input_tokens) * settings.embedding_input_cost_per_million / Decimal(1_000_000)
    return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


async def _record_usage(
    factory: async_sessionmaker[AsyncSession],
    *,
    user_id: UUID,
    provider: EmbeddingProvider,
    settings: Settings,
    task_type: str,
    response: EmbeddingResponse | None,
    duration_ms: int,
    succeeded: bool,
    error_code: str | None,
) -> None:
    usage = response.usage if response else None
    input_tokens = usage.input_tokens if usage else 0
    total_tokens = usage.total_tokens if usage else 0
    async with factory() as session:
        session.add(
            AIUsageRecord(
                user_id=user_id,
                analysis_id=None,
                task_type=task_type,
                provider=provider.name,
                model=provider.model,
                input_tokens=input_tokens,
                output_tokens=0,
                total_tokens=total_tokens,
                estimated_cost=calculate_embedding_cost(input_tokens, settings),
                duration_ms=max(0, duration_ms),
                succeeded=succeeded,
                error_code=error_code,
            )
        )
        await session.commit()


async def _embed_with_audit(
    factory: async_sessionmaker[AsyncSession],
    *,
    user_id: UUID,
    provider: EmbeddingProvider,
    settings: Settings,
    task_type: str,
    inputs: list[str],
    started: float,
    sleep: Callable[[float], Awaitable[None]],
) -> EmbeddingResponse:
    last_error = EmbeddingError(
        "embedding_failed", "Embedding failed unexpectedly", retryable=False
    )
    for attempt in range(1, 4):
        remaining = EMBEDDING_BUDGET_SECONDS - (time.monotonic() - started)
        if remaining <= 0:
            last_error = EmbeddingError(
                "embedding_timeout", "Embedding request timed out", retryable=False
            )
            break
        call_started = time.monotonic()
        response: EmbeddingResponse | None = None
        try:
            response = await asyncio.wait_for(provider.embed(inputs), timeout=remaining)
            if len(response.vectors) != len(inputs):
                raise EmbeddingError(
                    "embedding_invalid_output",
                    "Embedding returned invalid output",
                    retryable=False,
                )
            response = EmbeddingResponse(
                tuple(normalize_vector(vector) for vector in response.vectors),
                response.usage,
            )
        except TimeoutError:
            error = EmbeddingError(
                "embedding_timeout", "Embedding request timed out", retryable=True
            )
        except EmbeddingError as exc:
            error = exc
        except Exception:
            error = EmbeddingError(
                "embedding_failed", "Embedding failed unexpectedly", retryable=False
            )
        else:
            await _record_usage(
                factory,
                user_id=user_id,
                provider=provider,
                settings=settings,
                task_type=task_type,
                response=response,
                duration_ms=round((time.monotonic() - call_started) * 1000),
                succeeded=True,
                error_code=None,
            )
            return response
        await _record_usage(
            factory,
            user_id=user_id,
            provider=provider,
            settings=settings,
            task_type=task_type,
            response=response,
            duration_ms=round((time.monotonic() - call_started) * 1000),
            succeeded=False,
            error_code=error.code,
        )
        last_error = error
        if error.retryable and attempt < 3:
            delay = 2.0 if attempt == 1 else 4.0
            if time.monotonic() - started + delay < EMBEDDING_BUDGET_SECONDS:
                await sleep(delay)
                continue
        break
    raise last_error


async def run_embedding(
    factory: async_sessionmaker[AsyncSession],
    document_id: UUID,
    provider: EmbeddingProvider,
    settings: Settings,
    *,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> bool:
    bind = factory.kw.get("bind")
    if not isinstance(bind, AsyncEngine):
        raise RuntimeError("Embedding session factory requires an AsyncEngine bind")
    connection = await bind.connect()
    session = AsyncSession(bind=connection, expire_on_commit=False)
    locked = False
    try:
        await session.execute(
            text("SELECT pg_advisory_lock(:key)"), {"key": _advisory_key(document_id)}
        )
        locked = True
        await session.commit()
        row = (
            await session.execute(
                select(Document, Source.user_id)
                .join(RawItem, RawItem.id == Document.raw_item_id)
                .join(Source, Source.id == RawItem.source_id)
                .where(Document.id == document_id)
                .with_for_update(of=Document)
            )
        ).one_or_none()
        if row is None or row.Document.status != DocumentStatus.EMBEDDING:
            await session.rollback()
            return False
        document = row.Document
        chunks = chunk_text(
            document.content,
            size=settings.embedding_chunk_size,
            overlap=settings.embedding_chunk_overlap,
        )
        if not chunks:
            raise EmbeddingError(
                "embedding_invalid_output",
                "Document content cannot be embedded",
                retryable=False,
            )
        all_existing = list(
            (
                await session.scalars(
                    select(DocumentChunk)
                    .where(DocumentChunk.document_id == document_id)
                    .order_by(DocumentChunk.embedding_model, DocumentChunk.chunk_index)
                )
            ).all()
        )
        existing = list(chunk for chunk in all_existing if chunk.embedding_model == provider.model)
        if len(existing) == len(chunks) and all(
            saved.chunk_index == expected.index and saved.content == expected.content
            for saved, expected in zip(existing, chunks, strict=True)
        ):
            if len(all_existing) != len(existing):
                await session.execute(
                    delete(DocumentChunk).where(
                        DocumentChunk.document_id == document_id,
                        DocumentChunk.embedding_model != provider.model,
                    )
                )
            document.status = DocumentStatus.READY
            document.error_code = None
            document.error_message = None
            await session.commit()
            return True
        user_id = row.user_id
        await session.commit()

        started = time.monotonic()
        vectors: list[tuple[float, ...]] = []
        for offset in range(0, len(chunks), MAX_EMBEDDING_BATCH):
            batch = chunks[offset : offset + MAX_EMBEDDING_BATCH]
            response = await _embed_with_audit(
                factory,
                user_id=user_id,
                provider=provider,
                settings=settings,
                task_type="embedding",
                inputs=[chunk.content for chunk in batch],
                started=started,
                sleep=sleep,
            )
            vectors.extend(response.vectors)

        document = await session.scalar(
            select(Document).where(Document.id == document_id).with_for_update()
        )
        if document is None or document.status != DocumentStatus.EMBEDDING:
            await session.rollback()
            return False
        await session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
        session.add_all(
            [
                DocumentChunk(
                    document_id=document_id,
                    chunk_index=chunk.index,
                    content=chunk.content,
                    embedding=list(vector),
                    embedding_model=provider.model,
                )
                for chunk, vector in zip(chunks, vectors, strict=True)
            ]
        )
        document.status = DocumentStatus.READY
        document.error_code = None
        document.error_message = None
        await session.commit()
        get_logger().info(
            "embedding_completed",
            message="Document embedding completed",
            document_id=str(document_id),
            provider=provider.name,
            model=provider.model,
            chunk_count=len(chunks),
        )
        return True
    except EmbeddingError as exc:
        await session.rollback()
        document = await session.scalar(
            select(Document).where(Document.id == document_id).with_for_update()
        )
        if document is not None and document.status == DocumentStatus.EMBEDDING:
            document.status = DocumentStatus.FAILED
            document.error_code = exc.code
            document.error_message = exc.safe_message
            await session.commit()
        get_logger().warning(
            "embedding_failed",
            message=exc.safe_message,
            document_id=str(document_id),
            provider=provider.name,
            model=provider.model,
            error_code=exc.code,
        )
        return False
    finally:
        if locked:
            try:
                await session.rollback()
                await session.execute(
                    text("SELECT pg_advisory_unlock(:key)"), {"key": _advisory_key(document_id)}
                )
                await session.commit()
            except Exception:
                await session.rollback()
        await session.close()
        await connection.close()


async def dispatch_embedding_documents(
    factory: async_sessionmaker[AsyncSession],
    dispatch: Callable[[str, str], None],
    *,
    batch_size: int = 100,
) -> int:
    async with factory() as session:
        document_ids = list(
            (
                await session.scalars(
                    select(Document.id)
                    .where(Document.status == DocumentStatus.EMBEDDING)
                    .order_by(Document.updated_at.asc(), Document.id.asc())
                    .with_for_update(skip_locked=True)
                    .limit(batch_size)
                )
            ).all()
        )
        dispatched = 0
        for document_id in document_ids:
            try:
                dispatch(str(document_id), str(document_id))
            except Exception as exc:
                get_logger().warning(
                    "embedding_queue_unavailable",
                    message="Embedding queue is temporarily unavailable",
                    document_id=str(document_id),
                    exception_type=type(exc).__name__,
                )
                continue
            dispatched += 1
        await session.commit()
        return dispatched


def _resource_not_found() -> AppError:
    return AppError(status_code=404, code="resource_not_found", message="Resource not found")


def _constraint_name(exc: IntegrityError) -> str | None:
    for candidate in (exc.orig, getattr(exc.orig, "__cause__", None)):
        name = getattr(candidate, "constraint_name", None)
        if isinstance(name, str):
            return name
        diagnostic = getattr(candidate, "diag", None)
        name = getattr(diagnostic, "constraint_name", None)
        if isinstance(name, str):
            return name
    return None


def _bookmark_access(user_id: UUID, document_id: UUID) -> Any:
    return exists(
        select(Analysis.id)
        .join(Radar, Radar.id == Analysis.radar_id)
        .where(
            Analysis.document_id == document_id,
            Analysis.status == AnalysisStatus.COMPLETED,
            Radar.user_id == user_id,
            Radar.deleted_at.is_(None),
        )
    )


async def create_bookmark(
    session: AsyncSession, *, user_id: UUID, document_id: UUID, note: str | None
) -> Bookmark:
    allowed = await session.scalar(select(_bookmark_access(user_id, document_id)))
    if not allowed:
        await session.rollback()
        raise _resource_not_found()
    bookmark = Bookmark(user_id=user_id, document_id=document_id, note=note)
    session.add(bookmark)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        if _constraint_name(exc) == "bookmarks_user_id_document_id_key":
            raise AppError(
                status_code=409, code="bookmark_exists", message="Bookmark already exists"
            ) from None
        raise
    await session.refresh(bookmark)
    return bookmark


async def get_owned_bookmark(
    session: AsyncSession, *, user_id: UUID, bookmark_id: UUID, for_update: bool = False
) -> Bookmark:
    statement = select(Bookmark).where(Bookmark.id == bookmark_id, Bookmark.user_id == user_id)
    if for_update:
        statement = statement.with_for_update()
    bookmark = await session.scalar(statement)
    if bookmark is None:
        raise _resource_not_found()
    return bookmark


async def update_bookmark(
    session: AsyncSession, *, user_id: UUID, bookmark_id: UUID, note: str | None
) -> Bookmark:
    bookmark = await get_owned_bookmark(
        session, user_id=user_id, bookmark_id=bookmark_id, for_update=True
    )
    bookmark.note = note
    await session.commit()
    await session.refresh(bookmark)
    return bookmark


async def delete_bookmark(session: AsyncSession, *, user_id: UUID, bookmark_id: UUID) -> None:
    bookmark = await get_owned_bookmark(
        session, user_id=user_id, bookmark_id=bookmark_id, for_update=True
    )
    await session.delete(bookmark)
    await session.commit()


async def bookmark_data(session: AsyncSession, bookmark: Bookmark) -> dict[str, Any]:
    document = await session.get(Document, bookmark.document_id)
    if document is None:
        raise _resource_not_found()
    analysis = (
        await session.scalars(
            select(Analysis)
            .join(Radar, Radar.id == Analysis.radar_id)
            .where(
                Analysis.document_id == document.id,
                Analysis.status == AnalysisStatus.COMPLETED,
                Radar.user_id == bookmark.user_id,
            )
            .order_by(Analysis.created_at.desc(), Analysis.id.desc())
            .limit(1)
        )
    ).first()
    return {
        "id": bookmark.id,
        "document_id": document.id,
        "note": bookmark.note,
        "title": document.title,
        "canonical_url": document.canonical_url,
        "analysis_id": analysis.id if analysis else None,
        "radar_id": analysis.radar_id if analysis else None,
        "summary": analysis.summary if analysis else None,
        "category": analysis.category if analysis else None,
        "radar_score": analysis.radar_score if analysis else None,
        "recommendation": analysis.recommendation if analysis else None,
        "created_at": bookmark.created_at,
        "updated_at": bookmark.updated_at,
    }


async def list_bookmarks(
    session: AsyncSession, *, user_id: UUID, page: int, page_size: int
) -> tuple[list[dict[str, Any]], int]:
    total = int(
        await session.scalar(
            select(func.count()).select_from(Bookmark).where(Bookmark.user_id == user_id)
        )
        or 0
    )
    bookmarks = list(
        (
            await session.scalars(
                select(Bookmark)
                .where(Bookmark.user_id == user_id)
                .order_by(Bookmark.created_at.desc(), Bookmark.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    return [await bookmark_data(session, bookmark) for bookmark in bookmarks], total


def _provider_error(error: EmbeddingError) -> AppError:
    if error.code in {
        "embedding_timeout",
        "embedding_rate_limited",
        "embedding_provider_unavailable",
        "embedding_auth_failed",
    }:
        return AppError(status_code=503, code=error.code, message=error.safe_message)
    return AppError(status_code=502, code=error.code, message=error.safe_message)


async def search_memory(
    factory: async_sessionmaker[AsyncSession],
    *,
    user_id: UUID,
    query: str,
    top_k: int,
    radar_id: UUID | None,
    date_from: datetime | None,
    date_to: datetime | None,
    bookmarked_only: bool,
    provider: EmbeddingProvider,
    settings: Settings,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> list[dict[str, Any]]:
    async with factory() as session:
        if radar_id is not None:
            owned = await session.scalar(
                select(Radar.id).where(
                    Radar.id == radar_id,
                    Radar.user_id == user_id,
                    Radar.deleted_at.is_(None),
                )
            )
            await session.rollback()
            if owned is None:
                raise _resource_not_found()
        try:
            response = await _embed_with_audit(
                factory,
                user_id=user_id,
                provider=provider,
                settings=settings,
                task_type="memory_search",
                inputs=[query],
                started=time.monotonic(),
                sleep=sleep,
            )
        except EmbeddingError as exc:
            raise _provider_error(exc) from None

        vector = list(response.vectors[0])
        distance = DocumentChunk.embedding.cosine_distance(vector)
        matched = (
            select(
                DocumentChunk.content.label("excerpt"),
                distance.label("distance"),
            )
            .where(
                DocumentChunk.document_id == Document.id,
                DocumentChunk.embedding_model == provider.model,
            )
            .order_by(distance.asc(), DocumentChunk.chunk_index.asc())
            .limit(1)
            .lateral("matched_chunk")
        )
        bookmark_exists = exists(
            select(Bookmark.id).where(
                Bookmark.user_id == user_id,
                Bookmark.document_id == Document.id,
            )
        )
        occurred_at = func.coalesce(RawItem.published_at, Document.created_at)
        conditions: list[Any] = [
            Analysis.status == AnalysisStatus.COMPLETED,
            Document.status == DocumentStatus.READY,
            Radar.user_id == user_id,
        ]
        if radar_id is not None:
            conditions.extend([Analysis.radar_id == radar_id, Radar.deleted_at.is_(None)])
        if bookmarked_only:
            conditions.append(bookmark_exists)
        elif radar_id is None:
            conditions.append(or_(Radar.deleted_at.is_(None), bookmark_exists))
        if date_from is not None:
            conditions.append(occurred_at >= date_from)
        if date_to is not None:
            conditions.append(occurred_at <= date_to)
        similarity = func.greatest(literal(0.0), literal(1.0) - matched.c.distance)
        rows = (
            await session.execute(
                select(
                    Analysis,
                    Document,
                    occurred_at.label("occurred_at"),
                    matched.c.excerpt,
                    similarity.label("similarity"),
                    bookmark_exists.label("bookmarked"),
                )
                .join(Document, Document.id == Analysis.document_id)
                .join(RawItem, RawItem.id == Document.raw_item_id)
                .join(Radar, Radar.id == Analysis.radar_id)
                .join(matched, true())
                .where(*conditions)
                .order_by(similarity.desc(), Analysis.created_at.desc(), Analysis.id.desc())
                .limit(top_k)
            )
        ).all()
        return [
            {
                "analysis_id": row.Analysis.id,
                "document_id": row.Document.id,
                "radar_id": row.Analysis.radar_id,
                "title": row.Document.title,
                "canonical_url": row.Document.canonical_url,
                "summary": row.Analysis.summary,
                "category": row.Analysis.category,
                "radar_score": row.Analysis.radar_score,
                "recommendation": row.Analysis.recommendation,
                "excerpt": row.excerpt,
                "similarity": Decimal(str(row.similarity)).quantize(
                    Decimal("0.000001"), rounding=ROUND_HALF_UP
                ),
                "occurred_at": row.occurred_at,
                "bookmarked": row.bookmarked,
            }
            for row in rows
        ]
