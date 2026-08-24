from __future__ import annotations

from uuid import uuid4

from app.tasks.health import ping


def test_celery_health_task() -> None:
    correlation_id = str(uuid4())
    result = ping.apply(kwargs={"correlation_id": correlation_id})

    assert result.successful()
    assert result.get() == {"status": "ok", "correlation_id": correlation_id}
