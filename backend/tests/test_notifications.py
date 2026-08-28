from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from decimal import Decimal
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
from app.core.security import create_access_token
from app.main import create_app
from app.models.entities import (
    Analysis,
    AnalysisStatus,
    CollectionRun,
    CollectionRunStatus,
    CollectionTriggerType,
    Document,
    DocumentStatus,
    Notification,
    NotificationPriority,
    Radar,
    RadarType,
    RawItem,
    RawItemStatus,
    Recommendation,
    ResourceStatus,
    Source,
    SourceType,
    User,
)
from app.schemas.events import EventEnvelope
from app.services.intelligence import publish_analysis_completed
from app.services.notifications import dispatch_notifications, notification_priority
from app.services.readiness import ReadinessService

TABLES = (
    "notifications, ai_usage_records, document_chunks, bookmarks, analyses, documents, "
    "raw_items, radar_sources, collection_runs, sources, radars, refresh_tokens, users"
)


async def healthy_probe() -> None:
    return None


class RecordingPublisher:
    def __init__(self) -> None:
        self.events: list[tuple[UUID, EventEnvelope]] = []

    async def publish(self, user_id: UUID, event: EventEnvelope) -> None:
        self.events.append((user_id, event))


class CommitCheckingPublisher(RecordingPublisher):
    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        super().__init__()
        self.factory = factory

    async def publish(self, user_id: UUID, event: EventEnvelope) -> None:
        async with self.factory() as session:
            notification_id = event.data.model_dump().get("notification_id")
            assert notification_id is not None
            assert await session.get(Notification, notification_id) is not None
        await super().publish(user_id, event)


class FailingPublisher:
    async def publish(self, _user_id: UUID, _event: EventEnvelope) -> None:
        raise ConnectionError("redis-secret")


@pytest.fixture
async def notification_engine() -> Any:
    database_url = os.environ["TEST_DATABASE_URL"]
    assert "_test" in database_url.rsplit("/", maxsplit=1)[-1]
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    yield engine
    await engine.dispose()


async def create_user(engine: AsyncEngine, label: str) -> UUID:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        user = User(
            email=f"{label}-{uuid4()}@example.com",
            password_hash="synthetic",  # noqa: S106 - inert fixture
            display_name=label,
            profile={},
        )
        session.add(user)
        await session.commit()
        return user.id


async def create_completed_analysis(
    engine: AsyncEngine,
    *,
    user_id: UUID,
    score: Decimal | None,
    threshold: int,
    radar_status: ResourceStatus = ResourceStatus.ACTIVE,
    deleted: bool = False,
    summary: str | None = "Safe summary",
    analysis_status: AnalysisStatus = AnalysisStatus.COMPLETED,
) -> UUID:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        source = Source(
            user_id=user_id,
            name=f"Source {uuid4()}",
            source_type=SourceType.RSS,
            url=f"https://example.com/{uuid4()}",
            normalized_url=f"https://example.com/{uuid4()}",
            poll_interval_minutes=15,
            status=ResourceStatus.ACTIVE,
            config={},
        )
        radar = Radar(
            user_id=user_id,
            name=f"Radar {uuid4()}",
            goal="Notify safely",
            radar_type=RadarType.TECHNOLOGY,
            categories=[],
            keywords=[],
            status=radar_status,
            notification_threshold=threshold,
            deleted_at=datetime.now(UTC) if deleted else None,
        )
        session.add_all([source, radar])
        await session.flush()
        run = CollectionRun(
            source_id=source.id,
            trigger_type=CollectionTriggerType.MANUAL,
            status=CollectionRunStatus.SUCCEEDED,
        )
        session.add(run)
        await session.flush()
        raw = RawItem(
            source_id=source.id,
            collection_run_id=run.id,
            canonical_url=source.normalized_url,
            title="Safe title",
            fetched_at=datetime.now(UTC),
            raw_text="private-body-must-not-appear",
            content_hash=uuid4().hex * 2,
            item_metadata={},
            status=RawItemStatus.CLEANED,
        )
        session.add(raw)
        await session.flush()
        document = Document(
            raw_item_id=raw.id,
            canonical_url=raw.canonical_url,
            title="Safe title",
            content="private-body-must-not-appear",
            word_count=4,
            content_hash=uuid4().hex * 2,
            status=DocumentStatus.READY,
        )
        session.add(document)
        await session.flush()
        analysis = Analysis(
            document_id=document.id,
            radar_id=radar.id,
            pipeline_version="alpha-v1",
            prompt_version="intelligence-v1",
            summary=summary,
            radar_score=score,
            recommendation=Recommendation.READ if score is not None else None,
            reason="Safe reason",
            status=analysis_status,
        )
        session.add(analysis)
        await session.commit()
        return analysis.id


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (Decimal("0"), NotificationPriority.NORMAL),
        (Decimal("84.99"), NotificationPriority.NORMAL),
        (Decimal("85"), NotificationPriority.HIGH),
        (Decimal("94.99"), NotificationPriority.HIGH),
        (Decimal("95"), NotificationPriority.CRITICAL),
        (Decimal("100"), NotificationPriority.CRITICAL),
    ],
)
def test_notification_priority_boundaries(score: Decimal, expected: NotificationPriority) -> None:
    assert notification_priority(score) == expected


@pytest.mark.asyncio
async def test_notification_eligibility_concurrency_and_safe_events(
    notification_engine: AsyncEngine,
) -> None:
    user_id = await create_user(notification_engine, "owner")
    cases = [
        (Decimal("0"), 0, ResourceStatus.ACTIVE, False, True),
        (Decimal("84.99"), 85, ResourceStatus.ACTIVE, False, False),
        (Decimal("85"), 85, ResourceStatus.ACTIVE, False, True),
        (Decimal("94.99"), 85, ResourceStatus.ACTIVE, False, True),
        (Decimal("95"), 95, ResourceStatus.ACTIVE, False, True),
        (Decimal("100"), 100, ResourceStatus.ACTIVE, False, True),
        (Decimal("100"), 0, ResourceStatus.PAUSED, False, False),
        (Decimal("100"), 0, ResourceStatus.ACTIVE, True, False),
        (None, 0, ResourceStatus.ACTIVE, False, False),
    ]
    eligible: set[UUID] = set()
    for score, threshold, radar_status, deleted, qualifies in cases:
        analysis_id = await create_completed_analysis(
            notification_engine,
            user_id=user_id,
            score=score,
            threshold=threshold,
            radar_status=radar_status,
            deleted=deleted,
            summary=None if score == 0 else "Safe summary",
        )
        if qualifies:
            eligible.add(analysis_id)
    factory = async_sessionmaker(notification_engine, expire_on_commit=False)
    publisher = CommitCheckingPublisher(factory)
    counts = await asyncio.gather(
        dispatch_notifications(factory, publisher),
        dispatch_notifications(factory, publisher),
    )
    assert sum(counts) == len(eligible) == 5
    assert await dispatch_notifications(factory, publisher) == 0
    async with AsyncSession(notification_engine) as session:
        facts = list((await session.scalars(select(Notification))).all())
    assert {item.analysis_id for item in facts} == eligible
    assert len(publisher.events) == len(eligible)
    for event_user_id, event in publisher.events:
        assert event_user_id == user_id
        assert event.event_type == "notification.created"
        assert set(event.data.model_dump()) == {"notification_id", "analysis_id", "priority"}
        assert "private-body" not in event.model_dump_json()

    analysis_publisher = RecordingPublisher()
    analysis_id = next(iter(eligible))
    assert await publish_analysis_completed(factory, analysis_id, analysis_publisher)
    analysis_event = analysis_publisher.events[0][1]
    assert analysis_event.event_type == "analysis.completed"
    assert set(analysis_event.data.model_dump()) == {
        "analysis_id",
        "document_id",
        "radar_id",
        "radar_score",
        "recommendation",
    }
    assert "Safe summary" not in analysis_event.model_dump_json()

    failed_id = await create_completed_analysis(
        notification_engine,
        user_id=user_id,
        score=Decimal("100"),
        threshold=0,
        analysis_status=AnalysisStatus.FAILED,
    )
    assert await dispatch_notifications(factory, publisher, analysis_id=failed_id) == 0


@pytest.mark.asyncio
async def test_notification_publish_failure_keeps_committed_fact(
    notification_engine: AsyncEngine,
) -> None:
    user_id = await create_user(notification_engine, "publish-failure")
    await create_completed_analysis(
        notification_engine, user_id=user_id, score=Decimal("100"), threshold=0
    )
    factory = async_sessionmaker(notification_engine, expire_on_commit=False)
    assert await dispatch_notifications(factory, FailingPublisher()) == 1
    async with AsyncSession(notification_engine) as session:
        assert await session.scalar(select(func.count()).select_from(Notification)) == 1


@pytest.mark.asyncio
async def test_notification_rest_filters_idempotent_read_and_ownership(
    notification_engine: AsyncEngine,
) -> None:
    owner_id = await create_user(notification_engine, "rest-owner")
    stranger_id = await create_user(notification_engine, "rest-stranger")
    await create_completed_analysis(
        notification_engine, user_id=owner_id, score=Decimal("95"), threshold=75
    )
    await create_completed_analysis(
        notification_engine, user_id=owner_id, score=Decimal("85"), threshold=75
    )
    factory = async_sessionmaker(notification_engine, expire_on_commit=False)
    assert await dispatch_notifications(factory) == 2
    settings = Settings()
    app = create_app(settings, readiness_service=ReadinessService(healthy_probe, healthy_probe))
    app.state.session_factory = factory
    owner_headers = {"Authorization": f"Bearer {create_access_token(owner_id, settings)}"}
    stranger_headers = {"Authorization": f"Bearer {create_access_token(stranger_id, settings)}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listing = await client.get(
            "/api/v1/notifications?page=1&page_size=1&status=unread&priority=critical",
            headers=owner_headers,
        )
        assert listing.status_code == 200
        assert listing.json()["total"] == 1 and len(listing.json()["items"]) == 1
        notification_id = listing.json()["items"][0]["id"]
        first = await client.post(
            f"/api/v1/notifications/{notification_id}/read", headers=owner_headers
        )
        replay = await client.post(
            f"/api/v1/notifications/{notification_id}/read", headers=owner_headers
        )
        hidden = await client.post(
            f"/api/v1/notifications/{notification_id}/read", headers=stranger_headers
        )
        missing = await client.post(
            f"/api/v1/notifications/{uuid4()}/read", headers=stranger_headers
        )
        assert first.status_code == replay.status_code == 200
        assert first.json()["read_at"] == replay.json()["read_at"]
        assert hidden.status_code == missing.status_code == 404
        read_all = await client.post("/api/v1/notifications/read-all", headers=owner_headers)
        read_all_replay = await client.post("/api/v1/notifications/read-all", headers=owner_headers)
        assert read_all.status_code == 200 and read_all.json()["updated_count"] == 1
        assert read_all_replay.json()["updated_count"] == 0
        openapi = (await client.get("/openapi.json")).json()
        assert "/api/v1/notifications" in openapi["paths"]
        assert "/api/v1/notifications/{notification_id}/read" in openapi["paths"]
        assert "/api/v1/notifications/read-all" in openapi["paths"]
        properties = openapi["components"]["schemas"]["NotificationResponse"]["properties"]
        assert "user_id" not in properties and "analysis_id" in properties
        assert "private-body-must-not-appear" not in listing.text
