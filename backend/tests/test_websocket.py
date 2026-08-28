from __future__ import annotations

import asyncio
import os
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from redis import Redis as SyncRedis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from starlette.websockets import WebSocketDisconnect

from app.api.v1.routes.websocket import WEBSOCKET_QUEUE_LIMIT, enqueue_event
from app.core.config import Settings
from app.core.security import create_access_token
from app.main import create_app
from app.models.entities import User
from app.services.events import build_event, channel_for_user

TABLES = (
    "notifications, ai_usage_records, document_chunks, bookmarks, analyses, documents, "
    "raw_items, radar_sources, collection_runs, sources, radars, refresh_tokens, users"
)


async def seed_users() -> tuple[UUID, UUID, UUID, UUID]:
    database_url = os.environ["TEST_DATABASE_URL"]
    assert "_test" in database_url.rsplit("/", maxsplit=1)[-1]
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    async with AsyncSession(engine, expire_on_commit=False) as session:
        owner = User(
            email=f"ws-owner-{uuid4()}@example.com",
            password_hash="synthetic",  # noqa: S106 - inert fixture
            display_name="Owner",
            profile={},
        )
        stranger = User(
            email=f"ws-stranger-{uuid4()}@example.com",
            password_hash="synthetic",  # noqa: S106 - inert fixture
            display_name="Stranger",
            profile={},
        )
        disabled = User(
            email=f"ws-disabled-{uuid4()}@example.com",
            password_hash="synthetic",  # noqa: S106 - inert fixture
            display_name="Disabled",
            profile={},
            is_active=False,
        )
        deleted = User(
            email=f"ws-deleted-{uuid4()}@example.com",
            password_hash="synthetic",  # noqa: S106 - inert fixture
            display_name="Deleted",
            profile={},
            deleted_at=datetime.now(UTC),
        )
        session.add_all([owner, stranger, disabled, deleted])
        await session.commit()
        result = (owner.id, stranger.id, disabled.id, deleted.id)
    await engine.dispose()
    return result


def assert_ws_close(client: TestClient, url: str, *, headers: dict[str, str] | None = None) -> int:
    with client.websocket_connect(url, headers=headers or {}) as websocket:
        with pytest.raises(WebSocketDisconnect) as closed:
            websocket.receive_json()
    return closed.value.code


def test_websocket_header_auth_user_state_and_token_expiry() -> None:
    owner_id, _stranger_id, disabled_id, deleted_id = asyncio.run(seed_users())
    settings = Settings()
    app = create_app(settings)
    owner_token = create_access_token(owner_id, settings)
    with TestClient(app) as client:
        assert assert_ws_close(client, "/api/v1/ws") == 4401
        assert assert_ws_close(client, f"/api/v1/ws?token={owner_token}") == 4401
        client.cookies.set("access_token", owner_token)
        assert assert_ws_close(client, "/api/v1/ws") == 4401
        client.cookies.clear()
        assert (
            assert_ws_close(client, "/api/v1/ws", headers={"Authorization": "Bearer invalid-token"})
            == 4401
        )
        for user_id in (disabled_id, deleted_id):
            assert (
                assert_ws_close(
                    client,
                    "/api/v1/ws",
                    headers={"Authorization": f"Bearer {create_access_token(user_id, settings)}"},
                )
                == 4401
            )
        expiring = create_access_token(
            owner_id,
            settings,
            now=datetime.now(UTC)
            - timedelta(minutes=settings.access_token_ttl_minutes)
            + timedelta(seconds=2),
        )
        started = time.monotonic()
        assert (
            assert_ws_close(client, "/api/v1/ws", headers={"Authorization": f"Bearer {expiring}"})
            == 4401
        )
        assert time.monotonic() - started < 4


def test_websocket_real_redis_user_isolation_and_multiple_connections() -> None:
    owner_id, stranger_id, _disabled_id, _deleted_id = asyncio.run(seed_users())
    settings = Settings()
    app = create_app(settings)
    owner_headers = {"Authorization": f"Bearer {create_access_token(owner_id, settings)}"}
    stranger_headers = {"Authorization": f"Bearer {create_access_token(stranger_id, settings)}"}
    redis_client = SyncRedis.from_url(settings.redis_url.get_secret_value(), decode_responses=True)
    redis_client.flushdb()
    owner_resource = uuid4()
    stranger_resource = uuid4()
    owner_event = build_event(
        "analysis.completed",
        owner_resource,
        "completed:v1",
        {
            "analysis_id": owner_resource,
            "document_id": uuid4(),
            "radar_id": uuid4(),
            "radar_score": Decimal("95.00"),
            "recommendation": "must_read",
        },
    )
    stranger_event = build_event(
        "notification.created",
        stranger_resource,
        "created:v1",
        {
            "notification_id": stranger_resource,
            "analysis_id": uuid4(),
            "priority": "high",
        },
    )
    with TestClient(app) as client:
        with (
            client.websocket_connect("/api/v1/ws", headers=owner_headers) as owner_one,
            client.websocket_connect("/api/v1/ws", headers=owner_headers) as owner_two,
            client.websocket_connect("/api/v1/ws", headers=stranger_headers) as stranger,
        ):
            time.sleep(0.1)
            redis_client.publish(channel_for_user(owner_id), owner_event.model_dump_json())
            redis_client.publish(channel_for_user(stranger_id), stranger_event.model_dump_json())
            assert owner_one.receive_json()["event_id"] == str(owner_event.event_id)
            assert owner_two.receive_json()["event_id"] == str(owner_event.event_id)
            received_by_stranger = stranger.receive_json()
            assert received_by_stranger["event_id"] == str(stranger_event.event_id)
            assert received_by_stranger["event_id"] != str(owner_event.event_id)
    redis_client.close()


class BrokenPubSub:
    async def subscribe(self, _channel: str) -> None:
        raise RedisError("redis-secret")

    async def aclose(self) -> None:
        return None


class BrokenRedis:
    def pubsub(self) -> BrokenPubSub:
        return BrokenPubSub()


def test_websocket_redis_failure_backpressure_and_strict_event_schemas() -> None:
    owner_id, _stranger_id, _disabled_id, _deleted_id = asyncio.run(seed_users())
    settings = Settings()
    app = create_app(settings)
    headers = {"Authorization": f"Bearer {create_access_token(owner_id, settings)}"}
    with TestClient(app) as client:
        real_redis = app.state.redis_client
        app.state.redis_client = BrokenRedis()
        assert assert_ws_close(client, "/api/v1/ws", headers=headers) == 1013
        app.state.redis_client = real_redis

    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=WEBSOCKET_QUEUE_LIMIT)
    for index in range(WEBSOCKET_QUEUE_LIMIT):
        enqueue_event(queue, str(index))
    with pytest.raises(RuntimeError):
        enqueue_event(queue, "overflow")

    resource_id = uuid4()
    collection = build_event(
        "collection.updated",
        resource_id,
        "queued:v1",
        {
            "collection_run_id": resource_id,
            "source_id": uuid4(),
            "status": "queued",
            "fetched_count": 0,
            "created_count": 0,
            "duplicate_count": 0,
            "failed_count": 0,
        },
    )
    replay = build_event(
        "collection.updated",
        resource_id,
        "queued:v1",
        collection.data.model_dump(),
        occurred_at=collection.occurred_at,
    )
    assert collection.event_id == replay.event_id
    assert collection.occurred_at.tzinfo is not None
    assert set(collection.model_dump()) == {"event_id", "event_type", "occurred_at", "data"}
    assert set(collection.data.model_dump()) == {
        "collection_run_id",
        "source_id",
        "status",
        "fetched_count",
        "created_count",
        "duplicate_count",
        "failed_count",
    }
