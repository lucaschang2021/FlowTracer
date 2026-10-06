"""ACQ-1 closure Phase 3 acceptance matrix (docs/71 §Phase 3, ADR-040 / docs/23 §10).

WP-6 complete write path:

3.1 qualifying changes produce new downstream inputs — the I2 writer creates a
    RawItem only for ``created`` / ``content_changed`` snapshots (metadata/structure
    only changes stay events; reverts reuse their snapshot without a new item);
3.2 the downstream chain — a changed observation flows change -> cleaning ->
    analysis -> notification;
3.3 read APIs — ``GET /sources/{id}/changes`` and the per-artifact history with
    ownership, pagination, filters, and bounded evidence;
3.4 sequence behaviours — removed after two misses, reappearance, content revert and
    repeated observation;
3.5 write-path switch — migration head is 0008, legacy items are linked by the
    backfill, and the snapshot identity column exists end to end.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.main import create_app
from app.models.entities import (
    AcquisitionMode,
    BackendName,
    CollectionRun,
    CollectionRunStatus,
    CollectionTriggerType,
    DiscoveryMode,
    Notification,
    Radar,
    RadarSource,
    RadarType,
    RawItem,
    RawItemStatus,
    ResourceStatus,
    Source,
    SourceAcquisitionState,
    SourceType,
    User,
)
from app.models.evidence import AcquisitionSnapshot, ChangeEvent, SourceArtifact
from app.providers.analysis import FakeAnalysisProvider
from app.schemas.resources import AcquisitionProfileV1
from app.services.acquisition_route import execute_route_run
from app.services.acquisition_run_repository import SqlAlchemyAcquisitionRunRepository
from app.services.change_backfill import backfill_source_evidence
from app.services.cleaning import clean_raw_item
from app.services.intelligence import run_analysis
from app.services.native_acquisition import NativeAcquisitionBackend, SafeCrawlTransport
from app.services.notifications import dispatch_notifications
from app.services.readiness import ReadinessService
from app.services.safe_fetcher import SafeFetcher, WireResponse

TABLES = (
    "notifications, ai_usage_records, opportunity_action_payloads, opportunity_scores, "
    "opportunities, change_events, acquisition_snapshots, source_artifacts, "
    "acquisition_attempts, source_acquisition_states, document_chunks, bookmarks, analyses, "
    "documents, raw_items, radar_sources, collection_runs, sources, radars, refresh_tokens, users"
)
PUBLIC_IP = "93.184.216.34"
SEED = "https://example.com/guide/start.html"
SEED_PATH = "/guide/start.html"
NOW = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)
RSS_URL = "https://example.com/feed.xml"


async def public_resolver(_hostname: str) -> list[str]:
    return [PUBLIC_IP]


def html_page(marker: str, *links: str) -> bytes:
    body = f"<html><head><title>{marker}</title></head><body><main><p>"
    body += f"{marker} deterministic acceptable extraction content. " * 40
    body += "</p>"
    for link in links:
        body += f'<a href="{link}">Read the related chapter</a>'
    body += "</main></body></html>"
    return body.encode()


def rss_feed(*entries: tuple[str, str, str]) -> bytes:
    """Feed body from (guid, title, description) entries."""
    items = "".join(
        f"<item><guid>{guid}</guid><link>https://example.com/{guid}</link>"
        f"<title>{title}</title><description>{description}</description></item>"
        for guid, title, description in entries
    )
    return f"<rss><channel>{items}</channel></rss>".encode()


class SiteTransport:
    """Mutable deterministic transport: paths serve (content_type, body); robots 404."""

    def __init__(self, pages: dict[str, tuple[str, bytes]]) -> None:
        self.pages = pages
        self.requests: list[str] = []

    async def __call__(self, *, url: str, **_kwargs: Any) -> WireResponse:
        self.requests.append(url)
        path = url.split("example.com", 1)[-1] or "/"
        if path == "/robots.txt":
            return WireResponse(404, {"content-type": "text/plain"}, b"")
        entry = self.pages.get(path)
        if entry is None:
            return WireResponse(404, {"content-type": "text/html"}, b"")
        content_type, body = entry
        return WireResponse(200, {"content-type": content_type}, body)


def backend_with(transport: SiteTransport) -> NativeAcquisitionBackend:
    return NativeAcquisitionBackend(
        fetcher=SafeFetcher(resolver=public_resolver, transport=transport)
    )


async def create_source(
    engine: AsyncEngine,
    *,
    source_type: SourceType = SourceType.URL,
    url: str = SEED,
    profile: AcquisitionProfileV1 | None = None,
    discovery_mode: DiscoveryMode = DiscoveryMode.SINGLE_PAGE,
) -> UUID:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User(
            id=uuid4(),
            email=f"closure-p3-{uuid4()}@example.com",
            password_hash="synthetic",  # noqa: S106 - isolated database fixture
            display_name="Closure P3",
        )
        source = Source(
            id=uuid4(),
            user_id=user.id,
            name="Closure P3 Source",
            source_type=source_type,
            url=url,
            normalized_url=url,
            acquisition_mode=AcquisitionMode.AUTO,
            discovery_mode=discovery_mode,
            acquisition_profile=(profile or AcquisitionProfileV1()).storage_dict(),
        )
        session.add(user)
        await session.flush()
        session.add(source)
        await session.flush()
        session.add(SourceAcquisitionState(source_id=source.id))
        await session.commit()
        return source.id


async def attach_radar(engine: AsyncEngine, source_id: UUID) -> None:
    """Subscribe an active technology radar so cleaning creates analyses."""
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        source = await session.get(Source, source_id)
        assert source is not None
        radar = Radar(
            id=uuid4(),
            user_id=source.user_id,
            name=f"Closure P3 radar {uuid4()}",
            goal="Phase 3 downstream chain",
            radar_type=RadarType.TECHNOLOGY,
            categories=[],
            keywords=["closure"],
            status=ResourceStatus.ACTIVE,
            notification_threshold=0,
        )
        session.add(radar)
        await session.flush()
        session.add(RadarSource(radar_id=radar.id, source_id=source_id))
        await session.commit()


async def queue_run(engine: AsyncEngine, source_id: UUID) -> UUID:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        run = CollectionRun(
            id=uuid4(),
            source_id=source_id,
            trigger_type=CollectionTriggerType.MANUAL,
            status=CollectionRunStatus.QUEUED,
        )
        session.add(run)
        await session.commit()
        return run.id


def run_once(
    engine: AsyncEngine,
    run_id: UUID,
    transport: SiteTransport,
    *,
    backend_name: BackendName = BackendName.NATIVE_HTTP,
    raw_dispatch: Any | None = None,
) -> Any:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return execute_route_run(
        SqlAlchemyAcquisitionRunRepository(factory),
        run_id,
        backends={backend_name: backend_with(transport)},
        task_id="closure-p3",
        raw_dispatch=raw_dispatch,
    )


def run_rss(engine: AsyncEngine, run_id: UUID, transport: SiteTransport) -> Any:
    return run_once(engine, run_id, transport, backend_name=BackendName.RSS)


async def items_for(engine: AsyncEngine, source_id: UUID) -> list[RawItem]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        return list(
            (
                await session.scalars(
                    select(RawItem)
                    .where(RawItem.source_id == source_id)
                    .order_by(RawItem.created_at.asc(), RawItem.id.asc())
                )
            ).all()
        )


async def events_for(engine: AsyncEngine, source_id: UUID) -> list[ChangeEvent]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        return list(
            (
                await session.scalars(
                    select(ChangeEvent)
                    .join(SourceArtifact, SourceArtifact.id == ChangeEvent.artifact_id)
                    .where(SourceArtifact.source_id == source_id)
                    .order_by(ChangeEvent.occurred_at.asc())
                )
            ).all()
        )


@pytest.fixture
async def closure_p3_engine() -> AsyncIterator[AsyncEngine]:
    database_url = os.environ["TEST_DATABASE_URL"]
    assert "_test" in database_url.rsplit("/", maxsplit=1)[-1]
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    yield engine
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    await engine.dispose()


@pytest.fixture
async def closure_p3_client(
    closure_p3_engine: AsyncEngine,
) -> AsyncIterator[AsyncClient]:
    async def healthy_probe() -> None:
        return None

    app = create_app(Settings(), readiness_service=ReadinessService(healthy_probe, healthy_probe))
    app.state.session_factory = async_sessionmaker(closure_p3_engine, expire_on_commit=False)
    app.state.collection_dispatcher = lambda run_id, correlation_id: None
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def auth_headers(client: AsyncClient, email: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "closure-password-安全", "display_name": "Owner"},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['tokens']['access_token']}"}


class TestQualifyingWriter:
    @pytest.mark.asyncio
    async def test_only_qualifying_snapshots_become_raw_items(
        self, closure_p3_engine: AsyncEngine
    ) -> None:
        source_id = await create_source(closure_p3_engine)
        version_a = html_page("Alpha state v1")
        version_b = html_page("Beta state v2")
        transport = SiteTransport({SEED_PATH: ("text/html; charset=utf-8", version_a)})

        first = await queue_run(closure_p3_engine, source_id)
        assert await run_once(closure_p3_engine, first, transport) is True
        items = await items_for(closure_p3_engine, source_id)
        assert len(items) == 1 and items[0].snapshot_id is not None

        transport.pages[SEED_PATH] = ("text/html; charset=utf-8", version_b)
        second = await queue_run(closure_p3_engine, source_id)
        assert await run_once(closure_p3_engine, second, transport) is True
        items = await items_for(closure_p3_engine, source_id)
        assert len(items) == 2  # content change qualifies a new version
        assert items[1].snapshot_id != items[0].snapshot_id

        # Revert to the earlier state: the snapshot is reused, no third item.
        transport.pages[SEED_PATH] = ("text/html; charset=utf-8", version_a)
        third = await queue_run(closure_p3_engine, source_id)
        assert await run_once(closure_p3_engine, third, transport) is True
        items = await items_for(closure_p3_engine, source_id)
        assert len(items) == 2
        events = await events_for(closure_p3_engine, source_id)
        assert [event.change_type for event in events] == [
            "created",
            "content_changed",
            "content_changed",
        ]

        # Repeated observation of the same state: unchanged, still no new item.
        fourth = await queue_run(closure_p3_engine, source_id)
        assert await run_once(closure_p3_engine, fourth, transport) is True
        assert len(await items_for(closure_p3_engine, source_id)) == 2
        assert (await events_for(closure_p3_engine, source_id))[-1].change_type == "unchanged"

    @pytest.mark.asyncio
    async def test_metadata_only_change_stays_an_event(
        self, closure_p3_engine: AsyncEngine
    ) -> None:
        source_id = await create_source(closure_p3_engine, source_type=SourceType.RSS, url=RSS_URL)
        description = "Stable body content " * 20
        transport = SiteTransport(
            {
                "/feed.xml": (
                    "application/rss+xml",
                    rss_feed(("entry-1", "First title", description)),
                )
            }
        )
        first = await queue_run(closure_p3_engine, source_id)
        assert await run_rss(closure_p3_engine, first, transport) is True

        transport.pages["/feed.xml"] = (
            "application/rss+xml",
            rss_feed(("entry-1", "Renamed title", description)),
        )
        second = await queue_run(closure_p3_engine, source_id)
        assert await run_rss(closure_p3_engine, second, transport) is True
        events = await events_for(closure_p3_engine, source_id)
        assert events[-1].change_type == "metadata_changed"
        # Metadata-only changes keep a single item (the content never changed).
        assert len(await items_for(closure_p3_engine, source_id)) == 1

    @pytest.mark.asyncio
    async def test_crawl_pages_qualify_and_dispatch(self, closure_p3_engine: AsyncEngine) -> None:
        factory = async_sessionmaker(closure_p3_engine, expire_on_commit=False)
        seed_body = html_page("Crawl seed", "https://example.com/guide/a.html")
        transport = SiteTransport(
            {
                SEED_PATH: ("text/html; charset=utf-8", seed_body),
                "/guide/a.html": ("text/html; charset=utf-8", html_page("Crawl child")),
            }
        )
        profile = AcquisitionProfileV1()
        profile.resource_budget.max_depth = 1
        profile.resource_budget.max_pages = 4
        source_id = await create_source(
            closure_p3_engine, profile=profile, discovery_mode=DiscoveryMode.SAME_DOMAIN
        )
        dispatched: list[str] = []
        run_id = await queue_run(closure_p3_engine, source_id)
        ok = await execute_route_run(
            SqlAlchemyAcquisitionRunRepository(factory),
            run_id,
            backends={BackendName.NATIVE_HTTP: backend_with(transport)},
            task_id="closure-p3-crawl",
            raw_dispatch=lambda value, _correlation: dispatched.append(value),
            discovery_transport=SafeCrawlTransport(
                SafeFetcher(resolver=public_resolver, transport=transport)
            ),
        )
        assert ok is True
        items = await items_for(closure_p3_engine, source_id)
        assert len(items) == 2  # seed + one crawled page, each from its snapshot
        assert all(item.snapshot_id is not None for item in items)
        assert sorted(dispatched) == sorted(str(item.id) for item in items)


class TestRemovedAndReappearance:
    @pytest.mark.asyncio
    async def test_two_missing_cycles_remove_and_reappearance_restores(
        self, closure_p3_engine: AsyncEngine
    ) -> None:
        source_id = await create_source(closure_p3_engine, source_type=SourceType.RSS, url=RSS_URL)
        both = rss_feed(
            ("entry-1", "First entry", "First body " * 20),
            ("entry-2", "Second entry", "Second body " * 20),
        )
        only_first = rss_feed(("entry-1", "First entry", "First body " * 20))
        transport = SiteTransport({"/feed.xml": ("application/rss+xml", both)})
        first = await queue_run(closure_p3_engine, source_id)
        assert await run_rss(closure_p3_engine, first, transport) is True
        assert len(await items_for(closure_p3_engine, source_id)) == 2

        transport.pages["/feed.xml"] = ("application/rss+xml", only_first)
        second = await queue_run(closure_p3_engine, source_id)
        assert await run_rss(closure_p3_engine, second, transport) is True
        assert "removed" not in [
            event.change_type for event in await events_for(closure_p3_engine, source_id)
        ]

        third = await queue_run(closure_p3_engine, source_id)
        assert await run_rss(closure_p3_engine, third, transport) is True
        events = await events_for(closure_p3_engine, source_id)
        assert events[-1].change_type == "removed"
        assert len(await items_for(closure_p3_engine, source_id)) == 2  # removals add no item

        # Reappearance with identical content clears the removal without a new item.
        transport.pages["/feed.xml"] = ("application/rss+xml", both)
        fourth = await queue_run(closure_p3_engine, source_id)
        assert await run_rss(closure_p3_engine, fourth, transport) is True
        factory = async_sessionmaker(closure_p3_engine, expire_on_commit=False)
        async with factory() as session:
            artifact = await session.scalar(
                select(SourceArtifact).where(
                    SourceArtifact.source_id == source_id,
                    SourceArtifact.artifact_key == "https://example.com/entry-2",
                )
            )
            assert artifact is not None and artifact.removed_at is None
        assert len(await items_for(closure_p3_engine, source_id)) == 2


class TestReadApis:
    @pytest.mark.asyncio
    async def test_change_history_endpoints(
        self, closure_p3_engine: AsyncEngine, closure_p3_client: AsyncClient
    ) -> None:
        client = closure_p3_client
        headers = await auth_headers(client, "change-reader@example.com")
        source_response = await client.post(
            "/api/v1/sources",
            headers=headers,
            json={
                "name": "Reader source",
                "source_type": "url",
                "url": SEED,
                "poll_interval_minutes": 15,
                "config": {},
            },
        )
        assert source_response.status_code == 201
        source_id = UUID(source_response.json()["id"])

        version_a = html_page("Reader state one")
        version_b = html_page("Reader state two")
        transport = SiteTransport({SEED_PATH: ("text/html; charset=utf-8", version_a)})
        first = await queue_run(closure_p3_engine, source_id)
        assert await run_once(closure_p3_engine, first, transport) is True
        transport.pages[SEED_PATH] = ("text/html; charset=utf-8", version_b)
        second = await queue_run(closure_p3_engine, source_id)
        assert await run_once(closure_p3_engine, second, transport) is True

        response = await client.get(f"/api/v1/sources/{source_id}/changes", headers=headers)
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 2
        assert [item["change_type"] for item in payload["items"]] == [
            "content_changed",
            "created",
        ]
        changed = payload["items"][0]
        assert changed["previous"]["version"] == 1
        assert changed["current"]["version"] == 2
        assert changed["artifact_key"] == SEED
        # Bounded evidence only: raw body text and internal trace never leak, and
        # field-diff values stay within the frozen 200-character bound.
        serialized = json.dumps(payload)
        assert "deterministic acceptable extraction content" not in serialized
        values = [
            value for field in changed["field_diff"]["fields"].values() for value in field.values()
        ]
        assert values and all(len(str(value)) <= 200 for value in values)
        assert set(changed["field_diff"]) == {"changed", "fields"}

        filtered = await client.get(
            f"/api/v1/sources/{source_id}/changes",
            headers=headers,
            params={"change_type": "created"},
        )
        assert filtered.status_code == 200
        assert filtered.json()["total"] == 1

        artifact_id = changed["artifact_id"]
        artifact_history = await client.get(
            f"/api/v1/sources/{source_id}/artifacts/{artifact_id}/changes", headers=headers
        )
        assert artifact_history.status_code == 200
        assert artifact_history.json()["total"] == 2

        by_artifact = await client.get(
            f"/api/v1/sources/{source_id}/changes",
            headers=headers,
            params={"artifact_id": artifact_id, "page_size": 1},
        )
        assert by_artifact.status_code == 200
        assert by_artifact.json()["total"] == 2
        assert len(by_artifact.json()["items"]) == 1

        # Ownership and existence are enforced.
        other = await auth_headers(client, "change-other@example.com")
        assert (
            await client.get(f"/api/v1/sources/{source_id}/changes", headers=other)
        ).status_code == 404
        missing_artifact = await client.get(
            f"/api/v1/sources/{source_id}/artifacts/{uuid4()}/changes", headers=headers
        )
        assert missing_artifact.status_code == 404
        assert (
            await client.get(
                f"/api/v1/sources/{source_id}/changes",
                headers=headers,
                params={"change_type": "bogus"},
            )
        ).status_code == 422


class TestDownstreamChain:
    @pytest.mark.asyncio
    async def test_changed_observation_reaches_notification(
        self, closure_p3_engine: AsyncEngine
    ) -> None:
        source_id = await create_source(closure_p3_engine)
        await attach_radar(closure_p3_engine, source_id)
        transport = SiteTransport(
            {SEED_PATH: ("text/html; charset=utf-8", html_page("Chain state one"))}
        )
        first = await queue_run(closure_p3_engine, source_id)
        assert await run_once(closure_p3_engine, first, transport) is True
        transport.pages[SEED_PATH] = ("text/html; charset=utf-8", html_page("Chain state two"))
        second = await queue_run(closure_p3_engine, source_id)
        assert await run_once(closure_p3_engine, second, transport) is True

        items = await items_for(closure_p3_engine, source_id)
        assert len(items) == 2
        changed_item = items[1]
        assert changed_item.status == RawItemStatus.FETCHED

        factory = async_sessionmaker(closure_p3_engine, expire_on_commit=False)
        cleaned = await clean_raw_item(factory, changed_item.id)
        assert cleaned.document_id is not None
        assert len(cleaned.analysis_ids) == 1
        settings = Settings()
        analysis_provider = FakeAnalysisProvider(settings.ai_model)
        assert await run_analysis(factory, cleaned.analysis_ids[0], analysis_provider, settings)

        class RecordingPublisher:
            def __init__(self) -> None:
                self.events: list[Any] = []

            async def publish(self, user_id: UUID, event: Any) -> None:
                self.events.append(event)

        publisher = RecordingPublisher()
        assert await dispatch_notifications(factory, publisher) == 1
        async with factory() as session:
            notification = await session.scalar(select(Notification))
            assert notification is not None
            assert notification.analysis_id == cleaned.analysis_ids[0]


class TestBackfillLinking:
    @pytest.mark.asyncio
    async def test_legacy_items_are_linked_to_their_snapshots(
        self, closure_p3_engine: AsyncEngine
    ) -> None:
        source_id = await create_source(closure_p3_engine, source_type=SourceType.RSS, url=RSS_URL)
        factory = async_sessionmaker(closure_p3_engine, expire_on_commit=False)
        run_id = await queue_run(closure_p3_engine, source_id)
        async with factory() as session:
            for index in range(3):
                session.add(
                    RawItem(
                        id=uuid4(),
                        source_id=source_id,
                        collection_run_id=run_id,
                        external_id=f"legacy-{index}",
                        canonical_url=f"https://example.com/legacy-{index}",
                        title=f"Legacy {index}",
                        fetched_at=NOW,
                        content_type="text/html",
                        raw_text=f"Legacy body {index} " * 10,
                        content_hash=f"{index:064x}",
                        item_metadata={},
                        status=RawItemStatus.FETCHED,
                    )
                )
            await session.commit()

        async with factory() as session:
            source = await session.get(Source, source_id)
            assert source is not None
            first = await backfill_source_evidence(session, source=source, batch_size=2)
            await session.commit()
            assert first == 3
        async with factory() as session:
            source = await session.get(Source, source_id)
            assert source is not None
            second = await backfill_source_evidence(session, source=source, batch_size=2)
            await session.commit()
            assert second == 0
        items = await items_for(closure_p3_engine, source_id)
        assert all(item.snapshot_id is not None for item in items)
        async with factory() as session:
            snapshots = list(
                (
                    await session.scalars(
                        select(AcquisitionSnapshot).where(
                            AcquisitionSnapshot.id.in_(
                                [item.snapshot_id for item in items if item.snapshot_id]
                            )
                        )
                    )
                ).all()
            )
        assert len(snapshots) == 3
        assert all(snapshot.evidence.get("origin") == "legacy_backfill" for snapshot in snapshots)
        assert (await events_for(closure_p3_engine, source_id))[0].change_type == "created"
        after = await items_for(closure_p3_engine, source_id)
        assert [item.id for item in after] == [item.id for item in items]
        assert all(item.snapshot_id is not None for item in after)
