from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings
from app.main import create_app
from app.models.entities import (
    CollectionRun,
    CollectionRunStatus,
    CollectionTriggerType,
    RawItem,
    ResourceStatus,
    Source,
    SourceType,
)
from app.services.acquisition import (
    dispatch_queued_runs,
    execute_run,
    schedule_due_sources,
)
from app.services.acquisition_types import CollectionError, FetchResponse
from app.services.readiness import ReadinessService

TABLES = (
    "notifications, ai_usage_records, document_chunks, bookmarks, analyses, documents, "
    "raw_items, radar_sources, collection_runs, sources, radars, refresh_tokens, users"
)


async def healthy_probe() -> None:
    return None


@pytest.fixture
async def acquisition_engine() -> AsyncIterator[AsyncEngine]:
    database_url = os.environ["TEST_DATABASE_URL"]
    assert "_test" in database_url.rsplit("/", maxsplit=1)[-1]
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    yield engine
    await engine.dispose()


@pytest.fixture
async def acquisition_client(
    acquisition_engine: AsyncEngine,
) -> AsyncIterator[tuple[AsyncClient, list[tuple[str, str]]]]:
    app = create_app(Settings(), readiness_service=ReadinessService(healthy_probe, healthy_probe))
    app.state.session_factory = async_sessionmaker(acquisition_engine, expire_on_commit=False)
    dispatched: list[tuple[str, str]] = []
    app.state.collection_dispatcher = lambda run_id, correlation_id: dispatched.append(
        (run_id, correlation_id)
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, dispatched


async def auth_headers(client: AsyncClient, email: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "acquisition-password-安全", "display_name": "Owner"},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['tokens']['access_token']}"}


async def create_source(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    source_type: str = "rss",
    url: str = "https://example.com/feed.xml",
) -> str:
    response = await client.post(
        "/api/v1/sources",
        headers=headers,
        json={
            "name": f"Source {uuid4()}",
            "source_type": source_type,
            "url": url,
            "poll_interval_minutes": 15,
            "config": {"private_hint": "must-never-be-forwarded"},
        },
    )
    assert response.status_code == 201
    return str(response.json()["id"])


@pytest.mark.asyncio
async def test_manual_collection_idempotency_queue_failure_and_api_contract(
    acquisition_client: tuple[AsyncClient, list[tuple[str, str]]],
    acquisition_engine: AsyncEngine,
) -> None:
    client, dispatched = acquisition_client
    headers = await auth_headers(client, "collector@example.com")
    source_id = await create_source(client, headers)

    first = await client.post(
        f"/api/v1/sources/{source_id}/collect",
        headers={**headers, "Idempotency-Key": "  stable-key  "},
    )
    replay = await client.post(
        f"/api/v1/sources/{source_id}/collect",
        headers={**headers, "Idempotency-Key": "stable-key"},
    )
    assert first.status_code == replay.status_code == 202
    assert first.json() == replay.json()
    assert first.headers["location"] == f"/api/v1/collection-runs/{first.json()['run_id']}"
    assert first.json()["status"] == "queued"
    assert len(dispatched) == 2
    assert all(value[1] for value in dispatched)

    second = await client.post(f"/api/v1/sources/{source_id}/collect", headers=headers)
    third = await client.post(f"/api/v1/sources/{source_id}/collect", headers=headers)
    assert second.json()["run_id"] != third.json()["run_id"]

    async def concurrent_collect() -> Any:
        return await client.post(
            f"/api/v1/sources/{source_id}/collect",
            headers={**headers, "Idempotency-Key": "concurrent-key"},
        )

    concurrent = await asyncio.gather(concurrent_collect(), concurrent_collect())
    assert [item.status_code for item in concurrent] == [202, 202]
    assert concurrent[0].json()["run_id"] == concurrent[1].json()["run_id"]

    invalid = await client.post(
        f"/api/v1/sources/{source_id}/collect",
        headers={**headers, "Idempotency-Key": ""},
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "invalid_request"

    stranger = await auth_headers(client, "collect-stranger@example.com")
    hidden = await client.post(f"/api/v1/sources/{source_id}/collect", headers=stranger)
    missing = await client.post(f"/api/v1/sources/{uuid4()}/collect", headers=stranger)
    assert hidden.status_code == missing.status_code == 404
    assert hidden.json()["error"]["code"] == missing.json()["error"]["code"]

    paused = await client.post(f"/api/v1/sources/{source_id}/pause", headers=headers)
    assert paused.status_code == 200
    inactive = await client.post(f"/api/v1/sources/{source_id}/collect", headers=headers)
    assert inactive.status_code == 409
    assert inactive.json()["error"]["code"] == "source_not_active"
    assert (
        await client.post(f"/api/v1/sources/{source_id}/resume", headers=headers)
    ).status_code == 200

    async with AsyncSession(acquisition_engine) as session:
        owner_id = await session.scalar(select(Source.user_id).where(Source.id == UUID(source_id)))
        assert owner_id is not None
        legacy_api_source = Source(
            user_id=owner_id,
            name="Legacy API",
            source_type=SourceType.API,
            url="https://api.example.com/data",
            normalized_url="https://api.example.com/data",
            poll_interval_minutes=15,
            status=ResourceStatus.ACTIVE,
            config={},
        )
        session.add(legacy_api_source)
        await session.commit()
        await session.refresh(legacy_api_source)
        legacy_api_id = legacy_api_source.id
    unsupported = await client.post(f"/api/v1/sources/{legacy_api_id}/collect", headers=headers)
    assert unsupported.status_code == 422
    assert unsupported.json()["error"]["code"] == "unsupported_source_type"

    client._transport.app.state.collection_dispatcher = (  # type: ignore[attr-defined]
        lambda _run_id, _correlation_id: (_ for _ in ()).throw(ConnectionError("secret broker"))
    )
    failed_dispatch = await client.post(
        f"/api/v1/sources/{source_id}/collect",
        headers={**headers, "Idempotency-Key": "broker-failure"},
    )
    assert failed_dispatch.status_code == 503
    assert failed_dispatch.json()["error"]["code"] == "collection_queue_unavailable"
    assert "secret" not in failed_dispatch.text
    async with AsyncSession(acquisition_engine) as session:
        queued = await session.scalar(
            select(CollectionRun).where(CollectionRun.idempotency_key == "broker-failure")
        )
        assert queued is not None
        assert queued.status == CollectionRunStatus.QUEUED
        assert queued.error_code == "queue_unavailable"

    redelivered: list[tuple[str, str]] = []
    factory = async_sessionmaker(acquisition_engine, expire_on_commit=False)
    assert (
        await dispatch_queued_runs(
            factory,
            lambda run_id, correlation_id: redelivered.append((run_id, correlation_id)),
        )
        >= 1
    )
    assert any(run_id == str(queued.id) for run_id, _ in redelivered)
    async with AsyncSession(acquisition_engine) as session:
        recovered = await session.get(CollectionRun, queued.id)
        assert recovered is not None
        assert recovered.error_code is None

    openapi = (await client.get("/openapi.json")).json()
    assert "/api/v1/sources/{source_id}/collect" in openapi["paths"]
    assert "/api/v1/collection-runs/{run_id}/items" in openapi["paths"]
    schemas = openapi["components"]["schemas"]
    assert "raw_text" not in schemas["RawItemResponse"]["properties"]
    assert "metadata" in schemas["RawItemResponse"]["properties"]


@pytest.mark.asyncio
async def test_collection_queries_are_owned_filtered_and_paginated(
    acquisition_client: tuple[AsyncClient, list[tuple[str, str]]],
) -> None:
    client, _ = acquisition_client
    owner = await auth_headers(client, "run-owner@example.com")
    stranger = await auth_headers(client, "run-stranger@example.com")
    source_id = await create_source(client, owner)
    run_ids: list[str] = []
    for key in ("one", "two", "three"):
        response = await client.post(
            f"/api/v1/sources/{source_id}/collect",
            headers={**owner, "Idempotency-Key": key},
        )
        run_ids.append(response.json()["run_id"])

    page = await client.get(
        f"/api/v1/sources/{source_id}/runs?page=1&page_size=2&status=queued&trigger_type=manual",
        headers=owner,
    )
    assert page.status_code == 200
    assert page.json()["total"] == 3
    assert len(page.json()["items"]) == 2
    assert (
        await client.get(f"/api/v1/collection-runs/{run_ids[0]}", headers=owner)
    ).status_code == 200

    for path in (
        f"/api/v1/sources/{source_id}/runs",
        f"/api/v1/collection-runs/{run_ids[0]}",
        f"/api/v1/collection-runs/{run_ids[0]}/items",
    ):
        unauthorized = await client.get(path, headers=stranger)
        missing = await client.get(
            path.replace(source_id, str(uuid4())).replace(run_ids[0], str(uuid4())),
            headers=stranger,
        )
        assert unauthorized.status_code == missing.status_code == 404
        assert unauthorized.json()["error"]["code"] == missing.json()["error"]["code"]
        assert unauthorized.json()["error"]["message"] == missing.json()["error"]["message"]
        assert unauthorized.json()["error"]["details"] == missing.json()["error"]["details"]


class StaticFetcher:
    def __init__(self, body: bytes, content_type: str = "application/rss+xml") -> None:
        self.body = body
        self.content_type = content_type
        self.urls: list[str] = []

    async def fetch(self, url: str, _source_type: object) -> FetchResponse:
        self.urls.append(url)
        return FetchResponse(
            final_url="https://example.com/feed.xml",
            content_type=self.content_type,
            body=self.body,
        )


class FailingFetcher:
    async def fetch(self, _url: str, _source_type: object) -> FetchResponse:
        raise CollectionError("invalid_feed", "Safe parser failure")


class ExplodingFetcher:
    async def fetch(self, _url: str, _source_type: object) -> FetchResponse:
        raise RuntimeError("database-url-and-token-must-not-leak")


@pytest.mark.asyncio
async def test_worker_is_idempotent_partial_and_applies_three_level_deduplication(
    acquisition_client: tuple[AsyncClient, list[tuple[str, str]]],
    acquisition_engine: AsyncEngine,
) -> None:
    client, _ = acquisition_client
    headers = await auth_headers(client, "worker@example.com")
    source_id = await create_source(client, headers)
    factory = async_sessionmaker(acquisition_engine, expire_on_commit=False)

    async def new_run(key: str) -> UUID:
        response = await client.post(
            f"/api/v1/sources/{source_id}/collect",
            headers={**headers, "Idempotency-Key": key},
        )
        return UUID(response.json()["run_id"])

    first_run = await new_run("worker-one")
    first_feed = b"""<rss><channel><item><guid>external-1</guid>
      <link>https://example.com/canonical-1</link><description>same content</description>
      </item></channel></rss>"""
    first_fetcher = StaticFetcher(first_feed)
    outcomes = await asyncio.gather(
        execute_run(factory, first_run, fetcher=first_fetcher),  # type: ignore[arg-type]
        execute_run(factory, first_run, fetcher=first_fetcher),  # type: ignore[arg-type]
    )
    assert sorted(outcomes) == [False, True]
    assert first_fetcher.urls == ["https://example.com/feed.xml"]

    second_run = await new_run("worker-two")
    second_feed = b"""<rss><channel>
      <item><guid>external-1</guid><link>https://example.com/new-a</link>
        <description>new A</description></item>
      <item><guid>external-2</guid><link>https://example.com/canonical-1</link>
        <description>new B</description></item>
      <item><guid>external-3</guid><link>https://example.com/new-c</link>
        <description>same content</description></item>
      <item><guid>external-4</guid><link>https://example.com/new-d</link>
        <description>unique content</description></item>
      <item><guid>empty</guid><description> </description></item>
    </channel></rss>"""
    assert await execute_run(
        factory,
        second_run,
        fetcher=StaticFetcher(second_feed),  # type: ignore[arg-type]
    )

    async with AsyncSession(acquisition_engine) as session:
        run = await session.get(CollectionRun, second_run)
        assert run is not None
        assert run.status == CollectionRunStatus.PARTIAL
        assert (run.fetched_count, run.created_count, run.duplicate_count, run.failed_count) == (
            5,
            1,
            3,
            1,
        )
        assert int(await session.scalar(select(func.count()).select_from(RawItem)) or 0) == 2

    items = await client.get(f"/api/v1/collection-runs/{second_run}/items", headers=headers)
    assert items.status_code == 200
    assert items.json()["total"] == 1
    assert "raw_text" not in items.json()["items"][0]
    assert items.json()["items"][0]["metadata"] == {}

    failed_run = await new_run("worker-failure")
    assert not await execute_run(
        factory,
        failed_run,
        fetcher=FailingFetcher(),  # type: ignore[arg-type]
        correlation_id="safe-correlation",
        task_id="safe-task",
    )
    async with AsyncSession(acquisition_engine) as session:
        failed = await session.get(CollectionRun, failed_run)
        assert failed is not None
        assert failed.status == CollectionRunStatus.FAILED
        assert failed.failed_count == 1
        assert failed.error_code == "invalid_feed"
        assert failed.error_message == "Safe parser failure"

    internal_run = await new_run("worker-internal-failure")
    assert not await execute_run(
        factory,
        internal_run,
        fetcher=ExplodingFetcher(),  # type: ignore[arg-type]
    )
    async with AsyncSession(acquisition_engine) as session:
        internal = await session.get(CollectionRun, internal_run)
        assert internal is not None
        assert internal.status == CollectionRunStatus.FAILED
        assert internal.error_code == "internal_collection_error"
        assert "token" not in (internal.error_message or "").lower()

    deleted_run = await new_run("worker-deleted-source")
    assert (await client.delete(f"/api/v1/sources/{source_id}", headers=headers)).status_code == 204
    assert not await execute_run(
        factory,
        deleted_run,
        fetcher=StaticFetcher(first_feed),  # type: ignore[arg-type]
    )
    async with AsyncSession(acquisition_engine) as session:
        deleted = await session.get(CollectionRun, deleted_run)
        assert deleted is not None
        assert deleted.status == CollectionRunStatus.FAILED
        assert deleted.error_code == "internal_collection_error"


@pytest.mark.asyncio
async def test_scheduler_multi_instance_creates_one_run_per_minute(
    acquisition_client: tuple[AsyncClient, list[tuple[str, str]]],
    acquisition_engine: AsyncEngine,
) -> None:
    client, _ = acquisition_client
    headers = await auth_headers(client, "scheduler@example.com")
    source_id = await create_source(client, headers)
    factory = async_sessionmaker(acquisition_engine, expire_on_commit=False)
    now = datetime(2026, 8, 26, 10, 5, 42, tzinfo=UTC)
    counts = await asyncio.gather(
        schedule_due_sources(factory, now=now),
        schedule_due_sources(factory, now=now),
    )
    assert sum(counts) == 1
    async with AsyncSession(acquisition_engine) as session:
        runs = list(
            (
                await session.scalars(
                    select(CollectionRun).where(
                        CollectionRun.source_id == UUID(source_id),
                        CollectionRun.trigger_type == CollectionTriggerType.SCHEDULE,
                    )
                )
            ).all()
        )
        source = await session.get(Source, UUID(source_id))
        assert len(runs) == 1
        assert runs[0].idempotency_key == "schedule:2026-08-26T10:05:00+00:00"
        assert source is not None
        assert source.status == ResourceStatus.ACTIVE
        assert source.next_fetch_at == datetime(2026, 8, 26, 10, 20, 42, tzinfo=UTC)

    async with AsyncSession(acquisition_engine) as session:
        source = await session.get(Source, UUID(source_id))
        assert source is not None
        source.next_fetch_at = None
        await session.commit()
    assert await schedule_due_sources(factory, now=now) == 0

    def unavailable(_run_id: str, _correlation_id: str) -> None:
        raise ConnectionError("broker detail")

    assert await dispatch_queued_runs(factory, unavailable) == 0
    async with AsyncSession(acquisition_engine) as session:
        scheduled = await session.scalar(
            select(CollectionRun).where(
                CollectionRun.source_id == UUID(source_id),
                CollectionRun.trigger_type == CollectionTriggerType.SCHEDULE,
            )
        )
        assert scheduled is not None
        assert scheduled.error_code == "queue_unavailable"
        assert "broker detail" not in (scheduled.error_message or "")
