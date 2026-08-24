from __future__ import annotations

from typing import Any

from app.core.context import bind_context, reset_context
from app.core.logging import get_logger
from app.tasks.celery_app import celery_app


@celery_app.task(bind=True, name="flowtracer.tasks.health.ping")  # type: ignore[untyped-decorator]
def ping(self: Any, correlation_id: str | None = None) -> dict[str, str]:
    resolved_correlation_id = correlation_id or str(self.request.id)
    tokens = bind_context(
        request_id=resolved_correlation_id,
        correlation_id=resolved_correlation_id,
    )
    try:
        get_logger().info(
            "celery_health_ping",
            message="Celery health task completed",
            task_name=self.name,
            task_id=str(self.request.id),
            attempt=int(self.request.retries),
        )
        return {"status": "ok", "correlation_id": resolved_correlation_id}
    finally:
        reset_context(tokens)
