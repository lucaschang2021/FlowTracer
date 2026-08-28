from __future__ import annotations

import asyncio

from redis.asyncio import Redis

from app.core.config import get_settings
from app.db.session import create_database_engine, create_session_factory
from app.services.events import RedisEventPublisher
from app.services.notifications import dispatch_notifications as dispatch_notification_facts
from app.tasks.celery_app import celery_app


async def _dispatch() -> int:
    settings = get_settings()
    engine = create_database_engine(settings)
    redis_client = Redis.from_url(settings.redis_url.get_secret_value(), decode_responses=True)
    try:
        return await dispatch_notification_facts(
            create_session_factory(engine), RedisEventPublisher(redis_client)
        )
    finally:
        await redis_client.aclose()
        await engine.dispose()


@celery_app.task(name="flowtracer.tasks.notifications.dispatch_notifications")  # type: ignore[untyped-decorator]
def dispatch_notifications() -> int:
    return int(asyncio.run(_dispatch()))
