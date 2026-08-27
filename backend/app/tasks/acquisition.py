from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from app.core.config import get_settings
from app.core.context import bind_context, reset_context
from app.core.logging import get_logger
from app.db.session import create_database_engine, create_session_factory
from app.services.acquisition import dispatch_queued_runs, execute_run, schedule_due_sources
from app.tasks.celery_app import celery_app


def enqueue_collection(run_id: str, correlation_id: str) -> None:
    collect_source.apply_async(args=[run_id], kwargs={"correlation_id": correlation_id})


async def _with_database(operation: Any) -> Any:
    engine = create_database_engine(get_settings())
    try:
        return await operation(create_session_factory(engine))
    finally:
        await engine.dispose()


@celery_app.task(bind=True, name="flowtracer.tasks.acquisition.collect_source")  # type: ignore[untyped-decorator]
def collect_source(self: Any, run_id: str, correlation_id: str | None = None) -> bool:
    resolved_correlation_id = correlation_id or str(self.request.id)
    tokens = bind_context(
        request_id=resolved_correlation_id,
        correlation_id=resolved_correlation_id,
    )
    try:
        return bool(
            asyncio.run(
                _with_database(
                    lambda factory: execute_run(
                        factory,
                        UUID(run_id),
                        correlation_id=resolved_correlation_id,
                        task_id=str(self.request.id),
                    )
                )
            )
        )
    finally:
        reset_context(tokens)


@celery_app.task(name="flowtracer.tasks.acquisition.schedule_due_sources")  # type: ignore[untyped-decorator]
def schedule_sources() -> int:
    return int(asyncio.run(_with_database(schedule_due_sources)))


@celery_app.task(name="flowtracer.tasks.acquisition.dispatch_queued_runs")  # type: ignore[untyped-decorator]
def dispatch_runs() -> int:
    count = int(
        asyncio.run(
            _with_database(lambda factory: dispatch_queued_runs(factory, enqueue_collection))
        )
    )
    get_logger().info(
        "collection_dispatch_completed",
        message="Queued collection runs dispatched",
        dispatched_count=count,
    )
    return count
