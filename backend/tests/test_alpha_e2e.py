from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from redis import Redis as SyncRedis
from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings
from app.main import create_app
from app.models.entities import Analysis, Document, Notification, RawItem, SourceType
from app.providers.analysis import FakeAnalysisProvider
from app.providers.embedding import FakeEmbeddingProvider
from app.schemas.events import EventEnvelope
from app.services.acquisition import dispatch_queued_runs, execute_run
from app.services.acquisition_run_repository import SqlAlchemyAcquisitionRunRepository
from app.services.acquisition_types import FetchResponse
from app.services.cleaning import clean_raw_item
from app.services.events import channel_for_user
from app.services.intelligence import publish_analysis_completed, run_analysis
from app.services.memory import run_embedding
from app.services.native_acquisition import NativeAcquisitionBackend
from app.services.notifications import dispatch_notifications
from app.services.readiness import ReadinessService

TABLES = (
    "notifications, ai_usage_records, document_chunks, bookmarks, analyses, documents, "
    "raw_items, radar_sources, collection_runs, sources, radars, refresh_tokens, users"
)
FIXTURES = Path(__file__).resolve().parent / "fixtures"


async def healthy_probe() -> None:
    return None


class RecordingPublisher:
    def __init__(self) -> None:
        self.events: list[tuple[UUID, EventEnvelope]] = []

    async def publish(self, user_id: UUID, event: EventEnvelope) -> None:
        self.events.append((user_id, event))


class FixtureFetcher:
    async def fetch(self, url: str, source_type: SourceType) -> FetchResponse:
        fixture, content_type = (
            ("alpha_feed.xml", "application/rss+xml")
            if source_type == SourceType.RSS
            else ("alpha_page.html", "text/html; charset=utf-8")
        )
        return FetchResponse(
            final_url=url,
            content_type=content_type,
            body=(FIXTURES / fixture).read_bytes(),
        )


@pytest.fixture
async def alpha_engine() -> AsyncIterator[AsyncEngine]:
    database_url = os.environ["TEST_DATABASE_URL"]
    assert "_test" in database_url.rsplit("/", maxsplit=1)[-1]
    settings = Settings()
    engine = create_async_engine(database_url)
    broker = Redis.from_url(settings.redis_url.get_secret_value())
    results = Redis.from_url(settings.celery_result_backend.get_secret_value())
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    await broker.flushdb()
    await results.flushdb()
    yield engine
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    await broker.flushdb()
    await results.flushdb()
    await broker.aclose()
    await results.aclose()
    await engine.dispose()


async def register_and_login(
    client: AsyncClient, email: str
) -> tuple[dict[str, str], dict[str, Any]]:
    password = "offline-alpha-password-安全"  # noqa: S105 - isolated test credential
    registered = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "display_name": "Alpha Owner"},
    )
    assert registered.status_code == 201
    logged_in = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert logged_in.status_code == 200
    payload = logged_in.json()
    return {"Authorization": f"Bearer {payload['tokens']['access_token']}"}, payload


@pytest.mark.asyncio
async def test_complete_offline_alpha_loop_and_rest_recovery(alpha_engine: AsyncEngine) -> None:
    settings = Settings()
    factory = async_sessionmaker(alpha_engine, expire_on_commit=False)
    publisher = RecordingPublisher()
    app = create_app(settings, readiness_service=ReadinessService(healthy_probe, healthy_probe))
    app.state.session_factory = factory
    app.state.event_publisher = publisher
    queued: list[tuple[str, str]] = []
    app.state.collection_dispatcher = lambda run_id, correlation_id: queued.append(
        (run_id, correlation_id)
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner_headers, owner_auth = await register_and_login(client, "alpha-owner@example.com")
        stranger_headers, _ = await register_and_login(client, "alpha-stranger@example.com")
        owner_id = UUID(owner_auth["user"]["id"])

        radar_response = await client.post(
            "/api/v1/radars",
            headers=owner_headers,
            json={
                "name": "Alpha offline radar",
                "description": "BE-8 deterministic closure",
                "goal": "Validate the complete offline Alpha backend flow",
                "radar_type": "technology",
                "categories": ["technology"],
                "keywords": ["offline", "recovery"],
                "notification_threshold": 0,
            },
        )
        assert radar_response.status_code == 201
        radar_id = radar_response.json()["id"]

        sources: list[tuple[str, str]] = []
        for source_type, url in (
            ("rss", "https://fixtures.invalid/alpha-feed.xml"),
            ("url", "https://fixtures.invalid/alpha-page.html"),
        ):
            response = await client.post(
                "/api/v1/sources",
                headers=owner_headers,
                json={
                    "name": f"Offline {source_type.upper()}",
                    "source_type": source_type,
                    "url": url,
                    "poll_interval_minutes": 60,
                    "config": {},
                },
            )
            assert response.status_code == 201
            source_id = response.json()["id"]
            assert (
                await client.post(
                    f"/api/v1/radars/{radar_id}/sources/{source_id}",
                    headers=owner_headers,
                )
            ).status_code == 204
            sources.append((source_id, source_type))

        run_ids: list[UUID] = []
        for index, (source_id, _source_type) in enumerate(sources):
            headers = {**owner_headers, "Idempotency-Key": f"alpha-e2e-{index}"}
            created = await client.post(
                f"/api/v1/sources/{source_id}/collect",
                headers=headers,
            )
            replay = await client.post(
                f"/api/v1/sources/{source_id}/collect",
                headers=headers,
            )
            assert created.status_code == replay.status_code == 202
            assert created.json() == replay.json()
            run_ids.append(UUID(created.json()["run_id"]))

        fetcher = FixtureFetcher()
        first_delivery = await asyncio.gather(
            execute_run(
                SqlAlchemyAcquisitionRunRepository(factory),
                run_ids[0],
                backend=NativeAcquisitionBackend(fetcher),
                publisher=publisher,
            ),
            execute_run(
                SqlAlchemyAcquisitionRunRepository(factory),
                run_ids[0],
                backend=NativeAcquisitionBackend(fetcher),
                publisher=publisher,
            ),
        )
        assert sorted(first_delivery) == [False, True]
        assert await execute_run(
            SqlAlchemyAcquisitionRunRepository(factory),
            run_ids[1],
            backend=NativeAcquisitionBackend(fetcher),
            publisher=publisher,
        )

        async with AsyncSession(alpha_engine) as session:
            raw_ids = list(
                (
                    await session.scalars(
                        select(RawItem.id).order_by(RawItem.created_at, RawItem.id)
                    )
                ).all()
            )
        assert len(raw_ids) == 2

        documents: list[UUID] = []
        analyses: list[UUID] = []
        for raw_id in raw_ids:
            cleaned = await clean_raw_item(factory, raw_id)
            assert cleaned.document_id is not None
            assert len(cleaned.analysis_ids) == 1
            replay = await clean_raw_item(factory, raw_id)
            assert replay.document_id is None
            documents.append(cleaned.document_id)
            analyses.append(cleaned.analysis_ids[0])

        analysis_provider = FakeAnalysisProvider(settings.ai_model)
        for analysis_id in analyses:
            assert await run_analysis(factory, analysis_id, analysis_provider, settings)
            assert not await run_analysis(factory, analysis_id, analysis_provider, settings)
            assert await publish_analysis_completed(factory, analysis_id, publisher)

        embedding_provider = FakeEmbeddingProvider(settings.embedding_model)
        for document_id in documents:
            assert await run_embedding(factory, document_id, embedding_provider, settings)
            assert not await run_embedding(factory, document_id, embedding_provider, settings)

        notification_results = await asyncio.gather(
            dispatch_notifications(factory, publisher),
            dispatch_notifications(factory, publisher),
        )
        assert sum(notification_results) == 2
        async with AsyncSession(alpha_engine) as session:
            notifications = list((await session.scalars(select(Notification))).all())
        assert len(notifications) == 2
        assert {notification.analysis_id for notification in notifications} == set(analyses)

        notification_events = [
            event for _, event in publisher.events if event.event_type == "notification.created"
        ]
        assert len(notification_events) == 2
        notification_payloads = [event.data.model_dump() for event in notification_events]
        assert {payload["analysis_id"] for payload in notification_payloads} == set(analyses)
        assert len({payload["notification_id"] for payload in notification_payloads}) == 2
        assert {payload["notification_id"] for payload in notification_payloads} == {
            notification.id for notification in notifications
        }
        assert await dispatch_notifications(factory, publisher) == 0
        assert {event.event_type for _, event in publisher.events} == {
            "collection.updated",
            "analysis.completed",
            "notification.created",
        }

        intelligence = await client.get(
            f"/api/v1/intelligence?radar_id={radar_id}",
            headers=owner_headers,
        )
        assert intelligence.status_code == 200
        assert intelligence.json()["total"] == 2
        analysis_id = intelligence.json()["items"][0]["id"]
        document_id = intelligence.json()["items"][0]["document_id"]
        detail = await client.get(
            f"/api/v1/intelligence/{analysis_id}",
            headers=owner_headers,
        )
        assert detail.status_code == 200
        hidden = await client.get(
            f"/api/v1/intelligence/{analysis_id}",
            headers=stranger_headers,
        )
        missing = await client.get(
            f"/api/v1/intelligence/{uuid4()}",
            headers=stranger_headers,
        )
        assert hidden.status_code == missing.status_code == 404
        for field in ("code", "message", "details"):
            assert hidden.json()["error"][field] == missing.json()["error"][field]
        assert hidden.json()["error"]["request_id"]
        assert missing.json()["error"]["request_id"]

        bookmark = await client.post(
            "/api/v1/bookmarks",
            headers=owner_headers,
            json={"document_id": document_id, "note": "Recovered Alpha knowledge"},
        )
        assert bookmark.status_code == 201
        duplicate_bookmark = await client.post(
            "/api/v1/bookmarks",
            headers=owner_headers,
            json={"document_id": document_id, "note": "Duplicate"},
        )
        assert duplicate_bookmark.status_code == 409

        memory = await client.post(
            "/api/v1/memory/search",
            headers=owner_headers,
            json={
                "query": "offline resilient backend",
                "top_k": 5,
                "radar_id": radar_id,
                "bookmarked_only": True,
            },
        )
        assert memory.status_code == 200
        assert memory.json()["items"]
        assert all(item["bookmarked"] for item in memory.json()["items"])
        assert (
            await client.post(
                "/api/v1/memory/search",
                headers=stranger_headers,
                json={"query": "offline", "radar_id": radar_id},
            )
        ).status_code == 404

        notifications = await client.get("/api/v1/notifications", headers=owner_headers)
        assert notifications.status_code == 200
        assert notifications.json()["total"] == 2
        assert (await client.get("/api/v1/notifications", headers=stranger_headers)).json()[
            "total"
        ] == 0

        def unavailable_dispatch(_run_id: str, _correlation_id: str) -> None:
            raise RuntimeError("offline broker failure")

        app.state.collection_dispatcher = unavailable_dispatch
        failed_queue = await client.post(
            f"/api/v1/sources/{sources[0][0]}/collect",
            headers={**owner_headers, "Idempotency-Key": "alpha-e2e-broker-failure"},
        )
        assert failed_queue.status_code == 503
        recovered: list[tuple[str, str]] = []
        assert (
            await dispatch_queued_runs(
                factory,
                lambda run_id, correlation_id: recovered.append((run_id, correlation_id)),
            )
            == 1
        )
        assert len(recovered) == 1

    notification_event = next(
        event
        for user_id, event in publisher.events
        if user_id == owner_id and event.event_type == "notification.created"
    )
    websocket_app = create_app(settings)
    sync_redis = SyncRedis.from_url(settings.redis_url.get_secret_value(), decode_responses=True)
    with TestClient(websocket_app) as client:
        with client.websocket_connect("/api/v1/ws", headers=owner_headers) as websocket:
            sync_redis.publish(channel_for_user(owner_id), notification_event.model_dump_json())
            received = websocket.receive_json()
            assert received["event_id"] == str(notification_event.event_id)
            assert received["event_type"] == "notification.created"

        sync_redis.publish(channel_for_user(owner_id), notification_event.model_dump_json())
        recovered_facts = client.get("/api/v1/notifications", headers=owner_headers)
        assert recovered_facts.status_code == 200
        assert recovered_facts.json()["total"] == 2
    sync_redis.close()

    async with AsyncSession(alpha_engine) as session:
        assert len(list((await session.scalars(select(Document.id))).all())) == 2
        assert len(list((await session.scalars(select(Analysis.id))).all())) == 2
