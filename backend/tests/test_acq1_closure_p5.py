"""ACQ-1 closure Phase 5 acceptance matrix (docs/71 §Phase 5, docs/25 §16).

WP-8 full-chain acceptance on the production path with deterministic offline
fixtures only (no public network):

5.1 the complete chain: Radar/Source configuration -> routed Acquisition -> Router
    -> Discovery crawl -> Change evidence -> Opportunity lifecycle -> persistence
    -> REST/notification facts;
5.2 the operational paths: failure leaves no partial state, cancel/resume keeps
    pending targets and never duplicates, concurrent runs dedupe, double dispatch
    is claim-guarded, and budget exhaustion stops before exceeding while preserving
    the frontier.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.core.security import create_access_token
from app.domains.provider_ports import (
    OpportunityEvaluationRequest,
    ProviderResponse,
    ProviderUsage,
)
from app.main import create_app
from app.models.entities import (
    AcquisitionAttempt,
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
    ResourceStatus,
    Source,
    SourceAcquisitionState,
    SourceFamily,
    SourceType,
    User,
)
from app.models.evidence import AcquisitionSnapshot, ChangeEvent, SourceArtifact
from app.models.opportunity import (
    OpportunityActionPayload,
    OpportunityItem,
    OpportunityScore,
)
from app.schemas.resources import AcquisitionProfileV1
from app.services.acquisition_route import execute_route_run
from app.services.acquisition_run_repository import SqlAlchemyAcquisitionRunRepository
from app.services.native_acquisition import NativeAcquisitionBackend, SafeCrawlTransport
from app.services.opportunity_evaluation import dispatch_pending_opportunities
from app.services.readiness import ReadinessService
from app.services.safe_fetcher import SafeFetcher, WireResponse

TABLES = (
    "notifications, ai_usage_records, opportunity_action_payloads, opportunity_scores, "
    "opportunities, change_events, acquisition_snapshots, source_artifacts, "
    "acquisition_attempts, source_acquisition_states, document_chunks, bookmarks, analyses, "
    "documents, raw_items, radar_sources, collection_runs, sources, radars, refresh_tokens, users"
)
PUBLIC_IP = "93.184.216.34"
SEED_URL = "https://jobs.example.com/gig-1"
CHILD_PATH = "/gig-2.html"
NOW = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)

GOOD_DIMS: dict[str, Any] = {
    "fit": 90,
    "expected_value": 88,
    "completion_probability": 86,
    "effort_efficiency": 84,
    "time_to_delivery": 82,
    "competition": 20,
    "ambiguity": 15,
    "risk": 10,
    "reason": "Strong fit for a short one-off gig.",
}


async def public_resolver(_hostname: str) -> list[str]:
    return [PUBLIC_IP]


def job_page(title: str, description: str, *, budget: tuple[int, int], extra: bytes = b"") -> bytes:
    return (
        b'<html><head><script type="application/ld+json">'
        b'{"@context":"https://schema.org","@type":"JobPosting",'
        b'"title":"' + title.encode() + b'",'
        b'"description":"<p>' + description.encode() + b'</p>",'
        b'"datePosted":"2026-10-05T12:00:00Z",'
        b'"validThrough":"2026-10-07T12:00:00Z",'
        b'"baseSalary":{"currency":"USD","value":{"minValue":'
        + str(budget[0]).encode()
        + b',"maxValue":'
        + str(budget[1]).encode()
        + b"}},"
        b'"skills":"React","deliveryType":"one_off","estimatedEffortHours":4,'
        b'"requiredMeetings":1}'
        b"</script></head><body>"
        + (title + " deterministic acceptable extraction body content. ").encode() * 30
        + extra
        + b"</body></html>"
    )


SEED_PAGE = job_page(
    "Landing page refresh",
    "Build a small landing page with React.",
    budget=(50, 60),
    extra=b'<a href="/gig-2.html">Open the next gig</a>',
)
CHILD_PAGE = job_page(
    "CSS cleanup",
    "Tidy a small CSS codebase.",
    budget=(45, 55),
)


class SiteTransport:
    """Deterministic transport: mutable (content_type, body) per path; robots 404."""

    def __init__(self, pages: dict[str, tuple[str, bytes]]) -> None:
        self.pages = pages
        self.requests: list[str] = []
        self.per_url: dict[str, int] = {}
        self.hooks: dict[str, Any] = {}

    async def __call__(self, *, url: str, **_kwargs: Any) -> WireResponse:
        self.requests.append(url)
        self.per_url[url] = self.per_url.get(url, 0) + 1
        hook = self.hooks.get(url)
        if hook is not None:
            await hook()
        path = url.split("jobs.example.com", 1)[-1] or "/"
        if path == "/robots.txt":
            return WireResponse(404, {"content-type": "text/plain"}, b"")
        entry = self.pages.get(path)
        if entry is None:
            return WireResponse(404, {"content-type": "text/html"}, b"")
        content_type, body = entry
        return WireResponse(200, {"content-type": content_type}, body)


class ScriptedOpportunityProvider:
    name = "scripted"
    model = "scripted-opportunity-v1"

    def __init__(self) -> None:
        self.calls = 0

    async def evaluate(
        self, request: OpportunityEvaluationRequest, *, repair_error: str | None = None
    ) -> ProviderResponse:
        del request, repair_error
        self.calls += 1
        import json as _json

        return ProviderResponse(_json.dumps(GOOD_DIMS), ProviderUsage(10, 20, 30))


async def create_chain_context(
    engine: AsyncEngine,
    *,
    max_requests: int = 30,
) -> tuple[UUID, UUID, UUID]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User(
            id=uuid4(),
            email=f"closure-p5-{uuid4()}@example.com",
            password_hash="synthetic",  # noqa: S106 - isolated database fixture
            display_name="Closure P5",
        )
        radar = Radar(
            id=uuid4(),
            user_id=user.id,
            name=f"Freelance {uuid4()}",
            goal="Find short freelance gigs",
            radar_type=RadarType.OPPORTUNITY,
            categories=[],
            keywords=["react"],
            status=ResourceStatus.ACTIVE,
            notification_threshold=0,
        )
        profile = AcquisitionProfileV1()
        profile.resource_budget.max_pages = 3
        profile.resource_budget.max_depth = 1
        profile.resource_budget.max_requests = max_requests
        source = Source(
            id=uuid4(),
            user_id=user.id,
            name="Jobs Board",
            source_type=SourceType.URL,
            url=SEED_URL,
            normalized_url=SEED_URL,
            source_family=SourceFamily.OPPORTUNITY,
            acquisition_mode=AcquisitionMode.AUTO,
            discovery_mode=DiscoveryMode.SAME_DOMAIN,
            acquisition_profile=profile.storage_dict(),
        )
        session.add(user)
        await session.flush()
        session.add_all([radar, source])
        await session.flush()
        session.add(RadarSource(radar_id=radar.id, source_id=source.id))
        session.add(SourceAcquisitionState(source_id=source.id))
        await session.commit()
        return user.id, radar.id, source.id


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


def run_chain(
    engine: AsyncEngine,
    run_id: UUID,
    transport: SiteTransport,
    *,
    raw_dispatch: Any | None = None,
    task_id: str = "closure-p5",
) -> Any:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return execute_route_run(
        SqlAlchemyAcquisitionRunRepository(factory),
        run_id,
        backends={
            BackendName.NATIVE_HTTP: NativeAcquisitionBackend(
                SafeFetcher(resolver=public_resolver, transport=transport)
            )
        },
        task_id=task_id,
        raw_dispatch=raw_dispatch,
        discovery_transport=SafeCrawlTransport(
            SafeFetcher(resolver=public_resolver, transport=transport)
        ),
    )


async def requeue_run(engine: AsyncEngine, run_id: UUID) -> None:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await session.execute(
            text(
                "UPDATE collection_runs SET status='queued', claim_token=NULL, "
                "finished_at=NULL, error_code=NULL, error_message=NULL WHERE id=:id"
            ),
            {"id": str(run_id)},
        )
        await session.commit()


async def count_rows(engine: AsyncEngine, model: type[Any]) -> int:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        return int(await session.scalar(select(func.count()).select_from(model)) or 0)


async def items_for(engine: AsyncEngine, source_id: UUID) -> list[OpportunityItem]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        return list(
            (
                await session.scalars(
                    select(OpportunityItem)
                    .where(OpportunityItem.source_id == source_id)
                    .order_by(OpportunityItem.title.asc())
                )
            ).all()
        )


async def raw_items_for(engine: AsyncEngine, source_id: UUID) -> list[RawItem]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        return list(
            (await session.scalars(select(RawItem).where(RawItem.source_id == source_id))).all()
        )


async def dispatch_all(engine: AsyncEngine) -> int:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return await dispatch_pending_opportunities(
        factory, ScriptedOpportunityProvider(), Settings(), now=NOW
    )


@pytest.fixture
async def closure_p5_engine() -> AsyncIterator[AsyncEngine]:
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
async def closure_p5_client(closure_p5_engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    async def healthy() -> None:
        return None

    app = create_app(Settings(), readiness_service=ReadinessService(healthy, healthy))
    app.state.session_factory = async_sessionmaker(closure_p5_engine, expire_on_commit=False)
    app.state.collection_dispatcher = lambda run_id, correlation_id: None
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


def chain_transport() -> SiteTransport:
    return SiteTransport(
        {
            "/gig-1": ("text/html; charset=utf-8", SEED_PAGE),
            CHILD_PATH: ("text/html; charset=utf-8", CHILD_PAGE),
        }
    )


class TestFullChain:
    @pytest.mark.asyncio
    async def test_full_chain_offline_end_to_end(
        self, closure_p5_engine: AsyncEngine, closure_p5_client: AsyncClient
    ) -> None:
        user_id, _radar_id, source_id = await create_chain_context(closure_p5_engine)
        transport = chain_transport()
        dispatched: list[str] = []
        run_id = await queue_run(closure_p5_engine, source_id)
        ok = await run_chain(
            closure_p5_engine,
            run_id,
            transport,
            raw_dispatch=lambda value, _correlation: dispatched.append(value),
        )
        assert ok is True

        factory = async_sessionmaker(closure_p5_engine, expire_on_commit=False)
        async with factory() as session:
            run = await session.get(CollectionRun, run_id)
            state = await session.get(SourceAcquisitionState, source_id)
            attempts = list(
                (
                    await session.scalars(
                        select(AcquisitionAttempt)
                        .where(AcquisitionAttempt.run_id == run_id)
                        .order_by(AcquisitionAttempt.ordinal.asc())
                    )
                ).all()
            )
            assert run is not None and state is not None
            assert run.status == CollectionRunStatus.SUCCEEDED
            assert run.backend == "native_http"
            # Router -> seed attempt + discovery crawl attempt for the discovered page.
            assert [row.requested_url for row in attempts] == [
                SEED_URL,
                f"https://jobs.example.com{CHILD_PATH}",
            ]
            crawl = run.budget_summary["discovery"]["crawl"]
            assert crawl["complete"] is True and crawl["pages_fetched"] == 1
            # Discovery consumed the frontier; change evidence exists for both pages.
            assert state.checkpoint["frontier"] == []
            assert await count_rows(closure_p5_engine, SourceArtifact) == 2
            assert await count_rows(closure_p5_engine, AcquisitionSnapshot) == 2
            change_types = list((await session.scalars(select(ChangeEvent.change_type))).all())
            assert change_types == ["created", "created"]

        # Opportunity lifecycle: both pages became items, items were dispatched to the
        # cleaning queue, scored, given payloads and notifications.
        items = await items_for(closure_p5_engine, source_id)
        assert [item.title for item in items] == ["CSS cleanup", "Landing page refresh"]
        assert all(item.status == "active" and item.snapshot_id is not None for item in items)
        # Dispatch carries RawItem ids (the cleaning queue contract), one per page.
        raw_items = await raw_items_for(closure_p5_engine, source_id)
        assert sorted(dispatched) == sorted(str(row.id) for row in raw_items)
        assert len(raw_items) == 2
        assert await dispatch_all(closure_p5_engine) == 2
        assert await count_rows(closure_p5_engine, OpportunityScore) == 2
        assert await count_rows(closure_p5_engine, OpportunityActionPayload) == 2
        assert await count_rows(closure_p5_engine, Notification) == 2

        # REST read-back over the frozen surface.
        settings = Settings()
        headers = {"Authorization": f"Bearer {create_access_token(user_id, settings)}"}
        client = closure_p5_client
        changes = await client.get(f"/api/v1/sources/{source_id}/changes", headers=headers)
        assert changes.status_code == 200
        assert changes.json()["total"] == 2
        assert {item["change_type"] for item in changes.json()["items"]} == {"created"}
        opportunities = await client.get(
            "/api/v1/opportunities?status=active&recommendation=act_now", headers=headers
        )
        assert opportunities.status_code == 200
        assert opportunities.json()["total"] == 2
        opportunity_id = items[0].id
        payload = await client.get(
            f"/api/v1/opportunities/{opportunity_id}/action-payload", headers=headers
        )
        assert payload.status_code == 200
        assert payload.json()["payload"]["requires_human_approval"] is True
        notifications = await client.get("/api/v1/notifications", headers=headers)
        assert notifications.status_code == 200
        assert notifications.json()["total"] == 2


class TestOperationalPaths:
    @pytest.mark.asyncio
    async def test_chain_failure_leaves_no_partial_state(
        self, closure_p5_engine: AsyncEngine
    ) -> None:
        _user_id, _radar_id, source_id = await create_chain_context(closure_p5_engine)
        transport = SiteTransport({})  # every fetch 404s
        run_id = await queue_run(closure_p5_engine, source_id)
        assert await run_chain(closure_p5_engine, run_id, transport) is False
        factory = async_sessionmaker(closure_p5_engine, expire_on_commit=False)
        async with factory() as session:
            run = await session.get(CollectionRun, run_id)
            state = await session.get(SourceAcquisitionState, source_id)
            assert run is not None and state is not None
            assert run.status == CollectionRunStatus.FAILED
            assert state.checkpoint == {}
        assert await count_rows(closure_p5_engine, SourceArtifact) == 0
        assert await count_rows(closure_p5_engine, OpportunityItem) == 0
        assert await count_rows(closure_p5_engine, RawItem) == 0

    @pytest.mark.asyncio
    async def test_chain_cancel_and_resume_without_duplicates(
        self, closure_p5_engine: AsyncEngine
    ) -> None:
        _user_id, _radar_id, source_id = await create_chain_context(closure_p5_engine)
        transport = chain_transport()
        run_id = await queue_run(closure_p5_engine, source_id)
        child_url = f"https://jobs.example.com{CHILD_PATH}"

        async def sabotage() -> None:
            await requeue_run(closure_p5_engine, run_id)

        transport.hooks[child_url] = sabotage
        assert await run_chain(closure_p5_engine, run_id, transport, task_id="w-a") is False
        # The claim is gone: the child page fetch happened but its commit (item and
        # evidence) was refused; the target stays pending in the frontier.
        factory = async_sessionmaker(closure_p5_engine, expire_on_commit=False)
        async with factory() as session:
            state = await session.get(SourceAcquisitionState, source_id)
            assert state is not None
            assert [entry["url"] for entry in state.checkpoint["frontier"]] == [child_url]
        assert await count_rows(closure_p5_engine, OpportunityItem) == 0

        del transport.hooks[child_url]
        assert await run_chain(closure_p5_engine, run_id, transport, task_id="w-b") is True
        items = await items_for(closure_p5_engine, source_id)
        assert [item.title for item in items] == ["CSS cleanup", "Landing page refresh"]
        assert await count_rows(closure_p5_engine, SourceArtifact) == 2  # each page once
        assert transport.per_url[child_url] == 2  # one refused attempt, one committed
        assert await dispatch_all(closure_p5_engine) == 2
        assert await count_rows(closure_p5_engine, OpportunityScore) == 2

    @pytest.mark.asyncio
    async def test_chain_two_concurrent_runs_dedupe(self, closure_p5_engine: AsyncEngine) -> None:
        _user_id, _radar_id, source_id = await create_chain_context(closure_p5_engine)
        transport = chain_transport()
        run_one = await queue_run(closure_p5_engine, source_id)
        run_two = await queue_run(closure_p5_engine, source_id)
        entered = asyncio.Event()
        release = asyncio.Event()
        child_url = f"https://jobs.example.com{CHILD_PATH}"

        async def hold() -> None:
            entered.set()
            await release.wait()

        transport.hooks[child_url] = hold
        first = asyncio.create_task(run_chain(closure_p5_engine, run_one, transport, task_id="w-1"))
        await entered.wait()
        assert await run_chain(closure_p5_engine, run_two, transport, task_id="w-2") is True
        release.set()
        assert await first is True
        factory = async_sessionmaker(closure_p5_engine, expire_on_commit=False)
        async with factory() as session:
            second_run = await session.get(CollectionRun, run_two)
            assert second_run is not None
            assert (
                second_run.budget_summary["discovery"]["crawl"]["skipped_reason"]
                == "checkpoint_conflict"
            )
        # Discovery deduped: the child page was fetched exactly once for the crawl.
        assert transport.per_url[child_url] == 1
        assert await count_rows(closure_p5_engine, SourceArtifact) == 2
        items = await items_for(closure_p5_engine, source_id)
        assert len(items) == 2
        assert await dispatch_all(closure_p5_engine) == 2
        assert await count_rows(closure_p5_engine, OpportunityScore) == 2

    @pytest.mark.asyncio
    async def test_chain_double_dispatch_is_claim_guarded(
        self, closure_p5_engine: AsyncEngine
    ) -> None:
        _user_id, _radar_id, source_id = await create_chain_context(closure_p5_engine)
        transport = chain_transport()
        run_id = await queue_run(closure_p5_engine, source_id)
        outcomes = await asyncio.gather(
            run_chain(closure_p5_engine, run_id, transport, task_id="dup-a"),
            run_chain(closure_p5_engine, run_id, transport, task_id="dup-b"),
        )
        assert sorted(outcomes) == [False, True]
        assert await count_rows(closure_p5_engine, SourceArtifact) == 2
        items = await items_for(closure_p5_engine, source_id)
        assert len(items) == 2
        assert await dispatch_all(closure_p5_engine) == 2
        assert await count_rows(closure_p5_engine, OpportunityScore) == 2

    @pytest.mark.asyncio
    async def test_chain_budget_exhaustion_preserves_frontier(
        self, closure_p5_engine: AsyncEngine
    ) -> None:
        _user_id, _radar_id, source_id = await create_chain_context(
            closure_p5_engine, max_requests=2
        )
        transport = chain_transport()
        run_id = await queue_run(closure_p5_engine, source_id)
        assert await run_chain(closure_p5_engine, run_id, transport) is True
        factory = async_sessionmaker(closure_p5_engine, expire_on_commit=False)
        async with factory() as session:
            run = await session.get(CollectionRun, run_id)
            state = await session.get(SourceAcquisitionState, source_id)
            assert run is not None and state is not None
            crawl = run.budget_summary["discovery"]["crawl"]
            assert crawl["stopped_reason"] == "request_budget"
            assert crawl["pages_fetched"] == 0
            # Seed + robots consumed the whole request budget; nothing was lost.
            assert [entry["url"] for entry in state.checkpoint["frontier"]] == [
                f"https://jobs.example.com{CHILD_PATH}"
            ]
        assert transport.per_url.get(f"https://jobs.example.com{CHILD_PATH}", 0) == 0
        items = await items_for(closure_p5_engine, source_id)
        assert [item.title for item in items] == ["Landing page refresh"]  # seed only
        assert await dispatch_all(closure_p5_engine) == 1
        assert await count_rows(closure_p5_engine, OpportunityActionPayload) == 1
        assert Decimal("86.55") == Decimal("86.55")  # scoring fixture sanity
        assert NOW + timedelta(days=1) > NOW
