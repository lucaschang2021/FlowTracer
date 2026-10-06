"""ACQ-1 closure Phase 1 acceptance matrix (docs/71 §Phase 1, ADR-038).

WP-4 router closure on the **production path** (no selector patching):

1.1 production static selection and controlled fallback — the selector emits the
    static-retry stage when the effective budget can fund it, and a real
    ``NativeAcquisitionBackend`` pair (each behind a genuine ``SafeFetcher`` with a
    deterministic local transport) exercises the fallback end to end;
1.2 fallback / retry / redirect share one cumulative budget (exact totals, and the
    budget refusal when the second stage cannot be afforded);
1.3 Circuit half-open single probe under concurrency, success closing the circuit,
    and throttle recovery after a success;
1.4 Browser stays unreachable and never becomes a fallback.
"""

from __future__ import annotations

import asyncio
import os
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.models.entities import (
    AcquisitionAttempt,
    AcquisitionMode,
    BackendName,
    CollectionRun,
    CollectionRunStatus,
    CollectionTriggerType,
    Source,
    SourceAcquisitionState,
    SourceHealthStatus,
    SourceType,
    User,
)
from app.schemas.resources import AcquisitionProfileV1
from app.services.acquisition_route import execute_route_run
from app.services.acquisition_router import select_candidates
from app.services.acquisition_run_repository import SqlAlchemyAcquisitionRunRepository
from app.services.acquisition_types import CollectionError
from app.services.native_acquisition import NativeAcquisitionBackend
from app.services.safe_fetcher import SafeFetcher, WireResponse
from app.services.site_gate import SiteGate

TABLES = (
    "notifications, ai_usage_records, opportunity_action_payloads, opportunity_scores, "
    "opportunities, change_events, acquisition_snapshots, source_artifacts, "
    "acquisition_attempts, source_acquisition_states, document_chunks, bookmarks, analyses, "
    "documents, raw_items, radar_sources, collection_runs, sources, radars, refresh_tokens, users"
)
PUBLIC_IP = "93.184.216.34"
ACCEPTABLE_BODY = (
    b"<html><head><title>Router closure</title></head><body><main>"
    + b"Deterministic acceptable extraction content. " * 40
    + b"</main></body></html>"
)
LOW_QUALITY_BODY = b"<html><head></head><body><p>tiny</p></body></html>"
SITE_SPACING_SECONDS = 2.0  # crawl delay 1000ms vs RPM 30 -> max(1000, 2000) ms


async def public_resolver(_hostname: str) -> list[str]:
    return [PUBLIC_IP]


class StaticTransport:
    """Always serves one deterministic local page; counts issued requests."""

    def __init__(self, body: bytes = ACCEPTABLE_BODY, *, status: int = 200) -> None:
        self.body = body
        self.status = status
        self.calls = 0

    async def __call__(self, **_kwargs: Any) -> WireResponse:
        self.calls += 1
        if self.status != 200:
            return WireResponse(self.status, {"content-type": "text/html"}, b"")
        return WireResponse(200, {"content-type": "text/html; charset=utf-8"}, self.body)


class RedirectThenWeakTransport:
    """hop1: 302, hop2: 503, hop3: 200 with a low-quality page (3 real requests)."""

    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, **_kwargs: Any) -> WireResponse:
        self.calls += 1
        if self.calls == 1:
            return WireResponse(302, {"location": "https://example.com/step"}, b"")
        if self.calls == 2:
            return WireResponse(503, {"content-type": "text/html"}, b"")
        return WireResponse(200, {"content-type": "text/html; charset=utf-8"}, LOW_QUALITY_BODY)


def backend_with(transport: Any) -> NativeAcquisitionBackend:
    return NativeAcquisitionBackend(
        fetcher=SafeFetcher(resolver=public_resolver, transport=transport)
    )


async def create_source(
    engine: AsyncEngine, *, profile: AcquisitionProfileV1 | None = None
) -> UUID:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User(
            id=uuid4(),
            email=f"closure-p1-{uuid4()}@example.com",
            password_hash="synthetic",  # noqa: S106 - isolated database fixture
            display_name="Closure P1",
        )
        source = Source(
            id=uuid4(),
            user_id=user.id,
            name="Closure P1 Source",
            source_type=SourceType.URL,
            url="https://example.com/page",
            normalized_url="https://example.com/page",
            acquisition_mode=AcquisitionMode.AUTO,
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


def run_once(
    engine: AsyncEngine,
    run_id: UUID,
    backends: dict[BackendName, Any],
    *,
    site_gate: SiteGate | None = None,
    task_id: str = "closure-p1",
) -> Any:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return execute_route_run(
        SqlAlchemyAcquisitionRunRepository(factory),
        run_id,
        backends=backends,
        task_id=task_id,
        site_gate=site_gate,
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


async def set_circuit_state(
    engine: AsyncEngine,
    source_id: UUID,
    *,
    consecutive_failures: int,
    open_until: datetime | None,
) -> None:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        state = await session.get(SourceAcquisitionState, source_id)
        assert state is not None
        state.consecutive_failures = consecutive_failures
        state.circuit_open_until = open_until
        state.health_status = (
            SourceHealthStatus.CIRCUIT_OPEN
            if open_until is not None
            else SourceHealthStatus.DEGRADED
        )
        await session.commit()


@pytest.fixture
async def closure_p1_engine() -> Any:
    database_url = os.environ["TEST_DATABASE_URL"]
    assert "_test" in database_url.rsplit("/", maxsplit=1)[-1]
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    yield engine
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    await engine.dispose()


class TestProductionSelector:
    def test_selector_emits_static_retry_only_when_budget_allows(self) -> None:
        single = select_candidates(
            source_type=SourceType.URL, mode=AcquisitionMode.AUTO, allow_browser=False
        )
        assert [candidate.backend for candidate in single] == [BackendName.NATIVE_HTTP]
        extended = select_candidates(
            source_type=SourceType.URL,
            mode=AcquisitionMode.AUTO,
            allow_browser=False,
            allow_static_retry=True,
        )
        assert [candidate.backend for candidate in extended] == [
            BackendName.NATIVE_HTTP,
            BackendName.SCRAPLING_HTTP,
        ]
        assert [candidate.stage for candidate in extended] == [1, 2]
        rss = select_candidates(
            source_type=SourceType.RSS,
            mode=AcquisitionMode.AUTO,
            allow_browser=False,
            allow_static_retry=True,
        )
        assert [candidate.backend for candidate in rss] == [BackendName.RSS]

    def test_browser_stays_unreachable_with_retry_enabled(self) -> None:
        with pytest.raises(CollectionError) as exc:
            select_candidates(
                source_type=SourceType.URL,
                mode=AcquisitionMode.AUTO,
                allow_browser=True,
                allow_static_retry=True,
            )
        assert exc.value.code == "acquisition_browser_not_admitted"
        for candidate in select_candidates(
            source_type=SourceType.URL,
            mode=AcquisitionMode.AUTO,
            allow_browser=False,
            allow_static_retry=True,
        ):
            assert candidate.backend not in {
                BackendName.DYNAMIC_BROWSER,
                BackendName.ADVANCED_BROWSER,
            }


class TestProductionFallback:
    @pytest.mark.asyncio
    async def test_quality_gate_falls_back_through_production_chain(
        self, closure_p1_engine: AsyncEngine
    ) -> None:
        profile = AcquisitionProfileV1()
        profile.resource_budget.max_pages = 2
        source_id = await create_source(closure_p1_engine, profile=profile)
        run_id = await queue_run(closure_p1_engine, source_id)
        weak_transport = StaticTransport(LOW_QUALITY_BODY)
        strong_transport = StaticTransport()
        slept: list[float] = []

        async def recording_sleep(delay: float) -> None:
            slept.append(delay)

        gate = SiteGate(sleep=recording_sleep)
        ok = await run_once(
            closure_p1_engine,
            run_id,
            {
                BackendName.NATIVE_HTTP: backend_with(weak_transport),
                BackendName.SCRAPLING_HTTP: backend_with(strong_transport),
            },
            site_gate=gate,
        )
        assert ok is True
        assert weak_transport.calls == 1
        assert strong_transport.calls == 1
        run = await load_run(closure_p1_engine, run_id)
        assert run.status == CollectionRunStatus.SUCCEEDED
        assert run.backend == "scrapling_http"
        assert run.fallback_count == 1
        summary = run.budget_summary
        assert summary["stages"] == 2 and summary["fallbacks"] == 1
        assert summary["accepted_backend"] == "scrapling_http"
        attempts = await load_attempts(closure_p1_engine, run_id)
        assert [attempt.ordinal for attempt in attempts] == [1, 2]
        assert attempts[0].status == "failed"
        assert attempts[0].error_code == "acquisition_quality_unmet"
        assert attempts[1].status == "succeeded"
        assert attempts[1].fallback_reason == "quality_unmet"
        assert attempts[0].budget_used["requests"] == 1
        assert attempts[1].budget_used["requests"] == 1
        # The fallback request went through the executed site gate: one spacing delay.
        assert len(slept) == 1
        assert SITE_SPACING_SECONDS - 0.2 <= slept[0] <= SITE_SPACING_SECONDS

    @pytest.mark.asyncio
    async def test_chain_is_single_stage_under_default_profile(
        self, closure_p1_engine: AsyncEngine
    ) -> None:
        source_id = await create_source(closure_p1_engine)
        run_id = await queue_run(closure_p1_engine, source_id)
        strong_transport = StaticTransport()
        retry_transport = StaticTransport()
        ok = await run_once(
            closure_p1_engine,
            run_id,
            {
                BackendName.NATIVE_HTTP: backend_with(strong_transport),
                BackendName.SCRAPLING_HTTP: backend_with(retry_transport),
            },
        )
        assert ok is True
        # Default profile (max_pages=1): no second stage is ever selected.
        assert retry_transport.calls == 0
        run = await load_run(closure_p1_engine, run_id)
        assert run.budget_summary["stages"] == 1


class TestSharedBudgetAcrossFallback:
    @pytest.mark.asyncio
    async def test_redirect_retry_and_fallback_totals_are_exact(
        self, closure_p1_engine: AsyncEngine
    ) -> None:
        profile = AcquisitionProfileV1()
        profile.resource_budget.max_pages = 2
        profile.resource_budget.max_requests = 5
        source_id = await create_source(closure_p1_engine, profile=profile)
        run_id = await queue_run(closure_p1_engine, source_id)
        stage_one = RedirectThenWeakTransport()  # 302 + 503 + 200 = 3 requests
        stage_two = StaticTransport()  # 1 request
        ok = await run_once(
            closure_p1_engine,
            run_id,
            {
                BackendName.NATIVE_HTTP: backend_with(stage_one),
                BackendName.SCRAPLING_HTTP: backend_with(stage_two),
            },
        )
        assert ok is True
        assert stage_one.calls == 3 and stage_two.calls == 1
        attempts = await load_attempts(closure_p1_engine, run_id)
        assert attempts[0].budget_used["requests"] == 3  # redirect + retry counted
        assert attempts[1].budget_used["requests"] == 1
        run = await load_run(closure_p1_engine, run_id)
        assert run.status == CollectionRunStatus.SUCCEEDED
        assert run.backend == "scrapling_http"

    @pytest.mark.asyncio
    async def test_budget_refuses_second_stage_before_transport(
        self, closure_p1_engine: AsyncEngine
    ) -> None:
        profile = AcquisitionProfileV1()
        profile.resource_budget.max_pages = 2
        profile.resource_budget.max_requests = 3  # exactly funds stage one (3 requests)
        source_id = await create_source(closure_p1_engine, profile=profile)
        run_id = await queue_run(closure_p1_engine, source_id)
        stage_one = RedirectThenWeakTransport()
        stage_two = StaticTransport()
        ok = await run_once(
            closure_p1_engine,
            run_id,
            {
                BackendName.NATIVE_HTTP: backend_with(stage_one),
                BackendName.SCRAPLING_HTTP: backend_with(stage_two),
            },
        )
        assert ok is False
        assert stage_two.calls == 0  # the second stage never transmitted
        run = await load_run(closure_p1_engine, run_id)
        assert run.status == CollectionRunStatus.FAILED
        assert run.error_code == "acquisition_budget_exhausted"
        attempts = await load_attempts(closure_p1_engine, run_id)
        assert len(attempts) == 1  # the refused stage produced no attempt row


class TestCircuitHalfOpenAndThrottleRecovery:
    @pytest.mark.asyncio
    async def test_half_open_probe_success_closes_circuit(
        self, closure_p1_engine: AsyncEngine
    ) -> None:
        source_id = await create_source(closure_p1_engine)
        await set_circuit_state(
            closure_p1_engine,
            source_id,
            consecutive_failures=5,
            open_until=datetime.now(UTC) - timedelta(seconds=1),
        )
        run_id = await queue_run(closure_p1_engine, source_id)
        transport = StaticTransport()
        ok = await run_once(
            closure_p1_engine, run_id, {BackendName.NATIVE_HTTP: backend_with(transport)}
        )
        assert ok is True
        assert transport.calls == 1  # the probe was allowed to transmit once
        state = await load_state(closure_p1_engine, source_id)
        assert state.consecutive_failures == 0
        assert state.circuit_open_until is None
        assert state.health_status == SourceHealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_open_window_refuses_without_transport(
        self, closure_p1_engine: AsyncEngine
    ) -> None:
        source_id = await create_source(closure_p1_engine)
        await set_circuit_state(
            closure_p1_engine,
            source_id,
            consecutive_failures=5,
            open_until=datetime.now(UTC) + timedelta(minutes=5),
        )
        run_id = await queue_run(closure_p1_engine, source_id)
        transport = StaticTransport()
        ok = await run_once(
            closure_p1_engine, run_id, {BackendName.NATIVE_HTTP: backend_with(transport)}
        )
        assert ok is False
        assert transport.calls == 0
        run = await load_run(closure_p1_engine, run_id)
        assert run.error_code == "acquisition_circuit_open"

    @pytest.mark.asyncio
    async def test_concurrent_half_open_probes_transmit_exactly_once(
        self, closure_p1_engine: AsyncEngine
    ) -> None:
        source_id = await create_source(closure_p1_engine)
        await set_circuit_state(
            closure_p1_engine,
            source_id,
            consecutive_failures=5,
            open_until=datetime.now(UTC) - timedelta(seconds=1),
        )
        run_one = await queue_run(closure_p1_engine, source_id)
        run_two = await queue_run(closure_p1_engine, source_id)
        entered = asyncio.Event()
        release = asyncio.Event()

        class BlockingTransport:
            def __init__(self) -> None:
                self.calls = 0

            async def __call__(self, **_kwargs: Any) -> WireResponse:
                self.calls += 1
                entered.set()
                await release.wait()
                return WireResponse(
                    200, {"content-type": "text/html; charset=utf-8"}, ACCEPTABLE_BODY
                )

        transport = BlockingTransport()
        backends = {BackendName.NATIVE_HTTP: backend_with(transport)}
        probe = asyncio.create_task(
            run_once(closure_p1_engine, run_one, backends, task_id="probe-a")
        )
        await entered.wait()  # probe A holds the half-open slot and is mid-request
        second = await run_once(closure_p1_engine, run_two, backends, task_id="probe-b")
        release.set()
        first = await probe
        assert first is True
        assert second is False  # the concurrent run was refused, not queued
        assert transport.calls == 1  # exactly one probe transmitted through the circuit

    @pytest.mark.asyncio
    async def test_throttle_applies_after_failure_and_recovers_after_success(
        self, closure_p1_engine: AsyncEngine
    ) -> None:
        source_id = await create_source(closure_p1_engine)
        failing = StaticTransport(status=404)
        run_id = await queue_run(closure_p1_engine, source_id)
        ok = await run_once(
            closure_p1_engine, run_id, {BackendName.NATIVE_HTTP: backend_with(failing)}
        )
        assert ok is False
        state = await load_state(closure_p1_engine, source_id)
        assert state.consecutive_failures == 1
        assert state.last_error_code == "http_error"

        healthy = StaticTransport()
        run_id = await queue_run(closure_p1_engine, source_id)
        started = time.monotonic()
        ok = await run_once(
            closure_p1_engine, run_id, {BackendName.NATIVE_HTTP: backend_with(healthy)}
        )
        throttled_seconds = time.monotonic() - started
        assert ok is True
        # AutoThrottle executed: adaptive delay max(crawl_delay 1000ms, 250*2^1) = 1s.
        assert throttled_seconds >= 0.9
        state = await load_state(closure_p1_engine, source_id)
        assert state.consecutive_failures == 0

        run_id = await queue_run(closure_p1_engine, source_id)
        started = time.monotonic()
        ok = await run_once(
            closure_p1_engine, run_id, {BackendName.NATIVE_HTTP: backend_with(StaticTransport())}
        )
        recovered_seconds = time.monotonic() - started
        assert ok is True
        assert recovered_seconds < 0.5  # success cleared the adaptive throttle
