from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from redis.asyncio import Redis

from app.core.logging import get_logger
from app.domains.acquisition_ports import EventPublisher as EventPublisherPort
from app.schemas.events import EventEnvelope

EVENT_CHANNEL_PREFIX = "flowtracer:events"


type EventPublisher = EventPublisherPort[EventEnvelope]


class RedisEventPublisher:
    def __init__(self, redis_client: Redis) -> None:
        self._redis = redis_client

    async def publish(self, user_id: UUID, event: EventEnvelope) -> None:
        await self._redis.publish(channel_for_user(user_id), event.model_dump_json())


def channel_for_user(user_id: UUID) -> str:
    return f"{EVENT_CHANNEL_PREFIX}:{user_id}"


def build_event(
    event_type: str,
    resource_id: UUID,
    version: str,
    data: Mapping[str, Any],
    *,
    occurred_at: datetime | None = None,
) -> EventEnvelope:
    timestamp = occurred_at or datetime.now(UTC)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("event timestamp must be timezone-aware")
    return EventEnvelope.model_validate(
        {
            "event_id": uuid5(NAMESPACE_URL, f"flowtracer:{event_type}:{resource_id}:{version}"),
            "event_type": event_type,
            "occurred_at": timestamp.astimezone(UTC),
            "data": dict(data),
        }
    )


async def publish_safely(
    publisher: EventPublisher | None,
    *,
    user_id: UUID,
    event: EventEnvelope,
    resource_id: UUID,
) -> bool:
    if publisher is None:
        return False
    try:
        await publisher.publish(user_id, event)
    except Exception as exc:
        get_logger().warning(
            "event_publish_failed",
            message="Online event publication failed",
            event_type=event.event_type,
            resource_id=str(resource_id),
            exception_type=type(exc).__name__,
        )
        return False
    return True
