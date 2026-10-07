"""WP-5 Controlled Discovery v1 acceptance matrix (ADR-035 / docs/61).

Covers: four-scope boundary escapes, deterministic scoring, site-path gate, hard caps
(depth/frontier/discovered), frontier dedup within and across runs, checkpoint
round-trip/recovery, link extraction hygiene, and the routed-run wiring (checkpoint
persistence + closed run summary) end to end against the isolated test database.
"""

from __future__ import annotations

import json
import os
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from app.models.entities import (
    AcquisitionMode,
    CollectionRun,
    CollectionRunStatus,
    CollectionTriggerType,
    DiscoveryMode,
    Source,
    SourceAcquisitionState,
    SourceType,
    User,
)
from app.schemas.resources import AcquisitionProfileV1
from app.services.acquisition_route import execute_route_run
from app.services.acquisition_run_repository import SqlAlchemyAcquisitionRunRepository
from app.services.acquisition_types import AcquisitionResult, FetchResponse
from app.services.discovery_frontier import checkpoint_view, plan_discovery
from app.services.discovery_links import extract_links
from app.services.discovery_policy import (
    directory_prefix,
    has_tracking_params,
    path_allowed,
    scope_allows,
    score_link,
)

TABLES = (
    "acquisition_attempts, source_acquisition_states, raw_items, collection_runs, sources, users"
)
SEED = "https://example.com/guide/start.html"
APPROVED = frozenset({"cdn.example.com"})

PAGE_BODY = (
    b"<html><head><title>Guide</title></head><body><main>"
    b"<p>" + b"Deterministic acceptable extraction content for discovery tests. " * 40 + b"</p>"
    b'<a href="https://example.com/guide/next.html">Read the next chapter</a>'
    b'<a href="https://example.com/guide/other.html?utm_source=feed">Tracked link</a>'
    b'<a href="https://cdn.example.com/asset.html">Approved asset page</a>'
    b'<a href="https://other.example.org/away.html">External page</a>'
    b'<a href="https://example.com/private/secret.html">Private area</a>'
    b'<a href="https://example.com/guide/next.html">Read the next chapter</a>'
    b"</main></body></html>"
)


def plan(
    *,
    body: bytes = PAGE_BODY,
    scope: DiscoveryMode = DiscoveryMode.SAME_DOMAIN,
    checkpoint: dict[str, Any] | None = None,
    approved: frozenset[str] = APPROVED,
    allow_paths: tuple[str, ...] = (),
    deny_paths: tuple[str, ...] = ("/private",),
    max_depth: int = 1,
    max_frontier_size: int = 500,
    max_discovered_urls: int = 15,
    min_score: int = 20,
) -> Any:
    return plan_discovery(
        seed_url=SEED,
        body=body,
        content_type="text/html; charset=utf-8",
        final_url=SEED,
        scope=scope,
        approved_domains=approved,
        allow_paths=allow_paths,
        deny_paths=deny_paths,
        checkpoint=checkpoint,
        max_depth=max_depth,
        max_frontier_size=max_frontier_size,
        max_discovered_urls=max_discovered_urls,
        min_score=min_score,
    )


class TestScopeBoundaries:
    def test_single_page_allows_only_seed(self) -> None:
        assert scope_allows(
            seed_url=SEED,
            target_url=SEED,
            scope=DiscoveryMode.SINGLE_PAGE,
            approved_domains=APPROVED,
        )
        assert not scope_allows(
            seed_url=SEED,
            target_url="https://example.com/guide/other.html",
            scope=DiscoveryMode.SINGLE_PAGE,
            approved_domains=APPROVED,
        )

    def test_same_path_prefix_boundary(self) -> None:
        assert scope_allows(
            seed_url=SEED,
            target_url="https://example.com/guide/deep/page.html",
            scope=DiscoveryMode.SAME_PATH,
            approved_domains=APPROVED,
        )
        assert not scope_allows(
            seed_url=SEED,
            target_url="https://example.com/other/page.html",
            scope=DiscoveryMode.SAME_PATH,
            approved_domains=APPROVED,
        )
        assert directory_prefix("/guide/start.html") == "/guide/"

    def test_same_domain_rejects_subdomains_and_siblings(self) -> None:
        assert scope_allows(
            seed_url=SEED,
            target_url="https://example.com/anything?q=1",
            scope=DiscoveryMode.SAME_DOMAIN,
            approved_domains=APPROVED,
        )
        for target in (
            "https://cdn.example.com/asset.html",
            "https://www.example.com/",
            "https://example.org/",
            "https://sub.example.com/",
        ):
            assert not scope_allows(
                seed_url=SEED,
                target_url=target,
                scope=DiscoveryMode.SAME_DOMAIN,
                approved_domains=APPROVED,
            )

    def test_approved_domains_uses_intersection(self) -> None:
        assert scope_allows(
            seed_url=SEED,
            target_url="https://cdn.example.com/asset.html",
            scope=DiscoveryMode.APPROVED_DOMAINS,
            approved_domains=APPROVED,
        )
        assert not scope_allows(
            seed_url=SEED,
            target_url="https://unapproved.example.net/x.html",
            scope=DiscoveryMode.APPROVED_DOMAINS,
            approved_domains=APPROVED,
        )

    def test_unsafe_shapes_always_denied(self) -> None:
        for target in (
            "ftp://example.com/x",
            "https://user:pass@example.com/x",
            "https://example.com:8443/x",
            "http://example.com:9999/x",
        ):
            assert not scope_allows(
                seed_url=SEED,
                target_url=target,
                scope=DiscoveryMode.APPROVED_DOMAINS,
                approved_domains=APPROVED,
            )

    def test_path_gate_deny_then_allow(self) -> None:
        assert not path_allowed("/private/x", allow_paths=(), deny_paths=("/private",))
        assert not path_allowed("/news/x", allow_paths=("/guide",), deny_paths=())
        assert path_allowed("/guide/x", allow_paths=("/guide",), deny_paths=())


class TestScoring:
    def test_deterministic_and_bounded(self) -> None:
        first = score_link(
            seed_url=SEED,
            target_url="https://example.com/guide/a.html",
            anchor_text="Read more",
            depth=1,
            allow_paths=(),
            query="",
        )
        second = score_link(
            seed_url=SEED,
            target_url="https://example.com/guide/a.html",
            anchor_text="Read more",
            depth=1,
            allow_paths=(),
            query="",
        )
        assert first == second == 40
        capped = score_link(
            seed_url=SEED,
            target_url="https://example.com/guide/a.html",
            anchor_text="Long anchor text here",
            depth=0,
            allow_paths=("/guide",),
            query="",
        )
        assert 0 <= capped <= 100
        assert capped == 50

    def test_penalties_and_bonuses(self) -> None:
        deep = score_link(
            seed_url=SEED,
            target_url="https://example.com/guide/a.html",
            anchor_text="Read more",
            depth=3,
            allow_paths=(),
            query="",
        )
        host_only = score_link(
            seed_url=SEED,
            target_url="https://example.com/other/a.html",
            anchor_text="Read more",
            depth=1,
            allow_paths=(),
            query="",
        )
        tracked = score_link(
            seed_url=SEED,
            target_url="https://example.com/guide/a.html?utm_source=x",
            anchor_text="Read more",
            depth=1,
            allow_paths=(),
            query="utm_source=x",
        )
        approved = score_link(
            seed_url=SEED,
            target_url="https://cdn.example.com/asset.html",
            anchor_text="Read more",
            depth=1,
            allow_paths=(),
            query="",
            approved_host=True,
        )
        assert deep == 0
        assert host_only == 25
        assert tracked == 30
        assert approved == 20
        assert has_tracking_params("utm_source=x&a=1")
        assert not has_tracking_params("page=2")


class TestFrontierPlanning:
    def test_depth_cap_zero_accepts_nothing(self) -> None:
        result = plan(max_depth=0)
        assert result.entries == []
        assert result.summary["accepted"] == 0
        assert result.summary["depth_cap"] == 0
        assert result.checkpoint["frontier"] == []

    def test_scope_filters_and_dedupe(self) -> None:
        result = plan(scope=DiscoveryMode.SAME_DOMAIN)
        urls = [entry["url"] for entry in result.entries]
        assert urls == [
            "https://example.com/guide/next.html",
            "https://example.com/guide/other.html?utm_source=feed",
        ]
        assert result.summary["links_found"] == 6
        assert result.summary["duplicates"] == 1
        assert result.summary["rejected_scope"] == 3
        assert result.summary["rejected_score"] == 0
        assert "https://other.example.org/away.html" not in urls
        assert all("/private/" not in url for url in urls)

    def test_frontier_cap_and_discovered_cap(self) -> None:
        capped = plan(max_frontier_size=1)
        assert len(capped.entries) == 1
        assert capped.summary["truncated"] is True
        surfaced = plan(max_discovered_urls=1)
        assert len(surfaced.entries) == 1
        assert surfaced.summary["accepted"] == 1

    def test_checkpoint_roundtrip_is_idempotent(self) -> None:
        first = plan()
        checkpoint = json.loads(json.dumps(first.checkpoint))
        second = plan(checkpoint=checkpoint)
        assert second.entries == []
        assert second.summary["accepted"] == 0
        # Six raw links: the two accepted earlier plus the in-page repeat are all seen now.
        assert second.summary["duplicates"] == 3
        seen, frontier, counters = checkpoint_view(checkpoint)
        assert len(seen) == len(first.entries)
        assert len(frontier) == len(first.entries)
        assert counters["accepted_total"] == len(first.entries)
        third = plan(checkpoint=second.checkpoint)
        assert third.entries == []

    def test_malformed_checkpoint_is_tolerated(self) -> None:
        result = plan(checkpoint={"seen": "not-a-list", "frontier": 5, "counters": []})
        assert len(result.entries) == 2
        assert result.checkpoint["version"] == 2

    def test_approved_domains_scope_includes_intersection(self) -> None:
        result = plan(scope=DiscoveryMode.APPROVED_DOMAINS)
        urls = {entry["url"] for entry in result.entries}
        assert "https://cdn.example.com/asset.html" in urls
        result_narrow = plan(scope=DiscoveryMode.APPROVED_DOMAINS, approved=frozenset())
        urls_narrow = {entry["url"] for entry in result_narrow.entries}
        assert "https://cdn.example.com/asset.html" not in urls_narrow


class TestLinkExtraction:
    def test_hygiene_and_limit(self) -> None:
        body = (
            b"<a href='/one' rel='nofollow'>One link</a>"
            b"<script>var x = '<a href=\"/two\">hidden</a>';</script>"
            b"<a href='/three'>Three!</a>"
        )
        links = extract_links(body, "text/html", "https://example.com/", limit=10)
        assert [link.url for link in links] == [
            "https://example.com/one",
            "https://example.com/three",
        ]
        assert links[0].nofollow is True
        bounded = extract_links(body, "text/html", "https://example.com/", limit=1)
        assert len(bounded) == 1


async def create_source(
    engine: AsyncEngine,
    *,
    discovery_mode: DiscoveryMode,
    profile: AcquisitionProfileV1 | None = None,
    url: str = SEED,
) -> UUID:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User(
            id=uuid4(),
            email=f"discovery-{uuid4()}@example.com",
            password_hash="synthetic",  # noqa: S106 - isolated database fixture
            display_name="Discovery",
        )
        source = Source(
            id=uuid4(),
            user_id=user.id,
            name="Discovery Source",
            source_type=SourceType.URL,
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


class StaticPage:
    def __init__(self, body: bytes = PAGE_BODY) -> None:
        self.body = body
        self.calls = 0

    async def acquire(self, request: Any) -> AcquisitionResult:
        self.calls += 1
        return AcquisitionResult(
            FetchResponse(request.target_url, "text/html; charset=utf-8", self.body),
            retry_count=0,
            budget_used={"requests": 1, "pages": 1, "bytes_received": len(self.body)},
        )


@pytest.fixture
async def discovery_engine() -> AsyncEngine:
    database_url = os.environ["TEST_DATABASE_URL"]
    assert "_test" in database_url.rsplit("/", maxsplit=1)[-1]
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    yield engine
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    await engine.dispose()


class TestRoutedDiscovery:
    @pytest.mark.asyncio
    async def test_routed_run_records_discovery_and_dedupes(
        self, discovery_engine: AsyncEngine
    ) -> None:
        from app.models.entities import BackendName

        profile = AcquisitionProfileV1()
        profile.resource_budget.max_depth = 1
        profile.resource_budget.max_pages = 3
        profile.site_policy.deny_paths = ["/private"]
        source_id = await create_source(
            discovery_engine, discovery_mode=DiscoveryMode.SAME_DOMAIN, profile=profile
        )
        factory = async_sessionmaker(discovery_engine, expire_on_commit=False)
        repository = SqlAlchemyAcquisitionRunRepository(factory)
        page = StaticPage()

        run_one = await queue_run(discovery_engine, source_id)
        ok_one = await execute_route_run(
            repository, run_one, backends={BackendName.NATIVE_HTTP: page}, task_id="w-1"
        )
        assert ok_one is True
        run_two = await queue_run(discovery_engine, source_id)
        ok_two = await execute_route_run(
            repository, run_two, backends={BackendName.NATIVE_HTTP: page}, task_id="w-2"
        )
        assert ok_two is True

        async with factory() as session:
            stored_one = await session.get(CollectionRun, run_one)
            stored_two = await session.get(CollectionRun, run_two)
            state = await session.get(SourceAcquisitionState, source_id)
            assert stored_one is not None and stored_two is not None and state is not None
            discovery_one = stored_one.budget_summary["discovery"]
            assert discovery_one["scope"] == "same_domain"
            assert discovery_one["accepted"] == 2
            assert discovery_one["duplicates"] == 1
            discovery_two = stored_two.budget_summary["discovery"]
            assert discovery_two["accepted"] == 0
            # The two accepted URLs plus the in-page repeat all hit the persisted seen set.
            assert discovery_two["duplicates"] == 3
            checkpoint = state.checkpoint
            assert checkpoint["version"] == 2
            assert len(checkpoint["frontier"]) == 2
            assert checkpoint["counters"]["accepted_total"] == 2
            urls = {entry["url"] for entry in checkpoint["frontier"]}
            assert urls == {
                "https://example.com/guide/next.html",
                "https://example.com/guide/other.html?utm_source=feed",
            }

    @pytest.mark.asyncio
    async def test_single_page_source_leaves_no_checkpoint(
        self, discovery_engine: AsyncEngine
    ) -> None:
        from app.models.entities import BackendName

        source_id = await create_source(discovery_engine, discovery_mode=DiscoveryMode.SINGLE_PAGE)
        factory = async_sessionmaker(discovery_engine, expire_on_commit=False)
        repository = SqlAlchemyAcquisitionRunRepository(factory)
        run_id = await queue_run(discovery_engine, source_id)
        assert (
            await execute_route_run(
                repository, run_id, backends={BackendName.NATIVE_HTTP: StaticPage()}, task_id="w-3"
            )
            is True
        )
        async with factory() as session:
            stored = await session.get(CollectionRun, run_id)
            state = await session.get(SourceAcquisitionState, source_id)
            assert stored is not None and state is not None
            assert "discovery" not in stored.budget_summary
            assert state.checkpoint == {}

    @pytest.mark.asyncio
    async def test_denied_and_tracking_paths_never_enter_frontier(
        self, discovery_engine: AsyncEngine
    ) -> None:
        from app.models.entities import BackendName

        profile = AcquisitionProfileV1()
        profile.resource_budget.max_depth = 1
        profile.resource_budget.max_pages = 3
        profile.site_policy.deny_paths = ["/private"]
        source_id = await create_source(
            discovery_engine,
            discovery_mode=DiscoveryMode.APPROVED_DOMAINS,
            profile=profile,
        )
        factory = async_sessionmaker(discovery_engine, expire_on_commit=False)
        repository = SqlAlchemyAcquisitionRunRepository(factory)
        run_id = await queue_run(discovery_engine, source_id)
        assert (
            await execute_route_run(
                repository, run_id, backends={BackendName.NATIVE_HTTP: StaticPage()}, task_id="w-4"
            )
            is True
        )
        async with factory() as session:
            state = await session.get(SourceAcquisitionState, source_id)
            stored = await session.get(CollectionRun, run_id)
            assert state is not None and stored is not None
            urls = {entry["url"] for entry in state.checkpoint["frontier"]}
            assert all("/private/" not in url for url in urls)
            assert "https://other.example.org/away.html" not in urls
            discovery = stored.budget_summary["discovery"]
            assert discovery["rejected_scope"] >= 2
