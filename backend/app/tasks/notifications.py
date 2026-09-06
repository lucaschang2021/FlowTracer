from __future__ import annotations

import asyncio

from app.core.composition import invoke_with_runtime
from app.core.config import get_settings
from app.services.notifications import dispatch_notifications as dispatch_notification_facts
from app.tasks.celery_app import celery_app


async def _dispatch() -> int:
    settings = get_settings()
    return await invoke_with_runtime(settings, dispatch_notification_facts)


@celery_app.task(name="flowtracer.tasks.notifications.dispatch_notifications")  # type: ignore[untyped-decorator]
def dispatch_notifications() -> int:
    return int(asyncio.run(_dispatch()))
