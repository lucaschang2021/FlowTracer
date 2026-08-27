from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from app.core.config import get_settings
from app.core.context import bind_context, reset_context
from app.core.logging import get_logger
from app.db.session import create_database_engine, create_session_factory
from app.providers.analysis import build_provider
from app.services.cleaning import clean_raw_item, dispatch_fetched_raw_items
from app.services.intelligence import (
    dispatch_pending_analyses,
    recover_stale_analyses,
    run_analysis,
)
from app.tasks.celery_app import celery_app


async def _with_database(operation: Any) -> Any:
    engine = create_database_engine(get_settings())
    try:
        return await operation(create_session_factory(engine))
    finally:
        await engine.dispose()


def enqueue_raw_item(raw_item_id: str, correlation_id: str) -> None:
    process_raw_item.apply_async(args=[raw_item_id], kwargs={"correlation_id": correlation_id})


def enqueue_analysis(analysis_id: str, correlation_id: str) -> None:
    analyze_document.apply_async(args=[analysis_id], kwargs={"correlation_id": correlation_id})


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
        provider = build_provider(settings)
        return bool(
            asyncio.run(
                _with_database(
                    lambda factory: run_analysis(factory, UUID(analysis_id), provider, settings)
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
