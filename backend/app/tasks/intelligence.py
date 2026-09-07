from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from app.core.composition import (
    build_analysis_dependency,
    build_embedding_dependency,
    with_database,
    with_events,
)
from app.core.config import get_settings
from app.core.context import bind_context, reset_context
from app.core.logging import get_logger
from app.services.cleaning import clean_raw_item, dispatch_fetched_raw_items
from app.services.intelligence import (
    dispatch_pending_analyses,
    publish_analysis_completed,
    recover_stale_analyses,
    run_analysis,
)
from app.services.memory import dispatch_embedding_documents, run_embedding
from app.services.notifications import dispatch_notifications
from app.tasks.celery_app import celery_app


async def _with_database(operation: Any) -> Any:
    return await with_database(get_settings(), operation)


async def _with_events(operation: Any) -> Any:
    return await with_events(get_settings(), operation)


def enqueue_raw_item(raw_item_id: str, correlation_id: str) -> None:
    process_raw_item.apply_async(args=[raw_item_id], kwargs={"correlation_id": correlation_id})


def enqueue_analysis(analysis_id: str, correlation_id: str) -> None:
    analyze_document.apply_async(args=[analysis_id], kwargs={"correlation_id": correlation_id})


def enqueue_embedding(document_id: str, correlation_id: str) -> None:
    embed_document.apply_async(args=[document_id], kwargs={"correlation_id": correlation_id})


@celery_app.task(bind=True, name="flowtracer.tasks.intelligence.process_raw_item")  # type: ignore[untyped-decorator]
def process_raw_item(self: Any, raw_item_id: str, correlation_id: str | None = None) -> bool:
    resolved = correlation_id or str(self.request.id)
    tokens = bind_context(request_id=resolved, correlation_id=resolved)
    try:

        async def process(factory: Any) -> bool:
            result = await clean_raw_item(factory, UUID(raw_item_id))
            for analysis_id in result.analysis_ids:
                try:
                    enqueue_analysis(str(analysis_id), resolved)
                except Exception as exc:
                    get_logger().warning(
                        "analysis_queue_unavailable",
                        message="Analysis queue is temporarily unavailable",
                        analysis_id=str(analysis_id),
                        exception_type=type(exc).__name__,
                    )
                    continue
            get_logger().info(
                "cleaning_completed",
                message="Raw item cleaning finished",
                raw_item_id=raw_item_id,
                document_id=str(result.document_id) if result.document_id else None,
                status="duplicate" if result.duplicate else "processed",
            )
            return result.document_id is not None

        return bool(asyncio.run(_with_database(process)))
    finally:
        reset_context(tokens)


@celery_app.task(
    bind=True,
    name="flowtracer.tasks.intelligence.analyze_document",
    soft_time_limit=120,
    time_limit=150,
)  # type: ignore[untyped-decorator]
def analyze_document(self: Any, analysis_id: str, correlation_id: str | None = None) -> bool:
    resolved = correlation_id or str(self.request.id)
    tokens = bind_context(request_id=resolved, correlation_id=resolved)
    try:
        settings = get_settings()
        provider = build_analysis_dependency(settings)

        async def analyze(factory: Any) -> bool:
            async def with_events(publisher: Any) -> bool:
                completed = await run_analysis(factory, UUID(analysis_id), provider, settings)
                if completed:
                    await publish_analysis_completed(factory, UUID(analysis_id), publisher)
                    await dispatch_notifications(factory, publisher, analysis_id=UUID(analysis_id))
                return completed

            return bool(await _with_events(with_events))

        return bool(asyncio.run(_with_database(analyze)))
    finally:
        reset_context(tokens)


@celery_app.task(
    bind=True,
    name="flowtracer.tasks.intelligence.embed_document",
    soft_time_limit=120,
    time_limit=150,
)  # type: ignore[untyped-decorator]
def embed_document(self: Any, document_id: str, correlation_id: str | None = None) -> bool:
    resolved = correlation_id or str(self.request.id)
    tokens = bind_context(request_id=resolved, correlation_id=resolved)
    try:
        settings = get_settings()
        provider = build_embedding_dependency(settings)
        return bool(
            asyncio.run(
                _with_database(
                    lambda factory: run_embedding(factory, UUID(document_id), provider, settings)
                )
            )
        )
    finally:
        reset_context(tokens)


@celery_app.task(name="flowtracer.tasks.intelligence.dispatch_fetched_raw_items")  # type: ignore[untyped-decorator]
def dispatch_raw_items() -> int:
    return int(
        asyncio.run(
            _with_database(lambda factory: dispatch_fetched_raw_items(factory, enqueue_raw_item))
        )
    )


@celery_app.task(name="flowtracer.tasks.intelligence.dispatch_pending_analyses")  # type: ignore[untyped-decorator]
def dispatch_analyses() -> int:
    return int(
        asyncio.run(
            _with_database(lambda factory: dispatch_pending_analyses(factory, enqueue_analysis))
        )
    )


@celery_app.task(name="flowtracer.tasks.intelligence.recover_stale_analyses")  # type: ignore[untyped-decorator]
def recover_analyses() -> int:
    return int(asyncio.run(_with_database(recover_stale_analyses)))


@celery_app.task(name="flowtracer.tasks.intelligence.dispatch_embedding_documents")  # type: ignore[untyped-decorator]
def dispatch_embeddings() -> int:
    return int(
        asyncio.run(
            _with_database(lambda factory: dispatch_embedding_documents(factory, enqueue_embedding))
        )
    )
