"""ACQ-1 closure Phase 2 acceptance matrix (docs/71 §Phase 2, ADR-039).

WP-5 complete fetch execution on the production path (no selector patching):

2.1 frontier consumption — discovered pages fetched through a real ``SafeFetcher``
    (deterministic local transports only), one attempt row per page;
2.2 robots/domain policy — robots.txt fetched and enforced per ``robots_mode``,
    Crawl-delay executed through the site gate;
2.3 per-hop re-checks — redirects re-validated against network/site/scope policy
    before any transmission;
2.4 bounded traversal — pages/requests/bytes/time accumulate across pages and stop
    before exceeding; depth caps span crawl layers;
2.5 cancel/recovery — claim loss stops the loop; crash resume neither re-fetches
    committed pages nor drops pending targets;
2.6 concurrency — two runs on one source crawl each target at most once.
"""

from __future__ import annotations

import asyncio
import os
from collections import Counter
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.models.entities import (
    AcquisitionAttempt,
    AcquisitionMode,
    BackendName,
    CollectionRun,
    CollectionRunStatus,
    CollectionTriggerType,
    DiscoveryMode,
    Source,
    SourceAcquisitionState,
    SourceType,
    User,
)
from app.models.evidence import AcquisitionSnapshot, ChangeEvent
from app.schemas.resources import AcquisitionProfileV1, RobotsMode
from app.services.acquisition_policy import EffectiveResourceBudget
from app.services.acquisition_route import execute_route_run
from app.services.acquisition_run_repository import SqlAlchemyAcquisitionRunRepository
from app.services.discovery_pages import budget_gap
from app.services.native_acquisition import NativeAcquisitionBackend, SafeCrawlTransport
from app.services.safe_fetcher import SafeFetcher, WireResponse
from app.services.site_gate import SiteGate

TABLES = (
    "notifications, ai_usage_records, opportunity_action_payloads, opportunity_scores, "
    "opportunities, change_events, acquisition_snapshots, source_artifacts, "
    "acquisition_attempts, source_acquisition_states, document_chunks, bookmarks, analyses, "
    "documents, raw_items, radar_sources, collection_runs, sources, radars, refresh_tokens, users"
)
PUBLIC_IP = "93.184.216.34"
SEED = "https://example.com/guide/start.html"
SEED_PATH = "/guide/start.html"


async def public_resolver(_hostname: str) -> list[str]:
    return [PUBLIC_IP]


def page(*links: str, marker: str = "Crawl closure page") -> bytes:
    body = f"<html><head><title>{marker}</title></head><body><main><p>"
    body += f"{marker} deterministic acceptable extraction content. " * 40
    body += "</p>"
    for link in links:
        body += f'<a href="{link}">Read the related chapter</a>'
    body += "</main></body></html>"
    return body.encode()


class PageMap:
    """Deterministic multi-URL transport: pages, robots, hooks, request accounting."""

    def __init__(
        self,
        pages: dict[str, Any],
        *,
        robots: str | int = 404,
    ) -> None:
        self.pages = pages
        self.robots = robots
        self.requests: list[str] = []
        self.per_url: Counter[str] = Counter()
        self.hooks: dict[str, Callable[[], Awaitable[None]]] = {}

    async def __call__(self, *, url: str, **_kwargs: Any) -> WireResponse:
        self.requests.append(url)
        self.per_url[url] += 1
        hook = self.hooks.get(url)
        if hook is not None:
            await hook()
        path = url.split("example.com", 1)[-1] or "/"
        if path == "/robots.txt":
            if isinstance(self.robots, int):
                return WireResponse(self.robots, {"content-type": "text/plain"}, b"")
            return WireResponse(
                200, {"content-type": "text/plain; charset=utf-8"}, self.robots.encode()
            )
        entry = self.pages.get(path)
        if entry is None:
            return WireResponse(404, {"content-type": "text/html"}, b"")
        if isinstance(entry, tuple) and entry[0] == "redirect":
            return WireResponse(302, {"location": str(entry[1])}, b"")
        if isinstance(entry, tuple) and entry[0] == "status":
            return WireResponse(int(entry[1]), {"content-type": "text/html"}, b"")
        return WireResponse(200, {"content-type": "text/html; charset=utf-8"}, bytes(entry))


def backend_with(transport: PageMap) -> NativeAcquisitionBackend:
    return NativeAcquisitionBackend(
        fetcher=SafeFetcher(resolver=public_resolver, transport=transport)
    )


def crawl_transport(transport: PageMap) -> SafeCrawlTransport:
    return SafeCrawlTransport(SafeFetcher(resolver=public_resolver, transport=transport))


class DelayRecorder:
    """Records site-gate sleeps without waiting; the gate logic still executes."""

    def __init__(self) -> None:
        self.delays_ms: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.delays_ms.append(seconds * 1000)


def make_profile(
    *,
    max_pages: int = 6,
    max_requests: int = 30,
    max_depth: int = 1,
    max_total_bytes: int = 52_428_800,
    robots_mode: RobotsMode = RobotsMode.RESPECT,
) -> AcquisitionProfileV1:
    profile = AcquisitionProfileV1()
    profile.resource_budget.max_pages = max_pages
    profile.resource_budget.max_requests = max_requests
    profile.resource_budget.max_depth = max_depth
    profile.resource_budget.max_total_bytes = max_total_bytes
    profile.site_policy.robots_mode = robots_mode
    return profile


async def create_source(
    engine: AsyncEngine,
    *,
    profile: AcquisitionProfileV1 | None = None,
    discovery_mode: DiscoveryMode = DiscoveryMode.SAME_DOMAIN,
    url: str = SEED,
) -> UUID:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User(
            id=uuid4(),
            email=f"closure-p2-{uuid4()}@example.com",
            password_hash="synthetic",  # noqa: S106 - isolated database fixture
            display_name="Closure P2",
        )
        source = Source(
            id=uuid4(),
            user_id=user.id,
            name="Closure P2 Source",
            source_type=SourceType.URL,
            url=url,
            normalized_url=url,
            acquisition_mode=AcquisitionMode.AUTO,
            discovery_mode=discovery_mode,
            acquisition_profile=(profile or make_profile()).storage_dict(),
        )
        session.add(user)
        await session.flush()
        session.add(source)
        await session.flush()
        session.add(SourceAcquisitionState(source_id=source.id))
        await session.commit()
        return source.id


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
    transport: PageMap,
    *,
    site_gate: SiteGate | None = None,
    task_id: str = "closure-p2",
) -> Any:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return execute_route_run(
        SqlAlchemyAcquisitionRunRepository(factory),
        run_id,
        backends={BackendName.NATIVE_HTTP: backend_with(transport)},
        task_id=task_id,
        site_gate=site_gate,
        discovery_transport=crawl_transport(transport),
    )


async def load_run(engine: AsyncEngine, run_id: UUID) -> CollectionRun:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        run = await session.get(CollectionRun, run_id)
        assert run is not None
        return run


async def load_attempts(engine: AsyncEngine, run_id: UUID) -> list[AcquisitionAttempt]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        return list(
            (
                await session.scalars(
                    select(AcquisitionAttempt)
                    .where(AcquisitionAttempt.run_id == run_id)
                    .order_by(AcquisitionAttempt.ordinal.asc())
                )
            ).all()
        )


async def load_state(engine: AsyncEngine, source_id: UUID) -> SourceAcquisitionState:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        state = await session.get(SourceAcquisitionState, source_id)
        assert state is not None
        return state


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


@pytest.fixture
async def closure_p2_engine() -> AsyncEngine:
    database_url = os.environ["TEST_DATABASE_URL"]
    assert "_test" in database_url.rsplit("/", maxsplit=1)[-1]
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    yield engine
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    await engine.dispose()


def frontier_urls(state: SourceAcquisitionState) -> set[str]:
    return {str(entry["url"]) for entry in state.checkpoint.get("frontier", [])}


A_PAGE = page(marker="Alpha chapter")
B_PAGE = page(marker="Beta chapter")
C_PAGE = page(marker="Gamma chapter")
SEED_BODY = page(
    "https://example.com/guide/a.html",
    "https://example.com/guide/b.html",
    "https://example.com/guide/c.html",
    marker="Seed guide",
)
THREE_PAGES = {"/guide/a.html": A_PAGE, "/guide/b.html": B_PAGE, "/guide/c.html": C_PAGE}


class TestCrawlConsumption:
    @pytest.mark.asyncio
    async def test_crawl_consumes_frontier_through_real_fetcher(
        self, closure_p2_engine: AsyncEngine
    ) -> None:
        source_id = await create_source(closure_p2_engine)
        run_id = await queue_run(closure_p2_engine, source_id)
        transport = PageMap({SEED_PATH: SEED_BODY, **THREE_PAGES})
        assert await run_once(closure_p2_engine, run_id, transport) is True

        run = await load_run(closure_p2_engine, run_id)
        state = await load_state(closure_p2_engine, source_id)
        attempts = await load_attempts(closure_p2_engine, run_id)
        assert run.status == CollectionRunStatus.SUCCEEDED
        assert run.fetched_count == 4  # seed + three crawled pages
        assert attempts[0].ordinal == 1 and attempts[0].requested_url == SEED
        crawl_rows = attempts[1:]
        assert [row.requested_url for row in crawl_rows] == [
            "https://example.com/guide/a.html",
            "https://example.com/guide/b.html",
            "https://example.com/guide/c.html",
        ]
        assert all(row.status.value == "succeeded" for row in crawl_rows)
        assert all(row.decision_version == "discovery-crawl-v1" for row in crawl_rows)
        assert all(row.backend == BackendName.NATIVE_HTTP for row in crawl_rows)
        assert all(row.budget_used["pages"] == 1 for row in crawl_rows)
        # Every crawl fetch was issued through the shared SafeFetcher transport.
        assert transport.per_url["https://example.com/guide/a.html"] == 1
        assert transport.per_url["https://example.com/guide/b.html"] == 1
        assert transport.per_url["https://example.com/guide/c.html"] == 1
        assert transport.per_url[f"{SEED.split('/guide')[0]}/robots.txt"] == 1
        assert frontier_urls(state) == set()
        assert state.checkpoint["counters"]["crawled"] == 3
        crawl = run.budget_summary["discovery"]["crawl"]
        assert crawl["pages_fetched"] == 3
        assert crawl["complete"] is True
        assert crawl["stopped_reason"] == "frontier_empty"
        assert crawl["requests_used"] == 4  # robots + three pages

    @pytest.mark.asyncio
    async def test_recrawl_classifies_unchanged_without_false_removals(
        self, closure_p2_engine: AsyncEngine
    ) -> None:
        source_id = await create_source(closure_p2_engine)
        transport = PageMap({SEED_PATH: SEED_BODY, **THREE_PAGES})
        first = await queue_run(closure_p2_engine, source_id)
        assert await run_once(closure_p2_engine, first, transport) is True
        second = await queue_run(closure_p2_engine, source_id)
        assert await run_once(closure_p2_engine, second, transport) is True

        factory = async_sessionmaker(closure_p2_engine, expire_on_commit=False)
        async with factory() as session:
            events = list((await session.scalars(select(ChangeEvent.change_type))).all())
            snapshot_count = await session.scalar(
                select(func.count()).select_from(AcquisitionSnapshot)
            )
        # Run one observed seed + three crawled pages; the frontier is consumed once
        # per target (docs/61 §7), so the rerun re-observes only the seed.
        assert sorted(events) == ["created"] * 4 + ["unchanged"]
        assert "removed" not in events
        assert snapshot_count == 4  # content never changed; no extra versions
        second_run = await load_run(closure_p2_engine, second)
        assert second_run.budget_summary["discovery"]["crawl"]["pages_fetched"] == 0


class TestRobotsPolicy:
    @pytest.mark.asyncio
    async def test_robots_disallow_skips_target_and_delay_executes(
        self, closure_p2_engine: AsyncEngine
    ) -> None:
        source_id = await create_source(closure_p2_engine)
        run_id = await queue_run(closure_p2_engine, source_id)
        robots = "User-agent: FlowTracer-Alpha\nDisallow: /guide/b.html\nCrawl-delay: 2\n"
        transport = PageMap({SEED_PATH: SEED_BODY, **THREE_PAGES}, robots=robots)
        recorder = DelayRecorder()
        gate = SiteGate(sleep=recorder)
        assert await run_once(closure_p2_engine, run_id, transport, site_gate=gate) is True

        run = await load_run(closure_p2_engine, run_id)
        state = await load_state(closure_p2_engine, source_id)
        assert transport.per_url["https://example.com/guide/b.html"] == 0
        assert transport.per_url["https://example.com/guide/a.html"] == 1
        assert transport.per_url["https://example.com/guide/c.html"] == 1
        crawl = run.budget_summary["discovery"]["crawl"]
        assert crawl["robots_skipped"] == 1
        assert crawl["robots"]["https://example.com"] == "fetched"
        # Robots Crawl-delay: 2 forces the discovered-page spacing above the RPM floor.
        assert max(recorder.delays_ms) >= 1900
        # The denied target keeps its frontier slot for a future policy change.
        assert "https://example.com/guide/b.html" in frontier_urls(state)

    @pytest.mark.asyncio
    async def test_robots_availability_modes(self, closure_p2_engine: AsyncEngine) -> None:
        cases = [
            (404, RobotsMode.RESPECT, True),
            (404, RobotsMode.DENY_IF_UNAVAILABLE, False),
            (503, RobotsMode.RESPECT, True),
            (503, RobotsMode.DENY_IF_UNAVAILABLE, False),
        ]
        for robots_status, mode, crawl_allowed in cases:
            source_id = await create_source(
                closure_p2_engine, profile=make_profile(robots_mode=mode)
            )
            run_id = await queue_run(closure_p2_engine, source_id)
            transport = PageMap({SEED_PATH: SEED_BODY, **THREE_PAGES}, robots=robots_status)
            assert await run_once(closure_p2_engine, run_id, transport) is True
            run = await load_run(closure_p2_engine, run_id)
            state = await load_state(closure_p2_engine, source_id)
            crawl = run.budget_summary["discovery"]["crawl"]
            fetched = transport.per_url["https://example.com/guide/a.html"]
            if crawl_allowed:
                assert fetched == 1, (robots_status, mode)
                assert crawl["complete"] is True
            else:
                assert fetched == 0, (robots_status, mode)
                assert crawl["stopped_reason"] == "robots_unavailable"
                assert crawl["pages_fetched"] == 0
                assert frontier_urls(state) == {
                    "https://example.com/guide/a.html",
                    "https://example.com/guide/b.html",
                    "https://example.com/guide/c.html",
                }


class TestPerHopRechecks:
    @pytest.mark.asyncio
    async def test_redirect_is_rechecked_against_scope_and_ssrf(
        self, closure_p2_engine: AsyncEngine
    ) -> None:
        source_id = await create_source(closure_p2_engine)
        run_id = await queue_run(closure_p2_engine, source_id)
        transport = PageMap(
            {
                SEED_PATH: SEED_BODY,
                "/guide/a.html": ("redirect", "https://elsewhere.example.org/x.html"),
                "/guide/b.html": B_PAGE,
                "/guide/c.html": ("redirect", "http://127.0.0.1/metadata"),
            }
        )
        assert await run_once(closure_p2_engine, run_id, transport) is True

        run = await load_run(closure_p2_engine, run_id)
        attempts = await load_attempts(closure_p2_engine, run_id)
        by_url = {row.requested_url: row for row in attempts}
        assert by_url["https://example.com/guide/a.html"].status.value == "failed"
        assert by_url["https://example.com/guide/a.html"].error_code == "site_policy_denied"
        assert by_url["https://example.com/guide/c.html"].status.value == "failed"
        assert by_url["https://example.com/guide/c.html"].error_code == "network_policy_denied"
        # The out-of-scope and loopback hops were refused before any transmission.
        assert not any("elsewhere.example.org" in url for url in transport.requests)
        assert not any("127.0.0.1" in url for url in transport.requests)
        assert by_url["https://example.com/guide/b.html"].status.value == "succeeded"
        assert run.status == CollectionRunStatus.PARTIAL
        assert run.failed_count == 2
        crawl = run.budget_summary["discovery"]["crawl"]
        assert crawl["pages_failed"] == 2
        assert crawl["complete"] is False


class TestBoundedTraversal:
    @pytest.mark.asyncio
    async def test_page_budget_is_cumulative_and_resumes(
        self, closure_p2_engine: AsyncEngine
    ) -> None:
        source_id = await create_source(closure_p2_engine, profile=make_profile(max_pages=2))
        transport = PageMap({SEED_PATH: SEED_BODY, **THREE_PAGES})
        first = await queue_run(closure_p2_engine, source_id)
        assert await run_once(closure_p2_engine, first, transport) is True
        run_one = await load_run(closure_p2_engine, first)
        state = await load_state(closure_p2_engine, source_id)
        crawl_one = run_one.budget_summary["discovery"]["crawl"]
        assert crawl_one["pages_fetched"] == 1  # seed already used one page slot
        assert crawl_one["stopped_reason"] == "page_budget"
        assert crawl_one["requests_used"] == 2  # robots + one page
        assert transport.per_url["https://example.com/guide/a.html"] == 1
        assert "https://example.com/guide/a.html" not in frontier_urls(state)
        assert len(frontier_urls(state)) == 2

        second = await queue_run(closure_p2_engine, source_id)
        assert await run_once(closure_p2_engine, second, transport) is True
        crawl_two = (await load_run(closure_p2_engine, second)).budget_summary["discovery"]["crawl"]
        assert crawl_two["pages_fetched"] == 1
        assert transport.per_url["https://example.com/guide/a.html"] == 1  # no refetch
        assert transport.per_url["https://example.com/guide/b.html"] == 1
        assert transport.per_url["https://example.com/guide/c.html"] == 0

    @pytest.mark.asyncio
    async def test_request_budget_stops_before_exceeding(
        self, closure_p2_engine: AsyncEngine
    ) -> None:
        profile = make_profile(max_requests=2)  # seed + robots consume the ledger
        source_id = await create_source(closure_p2_engine, profile=profile)
        run_id = await queue_run(closure_p2_engine, source_id)
        transport = PageMap({SEED_PATH: SEED_BODY, **THREE_PAGES})
        assert await run_once(closure_p2_engine, run_id, transport) is True
        run = await load_run(closure_p2_engine, run_id)
        crawl = run.budget_summary["discovery"]["crawl"]
        assert crawl["stopped_reason"] == "request_budget"
        assert crawl["pages_fetched"] == 0
        assert transport.per_url["https://example.com/guide/a.html"] == 0

    @pytest.mark.asyncio
    async def test_byte_budget_accumulates_across_pages(
        self, closure_p2_engine: AsyncEngine
    ) -> None:
        # The cap funds the seed body plus one page: the second page is refused before
        # its request is issued. The mid-read hard cap (budget tripped *during* the body
        # read) rides the same FetchSession and is evidenced by the Phase 0 suite on
        # the real reader path.
        profile = make_profile(max_total_bytes=len(SEED_BODY) + len(A_PAGE))
        source_id = await create_source(closure_p2_engine, profile=profile)
        run_id = await queue_run(closure_p2_engine, source_id)
        transport = PageMap({SEED_PATH: SEED_BODY, **THREE_PAGES})
        assert await run_once(closure_p2_engine, run_id, transport) is True
        run = await load_run(closure_p2_engine, run_id)
        crawl = run.budget_summary["discovery"]["crawl"]
        assert crawl["pages_fetched"] == 1
        assert crawl["pages_failed"] == 0
        assert crawl["stopped_reason"] == "byte_budget"
        assert crawl["bytes_received"] == len(A_PAGE)
        assert transport.per_url["https://example.com/guide/b.html"] == 0
        assert transport.per_url["https://example.com/guide/c.html"] == 0

    def test_budget_gap_boundaries(self) -> None:
        budget = EffectiveResourceBudget(
            max_requests=5,
            max_pages=3,
            max_depth=1,
            max_duration_seconds=60,
            max_concurrency=1,
            max_browser_pages=0,
            max_retries_per_target=1,
            max_total_bytes=100,
        )
        assert (
            budget_gap(pages_used=2, requests_used=4, bytes_used=99, seconds_left=1, budget=budget)
            is None
        )
        assert (
            budget_gap(pages_used=3, requests_used=1, bytes_used=0, seconds_left=1, budget=budget)
            == "page_budget"
        )
        assert (
            budget_gap(pages_used=0, requests_used=5, bytes_used=0, seconds_left=1, budget=budget)
            == "request_budget"
        )
        assert (
            budget_gap(pages_used=0, requests_used=0, bytes_used=100, seconds_left=1, budget=budget)
            == "byte_budget"
        )
        assert (
            budget_gap(pages_used=0, requests_used=0, bytes_used=0, seconds_left=0, budget=budget)
            == "time_budget"
        )
        assert (
            budget_gap(
                pages_used=0, requests_used=0, bytes_used=0, seconds_left=None, budget=budget
            )
            is None
        )

    @pytest.mark.asyncio
    async def test_depth_cap_spans_crawl_layers(self, closure_p2_engine: AsyncEngine) -> None:
        profile = make_profile(max_depth=2, max_pages=6)
        deep_one = page("/guide/deep/two.html", marker="Deep one")
        seed_body = page("https://example.com/guide/a.html", marker="Depth seed")
        source_id = await create_source(closure_p2_engine, profile=profile)
        run_id = await queue_run(closure_p2_engine, source_id)
        transport = PageMap(
            {
                SEED_PATH: seed_body,
                "/guide/a.html": deep_one,
                "/guide/deep/two.html": page(marker="Deep two"),
            }
        )
        assert await run_once(closure_p2_engine, run_id, transport) is True
        state = await load_state(closure_p2_engine, source_id)
        # Layer 2 was crawled; nothing beyond the depth cap was planned or fetched.
        assert transport.per_url["https://example.com/guide/deep/two.html"] == 1
        assert frontier_urls(state) == set()
        run = await load_run(closure_p2_engine, run_id)
        assert run.budget_summary["discovery"]["crawl"]["pages_fetched"] == 2


class TestCancelAndRecovery:
    @pytest.mark.asyncio
    async def test_claim_loss_stops_the_crawl(self, closure_p2_engine: AsyncEngine) -> None:
        source_id = await create_source(closure_p2_engine)
        run_id = await queue_run(closure_p2_engine, source_id)
        transport = PageMap({SEED_PATH: SEED_BODY, **THREE_PAGES})

        async def sabotage() -> None:
            await requeue_run(closure_p2_engine, run_id)

        transport.hooks["https://example.com/guide/b.html"] = sabotage
        assert await run_once(closure_p2_engine, run_id, transport) is False
        attempts = await load_attempts(closure_p2_engine, run_id)
        # Page a committed before the claim vanished; b's commit was refused; c untouched.
        assert [row.requested_url for row in attempts] == ["https://example.com/guide/a.html"]
        assert transport.per_url["https://example.com/guide/c.html"] == 0
        state = await load_state(closure_p2_engine, source_id)
        assert frontier_urls(state) == {
            "https://example.com/guide/b.html",
            "https://example.com/guide/c.html",
        }
        run = await load_run(closure_p2_engine, run_id)
        assert run.status == CollectionRunStatus.QUEUED  # requeued for another worker

    @pytest.mark.asyncio
    async def test_crash_resume_no_refetch_no_loss(self, closure_p2_engine: AsyncEngine) -> None:
        source_id = await create_source(closure_p2_engine)
        run_id = await queue_run(closure_p2_engine, source_id)
        crashing = PageMap({SEED_PATH: SEED_BODY, **THREE_PAGES})

        async def explode() -> None:
            raise RuntimeError("worker crashed mid-crawl")

        crashing.hooks["https://example.com/guide/b.html"] = explode
        assert await run_once(closure_p2_engine, run_id, crashing) is False
        assert (await load_run(closure_p2_engine, run_id)).status == CollectionRunStatus.FAILED

        await requeue_run(closure_p2_engine, run_id)
        resumed = PageMap({SEED_PATH: SEED_BODY, **THREE_PAGES})
        assert await run_once(closure_p2_engine, run_id, resumed, task_id="worker-two") is True
        # Committed page a was not re-fetched; pending b and c were consumed once.
        assert crashing.per_url["https://example.com/guide/a.html"] == 1
        assert resumed.per_url["https://example.com/guide/a.html"] == 0
        assert resumed.per_url["https://example.com/guide/b.html"] == 1
        assert resumed.per_url["https://example.com/guide/c.html"] == 1
        state = await load_state(closure_p2_engine, source_id)
        assert frontier_urls(state) == set()
        ordinals = [row.ordinal for row in await load_attempts(closure_p2_engine, run_id)]
        assert len(ordinals) == len(set(ordinals))  # (run_id, ordinal) stays unique

    @pytest.mark.asyncio
    async def test_two_concurrent_runs_crawl_each_target_once(
        self, closure_p2_engine: AsyncEngine
    ) -> None:
        source_id = await create_source(closure_p2_engine)
        run_one = await queue_run(closure_p2_engine, source_id)
        run_two = await queue_run(closure_p2_engine, source_id)
        entered = asyncio.Event()
        release = asyncio.Event()
        transport = PageMap({SEED_PATH: SEED_BODY, **THREE_PAGES})

        async def hold() -> None:
            entered.set()
            await release.wait()

        transport.hooks["https://example.com/guide/a.html"] = hold
        first = asyncio.create_task(run_once(closure_p2_engine, run_one, transport, task_id="w-a"))
        await entered.wait()
        second_ok = await run_once(closure_p2_engine, run_two, transport, task_id="w-b")
        release.set()
        assert await first is True
        assert second_ok is True
        # The second run planned but bowed out of the crawl: it crawled nothing.
        run_two_row = await load_run(closure_p2_engine, run_two)
        crawl_two = run_two_row.budget_summary["discovery"]["crawl"]
        assert crawl_two["started"] is False
        assert crawl_two["skipped_reason"] == "checkpoint_conflict"
        assert transport.per_url["https://example.com/guide/a.html"] == 1
        assert transport.per_url["https://example.com/guide/b.html"] == 1
        assert transport.per_url["https://example.com/guide/c.html"] == 1
        assert transport.per_url["https://example.com/robots.txt"] == 1
        attempts_two = await load_attempts(closure_p2_engine, run_two)
        assert len(attempts_two) == 1  # seed only


class TestCrawlFailures:
    @pytest.mark.asyncio
    async def test_page_failure_records_attempt_and_partial_run(
        self, closure_p2_engine: AsyncEngine
    ) -> None:
        source_id = await create_source(closure_p2_engine)
        run_id = await queue_run(closure_p2_engine, source_id)
        transport = PageMap(
            {
                SEED_PATH: SEED_BODY,
                "/guide/a.html": A_PAGE,
                "/guide/b.html": ("status", 404),
                "/guide/c.html": C_PAGE,
            }
        )
        assert await run_once(closure_p2_engine, run_id, transport) is True
        run = await load_run(closure_p2_engine, run_id)
        attempts = await load_attempts(closure_p2_engine, run_id)
        by_url = {row.requested_url: row for row in attempts}
        failed = by_url["https://example.com/guide/b.html"]
        assert failed.status.value == "failed"
        assert failed.error_code == "http_error"
        assert failed.retry_count == 0
        assert run.status == CollectionRunStatus.PARTIAL
        assert run.failed_count == 1
        crawl = run.budget_summary["discovery"]["crawl"]
        assert crawl["pages_failed"] == 1
        assert crawl["pages_fetched"] == 2
        state = await load_state(closure_p2_engine, source_id)
        entry = next(
            entry
            for entry in state.checkpoint["frontier"]
            if entry["url"] == "https://example.com/guide/b.html"
        )
        assert entry["attempts"] == 1  # retryable on a later run
