"""ACQ-1 closure Phase 0 acceptance matrix (docs/71 §Phase 0).

Covers the six independent-review fixes:

0.1 per-hop/retry request billing — redirects and retries count as real requests and
    a budget stops the request *before* it would exceed;
0.2 time and byte budgets enforced during execution (pre-request deadline checks,
    byte-capped reads, deadline-bounded retry backoff);
0.3 version rollback — classification against the last observed state covers
    ``A→B→A→A`` (final ``unchanged``, no repeated change report) and ``A→B→A→B``;
0.4 real crawl-delay / RPM spacing and per-host serialization executed per request;
0.5 opportunity filter set semantics (radar scope + EXISTS-based score filters);
0.6 legacy backfill advances through more than one batch.
"""

from __future__ import annotations

import asyncio
import os
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.models.entities import (
    AcquisitionMode,
    BackendName,
    CollectionRun,
    CollectionRunStatus,
    CollectionTriggerType,
    DiscoveryMode,
    Radar,
    RadarSource,
    RadarType,
    RawItem,
    RawItemStatus,
    ResourceStatus,
    Source,
    SourceAcquisitionState,
    SourceFamily,
    SourceType,
    User,
)
from app.models.evidence import AcquisitionSnapshot, ChangeEvent, SourceArtifact
from app.models.opportunity import OpportunityItem, OpportunityScore
from app.schemas.resources import AcquisitionProfileV1
from app.services.acquisition_route import execute_route_run
from app.services.acquisition_run_repository import SqlAlchemyAcquisitionRunRepository
from app.services.acquisition_types import (
    AcquisitionResult,
    AttemptBudget,
    CollectionError,
    FetchResponse,
    ParseResult,
    RawCandidate,
)
from app.services.change_tracking import backfill_source_evidence, record_version_evidence
from app.services.native_acquisition import NativeAcquisitionBackend
from app.services.opportunity_queries import list_opportunities
from app.services.safe_fetcher import (
    FetchSession,
    SafeFetcher,
    WireResponse,
    _decode_body,
    fetch_with_retries,
)
from app.services.site_gate import SiteGate

TABLES = (
    "notifications, ai_usage_records, opportunity_action_payloads, opportunity_scores, "
    "opportunities, change_events, acquisition_snapshots, source_artifacts, "
    "acquisition_attempts, source_acquisition_states, document_chunks, bookmarks, analyses, "
    "documents, raw_items, radar_sources, collection_runs, sources, radars, refresh_tokens, users"
)
NOW = datetime(2026, 10, 6, 6, 0, tzinfo=UTC)
PUBLIC_IP = "93.184.216.34"


async def public_resolver(_hostname: str) -> list[str]:
    return [PUBLIC_IP]


class RedirectChainTransport:
    """302 chain ending in an acceptable HTML page; counts issued requests."""

    def __init__(self, *, hops: int = 2, body: bytes | None = None) -> None:
        self.hops = hops
        self.calls = 0
        self.body = body or (
            b"<html><head><title>Final</title></head><body><main>"
            + b"Deterministic acceptable extraction content. " * 40
            + b"</main></body></html>"
        )

    async def __call__(self, *, url: str, **_kwargs: Any) -> WireResponse:
        self.calls += 1
        if self.calls <= self.hops:
            return WireResponse(302, {"location": f"https://example.com/step-{self.calls}"}, b"")
        return WireResponse(200, {"content-type": "text/html; charset=utf-8"}, self.body)


class FlakyTransport:
    """Always fails with a retryable 503; counts issued requests."""

    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, *, url: str, **_kwargs: Any) -> WireResponse:
        self.calls += 1
        return WireResponse(503, {"content-type": "text/html"}, b"")


class FlakyOnceTransport:
    """Fails once with a retryable 503, then serves an acceptable HTML page."""

    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, *, url: str, **_kwargs: Any) -> WireResponse:
        self.calls += 1
        if self.calls == 1:
            return WireResponse(503, {"content-type": "text/html"}, b"")
        return WireResponse(
            200,
            {"content-type": "text/html; charset=utf-8"},
            b"<html><head><title>Recovered</title></head><body><main>"
            + b"Deterministic acceptable extraction content. " * 40
            + b"</main></body></html>",
        )


class TestHopBilling:
    @pytest.mark.asyncio
    async def test_redirect_hops_count_as_real_requests(self) -> None:
        transport = RedirectChainTransport(hops=2)
        fetcher = SafeFetcher(resolver=public_resolver, transport=transport)
        session = FetchSession()
        response = await fetcher.fetch("https://example.com/start", SourceType.URL, session=session)
        assert response.redirects == 2
        assert session.requests_made == 3
        assert transport.calls == 3

    @pytest.mark.asyncio
    async def test_request_budget_stops_before_the_next_request(self) -> None:
        transport = RedirectChainTransport(hops=5)
        fetcher = SafeFetcher(resolver=public_resolver, transport=transport)
        session = FetchSession(max_requests=2)
        with pytest.raises(CollectionError) as exc:
            await fetcher.fetch("https://example.com/start", SourceType.URL, session=session)
        assert exc.value.code == "acquisition_budget_exhausted"
        # The third request was never issued: the budget closed the chain first.
        assert transport.calls == 2
        assert session.requests_made == 2

    @pytest.mark.asyncio
    async def test_retry_and_hop_share_one_request_budget(self) -> None:
        transport = FlakyTransport()
        fetcher = SafeFetcher(resolver=public_resolver, transport=transport)
        session = FetchSession(max_requests=2)

        async def instant(_delay: float) -> None:
            return None

        with pytest.raises(CollectionError) as exc:
            await fetch_with_retries(
                fetcher,
                "https://example.com/feed",
                SourceType.URL,
                sleep=instant,
                max_retries=5,
                session=session,
            )
        assert exc.value.code == "acquisition_budget_exhausted"
        assert transport.calls == 2
        assert exc.value.requests_made == 2


class TestTimeAndByteBudget:
    @pytest.mark.asyncio
    async def test_expired_deadline_blocks_before_any_request(self) -> None:
        transport = RedirectChainTransport(hops=0)
        fetcher = SafeFetcher(resolver=public_resolver, transport=transport)
        session = FetchSession(deadline_monotonic=time.monotonic() - 1)
        with pytest.raises(CollectionError) as exc:
            await fetcher.fetch("https://example.com/page", SourceType.URL, session=session)
        assert exc.value.code == "acquisition_budget_exhausted"
        assert transport.calls == 0

    @pytest.mark.asyncio
    async def test_byte_budget_trips_during_read_not_after(self) -> None:
        reader = asyncio.StreamReader()
        reader.feed_data(b"x" * 4096)
        reader.feed_eof()
        session = FetchSession(max_bytes=1024)
        with pytest.raises(CollectionError) as exc:
            await _decode_body(reader, {"content-length": "4096"}, session=session)
        assert exc.value.code == "acquisition_budget_exhausted"

    @pytest.mark.asyncio
    async def test_fixed_cap_still_reports_response_too_large_without_budget(self) -> None:
        reader = asyncio.StreamReader()
        reader.feed_data(b"x" * 4096)
        reader.feed_eof()
        session = FetchSession()
        assert (
            await _decode_body(reader, {"content-length": "4096"}, session=session) == b"x" * 4096
        )
        assert session.bytes_received == 4096

    @pytest.mark.asyncio
    async def test_deadline_bounds_retry_backoff(self) -> None:
        transport = FlakyTransport()
        fetcher = SafeFetcher(resolver=public_resolver, transport=transport)
        session = FetchSession(deadline_monotonic=time.monotonic() + 0.5)
        slept: list[float] = []

        async def recording_sleep(delay: float) -> None:
            slept.append(delay)

        with pytest.raises(CollectionError) as exc:
            await fetch_with_retries(
                fetcher,
                "https://example.com/feed",
                SourceType.URL,
                sleep=recording_sleep,
                max_retries=3,
                session=session,
            )
        assert exc.value.code == "acquisition_budget_exhausted"
        assert slept == []  # the 2s backoff cannot fit the remaining budget

    @pytest.mark.asyncio
    async def test_native_backend_bills_hops_from_the_production_path(self) -> None:
        transport = RedirectChainTransport(hops=2)
        backend = NativeAcquisitionBackend(
            fetcher=SafeFetcher(resolver=public_resolver, transport=transport)
        )
        request = _backend_request()
        result = await backend.acquire(request)
        assert result.budget_used["requests"] == 3  # initial + two hops
        assert result.response.redirects == 2
        assert result.retry_count == 0


def _backend_request(
    *, max_requests: int = 10, max_bytes: int = 5_000_000, deadline: float | None = None
) -> Any:
    from app.services.acquisition_types import AcquisitionRequest

    return AcquisitionRequest(
        source_id=uuid4(),
        run_id=uuid4(),
        target_url="https://example.com/start",
        source_type=SourceType.URL,
        source_family=SourceFamily.GENERIC_WEB,
        mode=AcquisitionMode.AUTO,
        discovery_mode=DiscoveryMode.SINGLE_PAGE,
        profile=AcquisitionProfileV1(),
        correlation_id=None,
        remaining_budget=AttemptBudget(
            max_requests=max_requests, max_bytes=max_bytes, deadline_monotonic=deadline
        ),
    )


class TestSiteGate:
    @pytest.mark.asyncio
    async def test_crawl_delay_spacing_between_requests(self) -> None:
        slept: list[float] = []

        async def recording_sleep(delay: float) -> None:
            slept.append(delay)

        gate = SiteGate(sleep=recording_sleep)
        async with gate.guard("example.com", crawl_delay_ms=1000, requests_per_minute=600):
            pass
        assert slept == []  # first request has no predecessor
        async with gate.guard("example.com", crawl_delay_ms=1000, requests_per_minute=600):
            pass
        assert len(slept) == 1
        assert 0.6 <= slept[0] <= 1.0
        assert gate.delays_applied_ms and 600 <= gate.delays_applied_ms[0] <= 1000

    @pytest.mark.asyncio
    async def test_rpm_spacing_dominates_when_longer_than_crawl_delay(self) -> None:
        slept: list[float] = []

        async def recording_sleep(delay: float) -> None:
            slept.append(delay)

        gate = SiteGate(sleep=recording_sleep)
        async with gate.guard("example.com", crawl_delay_ms=0, requests_per_minute=30):
            pass
        async with gate.guard("example.com", crawl_delay_ms=0, requests_per_minute=30):
            pass
        assert len(slept) == 1
        assert 1.5 <= slept[0] <= 2.0  # 60_000 / 30 = 2000 ms

    @pytest.mark.asyncio
    async def test_same_host_requests_are_serialized(self) -> None:
        gate = SiteGate()
        in_flight = 0
        peak = 0
        entered = asyncio.Event()
        release = asyncio.Event()

        async def worker() -> None:
            nonlocal in_flight, peak
            async with gate.guard("example.com", crawl_delay_ms=0, requests_per_minute=600_000):
                in_flight += 1
                peak = max(peak, in_flight)
                entered.set()
                await release.wait()
                in_flight -= 1

        first = asyncio.create_task(worker())
        await entered.wait()
        second = asyncio.create_task(worker())
        await asyncio.sleep(0.05)
        assert peak == 1
        assert not second.done()
        release.set()
        await asyncio.gather(first, second)
        assert peak == 1

    @pytest.mark.asyncio
    async def test_routed_run_records_executed_throttle_evidence(
        self, closure_engine: AsyncEngine
    ) -> None:
        # Production candidate chain for URL sources is single-stage; the throttle
        # evidence must still record the *executed* values for every request.
        source_id = await create_route_source(closure_engine)
        run_id = await queue_route_run(closure_engine, source_id)
        gate = SiteGate()
        factory = async_sessionmaker(closure_engine, expire_on_commit=False)
        ok = await execute_route_run(
            SqlAlchemyAcquisitionRunRepository(factory),
            run_id,
            backends={BackendName.NATIVE_HTTP: StageBackend()},
            site_gate=gate,
        )
        assert ok is True
        async with factory() as session:
            run = await session.get(CollectionRun, run_id)
            assert run is not None
            throttle = run.budget_summary["site_throttle"]
            assert throttle["enforced_in_flight"] == 1
            assert throttle["max_parallel_requests"] >= 1
            assert throttle["crawl_delay_ms"] >= 0
            assert throttle["requests_per_minute"] >= 1
            assert tuple(throttle["delays_applied_ms"]) == ()  # first request: no predecessor

    @pytest.mark.asyncio
    async def test_retry_waits_at_least_the_site_spacing_floor(self) -> None:
        transport = FlakyOnceTransport()
        fetcher = SafeFetcher(resolver=public_resolver, transport=transport)
        slept: list[float] = []

        async def recording_sleep(delay: float) -> None:
            slept.append(delay)

        response, retries = await fetch_with_retries(
            fetcher,
            "https://example.com/page",
            SourceType.URL,
            sleep=recording_sleep,
            max_retries=2,
            min_delay=5.0,  # a 5s crawl-delay floor configured by the site policy
        )
        assert retries == 1
        assert transport.calls == 2
        assert slept == [5.0]  # max(exponential backoff 2s, spacing floor 5s)
        assert response.body


class StageBackend:
    def __init__(self, *, body: bytes | None = None) -> None:
        self.body = body or (
            b"<html><head><title>Closure</title></head><body><main>"
            + b"Deterministic acceptable extraction content. " * 40
            + b"</main></body></html>"
        )
        self.calls = 0

    async def acquire(self, request: Any) -> AcquisitionResult:
        self.calls += 1
        return AcquisitionResult(
            FetchResponse(request.target_url, "text/html; charset=utf-8", self.body),
            retry_count=0,
            budget_used={"requests": 1, "pages": 1, "bytes_received": len(self.body)},
        )


@pytest.fixture
async def closure_engine() -> Any:
    database_url = os.environ["TEST_DATABASE_URL"]
    assert "_test" in database_url.rsplit("/", maxsplit=1)[-1]
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    yield engine
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    await engine.dispose()


async def create_route_source(
    engine: AsyncEngine, *, family: SourceFamily = SourceFamily.GENERIC_WEB
) -> UUID:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User(
            id=uuid4(),
            email=f"closure-{uuid4()}@example.com",
            password_hash="synthetic",  # noqa: S106 - isolated database fixture
            display_name="Closure",
        )
        source = Source(
            id=uuid4(),
            user_id=user.id,
            name="Closure Source",
            source_type=SourceType.URL,
            url="https://example.com/page",
            normalized_url="https://example.com/page",
            source_family=family,
            acquisition_mode=AcquisitionMode.AUTO,
            acquisition_profile=AcquisitionProfileV1().storage_dict(),
        )
        session.add(user)
        await session.flush()
        session.add(source)
        await session.flush()
        session.add(SourceAcquisitionState(source_id=source.id))
        await session.commit()
        return source.id


async def queue_route_run(engine: AsyncEngine, source_id: UUID) -> UUID:
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


def evidence_candidate(raw_text: str, *, title: str = "Doc") -> RawCandidate:
    return RawCandidate(
        external_id="doc-1",
        canonical_url="https://example.com/doc",
        raw_text=raw_text,
        content_type="text/html; charset=utf-8",
        title=title,
    )


async def shadow_write(
    engine: AsyncEngine, source_id: UUID, raw_text: str, *, at: datetime = NOW
) -> None:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        source = await session.get(Source, source_id)
        assert source is not None
        run = CollectionRun(
            id=uuid4(),
            source_id=source.id,
            trigger_type=CollectionTriggerType.MANUAL,
            status=CollectionRunStatus.RUNNING,
            claim_token=uuid4(),
            worker_id="closure-test",
            lease_expires_at=at + timedelta(minutes=10),
        )
        session.add(run)
        await session.flush()
        await record_version_evidence(
            session,
            run=run,
            parsed=ParseResult(candidates=[evidence_candidate(raw_text)]),
            body=b"<html><body><p>x</p></body></html>",
            quality_score=Decimal("0.8000"),
            fetched_at=at,
        )
        await session.commit()


async def miss_cycle(engine: AsyncEngine, source_id: UUID, *, at: datetime = NOW) -> None:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        run = CollectionRun(
            id=uuid4(),
            source_id=source_id,
            trigger_type=CollectionTriggerType.MANUAL,
            status=CollectionRunStatus.RUNNING,
            claim_token=uuid4(),
            worker_id="closure-test",
            lease_expires_at=at + timedelta(minutes=10),
        )
        session.add(run)
        await session.flush()
        await record_version_evidence(
            session,
            run=run,
            parsed=ParseResult(candidates=[]),
            body=None,
            quality_score=Decimal("0.8000"),
            fetched_at=at,
        )
        await session.commit()


async def artifact_events(engine: AsyncEngine) -> tuple[SourceArtifact | None, list[ChangeEvent]]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        artifact = await session.scalar(select(SourceArtifact))
        events = list(
            (
                await session.scalars(
                    select(ChangeEvent).order_by(
                        ChangeEvent.occurred_at.asc(), ChangeEvent.id.asc()
                    )
                )
            ).all()
        )
        return artifact, events


class TestVersionRollback:
    @pytest.mark.asyncio
    async def test_revert_then_repeat_is_unchanged(self, closure_engine: AsyncEngine) -> None:
        source_id = await create_route_source(closure_engine)
        await shadow_write(closure_engine, source_id, "State A body with stable content.")
        await shadow_write(
            closure_engine,
            source_id,
            "State B body with changed content.",
            at=NOW + timedelta(minutes=1),
        )
        await shadow_write(
            closure_engine,
            source_id,
            "State A body with stable content.",
            at=NOW + timedelta(minutes=2),
        )
        await shadow_write(
            closure_engine,
            source_id,
            "State A body with stable content.",
            at=NOW + timedelta(minutes=3),
        )
        artifact, events = await artifact_events(closure_engine)
        assert artifact is not None
        assert [event.change_type for event in events] == [
            "created",
            "content_changed",
            "content_changed",
            "unchanged",
        ]
        factory = async_sessionmaker(closure_engine, expire_on_commit=False)
        async with factory() as session:
            snapshots = list(
                (
                    await session.scalars(
                        select(AcquisitionSnapshot).order_by(AcquisitionSnapshot.version.asc())
                    )
                ).all()
            )
        assert [snapshot.version for snapshot in snapshots] == [1, 2]
        # The pointer tracks the last *observed* state (the re-used version 1).
        assert artifact.current_snapshot_id == snapshots[0].id
        assert events[-1].materiality == Decimal("0.0000")

    @pytest.mark.asyncio
    async def test_revert_then_return_to_b_reuses_snapshot(
        self, closure_engine: AsyncEngine
    ) -> None:
        source_id = await create_route_source(closure_engine)
        await shadow_write(closure_engine, source_id, "State A body with stable content.")
        await shadow_write(
            closure_engine,
            source_id,
            "State B body with changed content.",
            at=NOW + timedelta(minutes=1),
        )
        await shadow_write(
            closure_engine,
            source_id,
            "State A body with stable content.",
            at=NOW + timedelta(minutes=2),
        )
        await shadow_write(
            closure_engine,
            source_id,
            "State B body with changed content.",
            at=NOW + timedelta(minutes=3),
        )
        artifact, events = await artifact_events(closure_engine)
        assert artifact is not None
        assert [event.change_type for event in events] == [
            "created",
            "content_changed",
            "content_changed",
            "content_changed",
        ]
        factory = async_sessionmaker(closure_engine, expire_on_commit=False)
        async with factory() as session:
            snapshots = list(
                (
                    await session.scalars(
                        select(AcquisitionSnapshot).order_by(AcquisitionSnapshot.version.asc())
                    )
                ).all()
            )
        assert [snapshot.version for snapshot in snapshots] == [1, 2]
        # Final event returns to the B state (version 2) from the observed A state.
        assert events[-1].current_snapshot_id == snapshots[1].id
        assert events[-1].previous_snapshot_id == snapshots[0].id
        assert artifact.current_snapshot_id == snapshots[1].id

    @pytest.mark.asyncio
    async def test_removed_then_reappear_same_state_is_unchanged(
        self, closure_engine: AsyncEngine
    ) -> None:
        source_id = await create_route_source(closure_engine)
        await shadow_write(closure_engine, source_id, "State A body with stable content.")
        await miss_cycle(closure_engine, source_id, at=NOW + timedelta(minutes=1))
        await miss_cycle(closure_engine, source_id, at=NOW + timedelta(minutes=2))
        await shadow_write(
            closure_engine,
            source_id,
            "State A body with stable content.",
            at=NOW + timedelta(minutes=3),
        )
        artifact, events = await artifact_events(closure_engine)
        assert artifact is not None
        assert artifact.removed_at is None
        assert [event.change_type for event in events] == [
            "created",
            "removed",
            "unchanged",
        ]


class TestBackfillCursor:
    @pytest.mark.asyncio
    async def test_backfill_processes_more_than_one_batch(
        self, closure_engine: AsyncEngine
    ) -> None:
        source_id = await create_route_source(closure_engine)
        factory = async_sessionmaker(closure_engine, expire_on_commit=False)
        run_id = await queue_route_run(closure_engine, source_id)
        async with factory() as session:
            for index in range(5):
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
                        raw_text=f"Legacy body {index} with stable content.",
                        content_hash=uuid4().hex * 2,
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
        assert first == 5
        async with factory() as session:
            second = await backfill_source_evidence(session, source=source, batch_size=2)
            await session.commit()
        assert second == 0


async def _seed_opportunity_world(
    engine: AsyncEngine,
) -> tuple[UUID, UUID, UUID, UUID, UUID]:
    """User + two opportunity sources + two radars + one scored and one unscored item."""
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User(
            id=uuid4(),
            email=f"opp-{uuid4()}@example.com",
            password_hash="synthetic",  # noqa: S106 - isolated database fixture
            display_name="Opp",
        )
        radar_a, radar_b = uuid4(), uuid4()
        source_a = Source(
            id=uuid4(),
            user_id=user.id,
            name="Opp Source A",
            source_type=SourceType.URL,
            url="https://example.com/a",
            normalized_url="https://example.com/a",
            source_family=SourceFamily.OPPORTUNITY,
            acquisition_mode=AcquisitionMode.AUTO,
            acquisition_profile=AcquisitionProfileV1().storage_dict(),
        )
        source_b = Source(
            id=uuid4(),
            user_id=user.id,
            name="Opp Source B",
            source_type=SourceType.URL,
            url="https://example.com/b",
            normalized_url="https://example.com/b",
            source_family=SourceFamily.OPPORTUNITY,
            acquisition_mode=AcquisitionMode.AUTO,
            acquisition_profile=AcquisitionProfileV1().storage_dict(),
        )
        session.add(user)
        await session.flush()
        session.add_all([source_a, source_b])
        await session.flush()
        session.add_all(
            [
                SourceAcquisitionState(source_id=source_a.id),
                SourceAcquisitionState(source_id=source_b.id),
                Radar(
                    id=radar_a,
                    user_id=user.id,
                    name="Radar A",
                    goal="goal",
                    radar_type=RadarType.OPPORTUNITY,
                    categories=[],
                    keywords=[],
                    status=ResourceStatus.ACTIVE,
                    notification_threshold=75,
                ),
                Radar(
                    id=radar_b,
                    user_id=user.id,
                    name="Radar B",
                    goal="goal",
                    radar_type=RadarType.OPPORTUNITY,
                    categories=[],
                    keywords=[],
                    status=ResourceStatus.ACTIVE,
                    notification_threshold=75,
                ),
            ]
        )
        await session.flush()
        session.add_all(
            [
                RadarSource(radar_id=radar_a, source_id=source_a.id),
                RadarSource(radar_id=radar_b, source_id=source_b.id),
            ]
        )

        async def seed_item(source: Source, title: str) -> UUID:
            run = CollectionRun(
                id=uuid4(),
                source_id=source.id,
                trigger_type=CollectionTriggerType.MANUAL,
                status=CollectionRunStatus.SUCCEEDED,
            )
            session.add(run)
            await session.flush()
            artifact = SourceArtifact(
                id=uuid4(),
                source_id=source.id,
                artifact_key=f"key-{uuid4()}",
                canonical_url=f"https://example.com/{uuid4()}",
                first_seen_at=NOW,
                last_seen_at=NOW,
                safe_metadata={},
            )
            session.add(artifact)
            await session.flush()
            snapshot = AcquisitionSnapshot(
                id=uuid4(),
                artifact_id=artifact.id,
                collection_run_id=run.id,
                version=1,
                fetched_at=NOW,
                normalized_content="Deterministic content.",
                safe_metadata={},
                structure_summary={},
                content_hash=uuid4().hex * 2,
                metadata_hash=uuid4().hex * 2,
                structure_hash=uuid4().hex * 2,
                extractor_version="extractor-v1",
                quality_score=Decimal("0.8000"),
                evidence={},
            )
            session.add(snapshot)
            await session.flush()
            artifact.current_snapshot_id = snapshot.id
            item = OpportunityItem(
                id=uuid4(),
                user_id=user.id,
                source_id=source.id,
                artifact_id=artifact.id,
                snapshot_id=snapshot.id,
                profile_version="freelance-v1",
                title=title,
                description="bounded description",
                source_url=f"https://example.com/{uuid4()}",
                status="active",
            )
            session.add(item)
            await session.flush()
            return item.id

        scored_id = await seed_item(source_a, "Scored")
        unscored_id = await seed_item(source_b, "Unscored")
        session.add(
            OpportunityScore(
                id=uuid4(),
                opportunity_id=scored_id,
                radar_id=radar_a,
                score_version="opportunity-score-v1",
                hard_filter_passed=True,
                disqualifiers=[],
                fit=90,
                expected_value=88,
                completion_probability=86,
                effort_efficiency=84,
                time_to_delivery=82,
                competition=20,
                ambiguity=15,
                risk=10,
                overall_score=Decimal("86.55"),
                recommendation="act_now",
                reason="ok",
                scored_at=NOW,
            )
        )
        await session.commit()
        return user.id, radar_a, radar_b, scored_id, unscored_id


class TestOpportunityFilterSet:
    @pytest.mark.asyncio
    async def test_radar_scope_and_score_filters_bound_the_set(
        self, closure_engine: AsyncEngine
    ) -> None:
        user_id, radar_a, radar_b, scored_id, unscored_id = await _seed_opportunity_world(
            closure_engine
        )
        factory = async_sessionmaker(closure_engine, expire_on_commit=False)

        async def listing(
            radar_id: UUID | None, recommendation: str | None, min_score: Decimal | None
        ) -> Any:
            async with factory() as session:
                return await list_opportunities(
                    session,
                    user_id=user_id,
                    page=1,
                    page_size=10,
                    radar_id=radar_id,
                    status=None,
                    recommendation=recommendation,
                    min_score=min_score,
                    currency=None,
                    deadline_before=None,
                )

        rows, total = await listing(None, None, None)
        assert total == len(rows) == 2  # both items belong to the user's set

        rows, total = await listing(radar_a, None, None)
        assert total == len(rows) == 1
        assert rows[0][0].id == scored_id

        rows, total = await listing(radar_a, "act_now", Decimal("80"))
        assert total == len(rows) == 1
        assert rows[0][0].id == scored_id

        rows, total = await listing(radar_b, None, None)
        assert total == len(rows) == 1
        assert rows[0][0].id == unscored_id
        assert rows[0][1] is None

        rows, total = await listing(None, "dismiss", None)
        assert total == len(rows) == 0
