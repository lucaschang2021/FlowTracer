"""WP-4 Router v1 acceptance matrix (ADR-034 / docs/57).

Covers: static-only candidate selection, browser fail-closed, quality gate and ordered
fallback, cumulative budget ledger, circuit gate + opening, duplicate-delivery idempotency,
and leak-free decision traces. Multi-stage chains are exercised by substituting the frozen
candidate selector; production keeps a single static stage while the browser tail stays
disabled.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.domains.acquisition_ports import SourceRuntimeFacts
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
from app.services.acquisition_router import (
    TRACE_KEYS,
    RouteBudgetLedger,
    RouteCandidate,
    circuit_open_seconds,
    quality_met,
    select_candidates,
    throttle_delay_ms,
)
from app.services.acquisition_run_repository import SqlAlchemyAcquisitionRunRepository
from app.services.acquisition_types import (
    AcquisitionResult,
    CollectionError,
    FetchResponse,
)

TABLES = (
    "acquisition_attempts, source_acquisition_states, raw_items, collection_runs, sources, users"
)

ACCEPTABLE_BODY = (
    b"<html><head><title>Router fixture</title></head><body><main>"
    + b"Deterministic acceptable extraction content. " * 60
    + b"</main></body></html>"
)
LOW_QUALITY_BODY = b"<html><head></head><body><script>var x=1;</script><div>hi</div></body></html>"


class StageBackend:
    """Deterministic static-stage double; counts calls and never touches the network."""

    def __init__(
        self,
        *,
        body: bytes = ACCEPTABLE_BODY,
        failure: CollectionError | None = None,
        retry_count: int = 0,
    ) -> None:
        self.body = body
        self.failure = failure
        self.retry_count = retry_count
        self.calls = 0

    async def acquire(self, request: Any) -> AcquisitionResult:
        self.calls += 1
        if self.failure is not None:
            self.failure.retry_count = self.retry_count
            raise self.failure
        return AcquisitionResult(
            FetchResponse(request.target_url, "text/html; charset=utf-8", self.body),
            retry_count=self.retry_count,
            budget_used={
                "requests": self.retry_count + 1,
                "pages": 1,
                "bytes_received": len(self.body),
            },
        )


@pytest.fixture
async def router_engine() -> AsyncEngine:
    database_url = os.environ["TEST_DATABASE_URL"]
    assert "_test" in database_url.rsplit("/", maxsplit=1)[-1]
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    yield engine
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    await engine.dispose()


async def create_source(
    engine: AsyncEngine,
    *,
    mode: AcquisitionMode = AcquisitionMode.AUTO,
    url: str = "https://example.com/article",
    profile: AcquisitionProfileV1 | None = None,
    source_type: SourceType = SourceType.URL,
) -> UUID:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User(
            id=uuid4(),
            email=f"router-{uuid4()}@example.com",
            password_hash="synthetic",  # noqa: S106 - isolated database fixture
            display_name="Router",
        )
        source = Source(
            id=uuid4(),
            user_id=user.id,
            name="Router Source",
            source_type=source_type,
            url=url,
            normalized_url=url,
            acquisition_mode=mode,
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


def run_router(
    engine: AsyncEngine,
    run_id: UUID,
    backends: dict[BackendName, Any],
    **kwargs: Any,
) -> Any:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return execute_route_run(
        SqlAlchemyAcquisitionRunRepository(factory),
        run_id,
        backends=backends,
        **kwargs,
    )


async def load_run(engine: AsyncEngine, run_id: UUID) -> CollectionRun:
    async with AsyncSession(engine) as session:
        run = await session.get(CollectionRun, run_id)
        assert run is not None
        return run


async def load_attempts(engine: AsyncEngine, run_id: UUID) -> list[AcquisitionAttempt]:
    async with AsyncSession(engine) as session:
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
    async with AsyncSession(engine) as session:
        state = await session.get(SourceAcquisitionState, source_id)
        assert state is not None
        return state


class TestPurePolicies:
    def test_select_candidates_is_static_only(self) -> None:
        rss = select_candidates(
            source_type=SourceType.RSS, mode=AcquisitionMode.AUTO, allow_browser=False
        )
        assert [candidate.backend for candidate in rss] == [BackendName.RSS]
        url = select_candidates(
            source_type=SourceType.URL, mode=AcquisitionMode.NATIVE, allow_browser=False
        )
        assert [candidate.backend for candidate in url] == [BackendName.NATIVE_HTTP]
        for candidate in rss + url:
            assert candidate.backend not in {
                BackendName.DYNAMIC_BROWSER,
                BackendName.ADVANCED_BROWSER,
            }

    def test_select_candidates_rejects_browser_and_unknown_modes(self) -> None:
        with pytest.raises(CollectionError) as browser:
            select_candidates(
                source_type=SourceType.URL,
                mode=AcquisitionMode.AUTO,
                allow_browser=True,
            )
        assert browser.value.code == "acquisition_browser_not_admitted"
        with pytest.raises(CollectionError) as dynamic:
            select_candidates(
                source_type=SourceType.URL,
                mode=AcquisitionMode.DYNAMIC,
                allow_browser=False,
            )
        assert dynamic.value.code == "acquisition_mode_unsupported"
        with pytest.raises(CollectionError) as api:
            select_candidates(
                source_type=SourceType.API,
                mode=AcquisitionMode.AUTO,
                allow_browser=False,
            )
        assert api.value.code == "acquisition_no_backend"

    def test_quality_gate_buckets(self) -> None:
        assert quality_met(None) is True
        assert quality_met(Decimal("0.7500")) is True
        assert quality_met(Decimal("0.5999")) is False
        assert quality_met(Decimal("0.1000")) is False

    def test_circuit_backoff_window(self) -> None:
        assert circuit_open_seconds(5) == 900
        assert circuit_open_seconds(6) == 1800
        assert circuit_open_seconds(8) == 7200
        assert circuit_open_seconds(12) == 7200

    def test_throttle_requires_real_signal(self) -> None:
        fresh = SourceRuntimeFacts("healthy", 0, None, None, None)
        assert throttle_delay_ms(fresh, crawl_delay_ms=1000) == 0
        assert throttle_delay_ms(None, crawl_delay_ms=1000) == 0
        noisy = SourceRuntimeFacts("degraded", 3, None, "http_error", 900)
        assert throttle_delay_ms(noisy, crawl_delay_ms=1000) == 2000
        unrelated = SourceRuntimeFacts("degraded", 3, None, "unsupported_content_type", 900)
        assert throttle_delay_ms(unrelated, crawl_delay_ms=1000) == 0
        capped = SourceRuntimeFacts("degraded", 9, None, "request_timeout", 900)
        assert throttle_delay_ms(capped, crawl_delay_ms=1000) == 30_000

    def test_budget_ledger_accumulates(self) -> None:
        ledger = RouteBudgetLedger()
        ledger.charge({"requests": 2, "pages": 1, "bytes_received": 100})
        ledger.charge({"requests": 1, "bytes_received": 50})
        assert ledger.totals == {"requests": 3, "pages": 1, "bytes_received": 150}
        from app.services.acquisition_policy import EffectiveResourceBudget

        strict = EffectiveResourceBudget(
            max_requests=3,
            max_pages=4,
            max_depth=1,
            max_duration_seconds=60,
            max_concurrency=1,
            max_browser_pages=0,
            max_retries_per_target=1,
            max_total_bytes=1024,
        )
        with pytest.raises(CollectionError) as exc:
            ledger.enforce(strict)
        assert exc.value.code == "acquisition_budget_exhausted"


class TestRouterRuns:
    @pytest.mark.asyncio
    async def test_quality_gate_falls_back_to_next_static_stage(
        self, router_engine: AsyncEngine
    ) -> None:
        profile = AcquisitionProfileV1()
        profile.resource_budget.max_pages = 4
        source_id = await create_source(router_engine, profile=profile)
        run_id = await queue_run(router_engine, source_id)
        first = StageBackend(body=LOW_QUALITY_BODY)
        second = StageBackend(body=ACCEPTABLE_BODY)
        chain = (
            RouteCandidate(1, BackendName.NATIVE_HTTP, "native_static"),
            RouteCandidate(2, BackendName.SCRAPLING_HTTP, "static_retry"),
        )
        with patch("app.services.acquisition_route.select_candidates", return_value=chain):
            ok = await run_router(
                router_engine,
                run_id,
                {BackendName.NATIVE_HTTP: first, BackendName.SCRAPLING_HTTP: second},
            )
        assert ok is True
        assert first.calls == 1
        assert second.calls == 1
        run = await load_run(router_engine, run_id)
        assert run.status == CollectionRunStatus.SUCCEEDED
        assert run.backend == "scrapling_http"
        assert run.fallback_count == 1
        assert run.error_code is None
        attempts = await load_attempts(router_engine, run_id)
        assert [attempt.ordinal for attempt in attempts] == [1, 2]
        assert attempts[0].status == "failed"
        assert attempts[0].error_code == "acquisition_quality_unmet"
        assert attempts[0].fallback_reason is None
        assert attempts[0].quality_score is not None
        assert attempts[1].status == "succeeded"
        assert attempts[1].fallback_reason == "quality_unmet"
        assert attempts[1].decision_version == "router-v1"

    @pytest.mark.asyncio
    async def test_single_stage_quality_unmet_is_partial(self, router_engine: AsyncEngine) -> None:
        source_id = await create_source(router_engine)
        run_id = await queue_run(router_engine, source_id)
        stage = StageBackend(body=LOW_QUALITY_BODY)
        ok = await run_router(router_engine, run_id, {BackendName.NATIVE_HTTP: stage})
        assert ok is True
        run = await load_run(router_engine, run_id)
        assert run.status == CollectionRunStatus.PARTIAL
        assert run.error_code == "acquisition_quality_unmet"
        assert run.fallback_count == 0
        assert run.quality_score is not None
        attempts = await load_attempts(router_engine, run_id)
        assert len(attempts) == 1
        assert attempts[0].status == "succeeded"
        assert attempts[0].error_code is None

    @pytest.mark.asyncio
    async def test_safety_terminal_never_falls_back(self, router_engine: AsyncEngine) -> None:
        source_id = await create_source(router_engine)
        run_id = await queue_run(router_engine, source_id)
        first = StageBackend(failure=CollectionError("network_policy_denied", "Denied"))
        second = StageBackend()
        chain = (
            RouteCandidate(1, BackendName.NATIVE_HTTP, "native_static"),
            RouteCandidate(2, BackendName.SCRAPLING_HTTP, "static_retry"),
        )
        with patch("app.services.acquisition_route.select_candidates", return_value=chain):
            ok = await run_router(
                router_engine,
                run_id,
                {BackendName.NATIVE_HTTP: first, BackendName.SCRAPLING_HTTP: second},
            )
        assert ok is False
        assert first.calls == 1
        assert second.calls == 0
        run = await load_run(router_engine, run_id)
        assert run.status == CollectionRunStatus.FAILED
        assert run.error_code == "network_policy_denied"
        assert run.fallback_count == 0
        attempts = await load_attempts(router_engine, run_id)
        assert len(attempts) == 1
        assert attempts[0].status == "blocked"

    @pytest.mark.asyncio
    async def test_cumulative_budget_stops_before_second_stage(
        self, router_engine: AsyncEngine
    ) -> None:
        profile = AcquisitionProfileV1()
        profile.resource_budget.max_requests = 1
        source_id = await create_source(router_engine, profile=profile)
        run_id = await queue_run(router_engine, source_id)
        first = StageBackend(failure=CollectionError("http_error", "Transient", retryable=True))
        second = StageBackend()
        chain = (
            RouteCandidate(1, BackendName.NATIVE_HTTP, "native_static"),
            RouteCandidate(2, BackendName.SCRAPLING_HTTP, "static_retry"),
        )
        with patch("app.services.acquisition_route.select_candidates", return_value=chain):
            ok = await run_router(
                router_engine,
                run_id,
                {BackendName.NATIVE_HTTP: first, BackendName.SCRAPLING_HTTP: second},
            )
        assert ok is False
        assert first.calls == 1
        assert second.calls == 0
        run = await load_run(router_engine, run_id)
        assert run.status == CollectionRunStatus.FAILED
        assert run.error_code == "acquisition_budget_exhausted"
        attempts = await load_attempts(router_engine, run_id)
        assert len(attempts) == 1
        assert attempts[0].error_code == "http_error"

    @pytest.mark.asyncio
    async def test_browser_flag_fails_closed_without_transport(
        self, router_engine: AsyncEngine
    ) -> None:
        profile = AcquisitionProfileV1()
        profile.allow_browser = True
        source_id = await create_source(router_engine, profile=profile)
        run_id = await queue_run(router_engine, source_id)
        stage = StageBackend()
        ok = await run_router(router_engine, run_id, {BackendName.NATIVE_HTTP: stage})
        assert ok is False
        assert stage.calls == 0
        run = await load_run(router_engine, run_id)
        assert run.error_code == "acquisition_browser_not_admitted"
        assert run.backend is None
        assert await load_attempts(router_engine, run_id) == []

    @pytest.mark.asyncio
    async def test_circuit_open_blocks_before_transport(self, router_engine: AsyncEngine) -> None:
        source_id = await create_source(router_engine)
        run_id = await queue_run(router_engine, source_id)
        async with AsyncSession(router_engine) as session:
            state = await session.get(SourceAcquisitionState, source_id)
            assert state is not None
            state.consecutive_failures = 5
            state.health_status = SourceHealthStatus.CIRCUIT_OPEN
            state.circuit_open_until = datetime.now(UTC) + timedelta(hours=1)
            await session.commit()
        stage = StageBackend()
        ok = await run_router(router_engine, run_id, {BackendName.NATIVE_HTTP: stage})
        assert ok is False
        assert stage.calls == 0
        run = await load_run(router_engine, run_id)
        assert run.error_code == "acquisition_circuit_open"
        assert run.backend is None
        assert await load_attempts(router_engine, run_id) == []
        state = await load_state(router_engine, source_id)
        assert state.failure_count == 0

    @pytest.mark.asyncio
    async def test_circuit_opens_after_repeated_retryable_failures(
        self, router_engine: AsyncEngine
    ) -> None:
        source_id = await create_source(router_engine)
        failure = CollectionError("http_error", "Transient upstream failure", retryable=True)
        for _ in range(5):
            run_id = await queue_run(router_engine, source_id)
            stage = StageBackend(failure=failure)
            ok = await run_router(router_engine, run_id, {BackendName.NATIVE_HTTP: stage})
            assert ok is False
        state = await load_state(router_engine, source_id)
        assert state.consecutive_failures == 5
        assert state.health_status == SourceHealthStatus.CIRCUIT_OPEN
        assert state.circuit_open_until is not None
        window = state.circuit_open_until - datetime.now(UTC)
        assert timedelta(seconds=700) < window <= timedelta(seconds=900)
        blocked_run = await queue_run(router_engine, source_id)
        blocked_stage = StageBackend()
        ok = await run_router(router_engine, blocked_run, {BackendName.NATIVE_HTTP: blocked_stage})
        assert ok is False
        assert blocked_stage.calls == 0
        run = await load_run(router_engine, blocked_run)
        assert run.error_code == "acquisition_circuit_open"

    @pytest.mark.asyncio
    async def test_policy_denials_do_not_open_circuit(self, router_engine: AsyncEngine) -> None:
        source_id = await create_source(router_engine, url="http://127.0.0.1/private")
        failure = CollectionError("network_policy_denied", "Denied by network policy")
        for _ in range(6):
            run_id = await queue_run(router_engine, source_id)
            ok = await run_router(
                router_engine, run_id, {BackendName.NATIVE_HTTP: StageBackend(failure=failure)}
            )
            assert ok is False
        state = await load_state(router_engine, source_id)
        assert state.consecutive_failures == 0
        assert state.circuit_open_until is None
        assert state.failure_count == 6
        assert state.health_status != SourceHealthStatus.CIRCUIT_OPEN

    @pytest.mark.asyncio
    async def test_duplicate_delivery_records_one_attempt(self, router_engine: AsyncEngine) -> None:
        source_id = await create_source(router_engine)
        run_id = await queue_run(router_engine, source_id)
        first = StageBackend()
        second = StageBackend()
        results = await asyncio.gather(
            run_router(router_engine, run_id, {BackendName.NATIVE_HTTP: first}, task_id="w-a"),
            run_router(router_engine, run_id, {BackendName.NATIVE_HTTP: second}, task_id="w-b"),
        )
        assert sorted(results) == [False, True]
        assert first.calls + second.calls == 1
        attempts = await load_attempts(router_engine, run_id)
        assert len(attempts) == 1
        run = await load_run(router_engine, run_id)
        assert run.status == CollectionRunStatus.SUCCEEDED
        assert run.claim_count == 1

    @pytest.mark.asyncio
    async def test_trace_is_closed_and_leak_free(self, router_engine: AsyncEngine) -> None:
        source_id = await create_source(router_engine, url="https://example.com/article?secret=1")
        run_id = await queue_run(router_engine, source_id)
        stage = StageBackend()
        ok = await run_router(router_engine, run_id, {BackendName.NATIVE_HTTP: stage})
        assert ok is True
        run = await load_run(router_engine, run_id)
        summary = run.budget_summary
        assert summary["decision_version"] == "router-v1"
        traces = summary["trace"]
        assert len(traces) == 1
        trace = traces[0]
        assert set(trace) == TRACE_KEYS
        rendered = json.dumps(trace)
        assert "://" not in rendered
        assert "?" not in rendered
        assert "secret" not in rendered
        attempts = await load_attempts(router_engine, run_id)
        attempt_payload = attempts[0].budget_used
        assert set(attempt_payload) == {"requests", "pages", "bytes_received", "trace"}
        assert set(attempt_payload["trace"]) == TRACE_KEYS

    @pytest.mark.asyncio
    async def test_rss_source_uses_rss_stage(self, router_engine: AsyncEngine) -> None:
        source_id = await create_source(
            router_engine,
            source_type=SourceType.RSS,
            url="https://example.com/feed.xml",
        )
        run_id = await queue_run(router_engine, source_id)
        feed = (
            b"<?xml version='1.0'?><rss version='2.0'><channel><title>F</title>"
            b"<item><title>Item</title><link>https://example.com/a</link>"
            b"<description>Body</description></item></channel></rss>"
        )
        stage = StageBackend(body=feed)
        ok = await run_router(router_engine, run_id, {BackendName.RSS: stage})
        assert ok is True
        run = await load_run(router_engine, run_id)
        assert run.backend == "rss"
        attempts = await load_attempts(router_engine, run_id)
        assert attempts[0].backend == "rss"
        assert attempts[0].decision_version == "router-v1"
