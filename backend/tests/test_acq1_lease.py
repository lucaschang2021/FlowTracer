from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.models.entities import (
    AcquisitionAttempt,
    AcquisitionMode,
    BackendName,
    CollectionRun,
    CollectionRunStatus,
    CollectionTriggerType,
    Source,
    SourceAcquisitionState,
    SourceType,
    User,
)
from app.schemas.resources import AcquisitionProfileV1
from app.services.acquisition import (
    _claim_run,
    _finish_failure,
    execute_run,
    heartbeat_run,
    recover_stale_runs,
)
from app.services.acquisition_run_repository import SqlAlchemyAcquisitionRunRepository
from app.services.acquisition_types import CollectionError, FetchResponse
from app.services.native_acquisition import NativeAcquisitionBackend

TABLES = (
    "acquisition_attempts, source_acquisition_states, raw_items, collection_runs, sources, users"
)


def execute_with_fetcher(
    factory: async_sessionmaker[AsyncSession],
    run_id: UUID,
    *,
    fetcher: object,
    **kwargs: object,
) -> object:
    return execute_run(
        SqlAlchemyAcquisitionRunRepository(factory),
        run_id,
        backend=NativeAcquisitionBackend(fetcher),  # type: ignore[arg-type]
        **kwargs,
    )


@pytest.fixture
async def acq1_engine() -> AsyncEngine:
    database_url = os.environ["TEST_DATABASE_URL"]
    assert "_test" in database_url.rsplit("/", maxsplit=1)[-1]
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    yield engine
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    await engine.dispose()


async def create_queued_run(
    engine: AsyncEngine,
    *,
    mode: AcquisitionMode = AcquisitionMode.AUTO,
    url: str = "https://example.com/article",
) -> UUID:
    async with AsyncSession(engine) as session:
        user = User(
            id=uuid4(),
            email=f"lease-{uuid4()}@example.com",
            password_hash="synthetic",  # noqa: S106 - isolated database fixture
            display_name="Lease",
        )
        source = Source(
            id=uuid4(),
            user_id=user.id,
            name="Lease Source",
            source_type=SourceType.URL,
            url=url,
            normalized_url=url,
            acquisition_mode=mode,
            acquisition_profile=AcquisitionProfileV1().storage_dict(),
        )
        run_id = uuid4()
        run = CollectionRun(
            id=run_id,
            source_id=source.id,
            trigger_type=CollectionTriggerType.MANUAL,
            status=CollectionRunStatus.QUEUED,
        )
        session.add(user)
        await session.flush()
        session.add(source)
        await session.flush()
        session.add_all([SourceAcquisitionState(source_id=source.id), run])
        await session.commit()
        return run_id


async def expire_run(engine: AsyncEngine, run_id: UUID, when: datetime) -> None:
    async with AsyncSession(engine) as session:
        run = await session.get(CollectionRun, run_id)
        assert run is not None
        run.lease_expires_at = when - timedelta(seconds=1)
        await session.commit()


@pytest.mark.asyncio
async def test_lease_claim_heartbeat_stale_recovery_and_old_worker_fencing(
    acq1_engine: AsyncEngine,
) -> None:
    factory = async_sessionmaker(acq1_engine, expire_on_commit=False)
    run_id = await create_queued_run(acq1_engine)
    initial = datetime(2026, 8, 30, tzinfo=UTC)
    claims = await asyncio.gather(
        _claim_run(factory, run_id, worker_id="worker-a", now=initial),
        _claim_run(factory, run_id, worker_id="worker-b", now=initial),
    )
    winners = [claim for claim in claims if claim is not None]
    assert len(winners) == 1
    source, first_token = winners[0]
    assert not await heartbeat_run(factory, run_id, uuid4(), now=initial)
    assert await heartbeat_run(factory, run_id, first_token, now=initial + timedelta(seconds=60))

    await expire_run(acq1_engine, run_id, initial + timedelta(minutes=11))
    assert await recover_stale_runs(factory, now=initial + timedelta(minutes=11)) == 1
    assert not await heartbeat_run(
        factory, run_id, first_token, now=initial + timedelta(minutes=11)
    )

    second_claim = await _claim_run(
        factory, run_id, worker_id="worker-c", now=initial + timedelta(minutes=11)
    )
    assert second_claim is not None
    _second_source, second_token = second_claim
    assert not await _finish_failure(
        factory,
        run_id,
        first_token,
        source,
        BackendName.NATIVE_HTTP,
        initial,
        0,
        CollectionError("http_error", "Safe failure"),
    )
    async with AsyncSession(acq1_engine) as session:
        run = await session.get(CollectionRun, run_id)
        assert run is not None
        assert run.status == CollectionRunStatus.RUNNING
        assert run.claim_token == second_token
        assert await session.scalar(select(func.count()).select_from(AcquisitionAttempt)) == 0

    await expire_run(acq1_engine, run_id, initial + timedelta(minutes=22))
    assert await recover_stale_runs(factory, now=initial + timedelta(minutes=22)) == 1
    third_claim = await _claim_run(
        factory, run_id, worker_id="worker-d", now=initial + timedelta(minutes=22)
    )
    assert third_claim is not None
    await expire_run(acq1_engine, run_id, initial + timedelta(minutes=33))
    assert await recover_stale_runs(factory, now=initial + timedelta(minutes=33)) == 1
    async with AsyncSession(acq1_engine) as session:
        run = await session.get(CollectionRun, run_id)
        assert run is not None
        assert run.status == CollectionRunStatus.FAILED
        assert run.claim_count == 3
        assert run.error_code == "run_lease_exhausted"


class OfflineFetcher:
    def __init__(self) -> None:
        self.called = False

    async def fetch(self, url: str, source_type: SourceType) -> FetchResponse:
        self.called = True
        assert source_type == SourceType.URL
        return FetchResponse(
            final_url=url,
            content_type="text/html; charset=utf-8",
            body=(
                b"<html><head><title>Lease evidence</title></head><body><main>"
                b"Deterministic offline acquisition content for exactly-once evidence."
                b"</main></body></html>"
            ),
        )


@pytest.mark.asyncio
async def test_duplicate_delivery_creates_one_attempt_and_updates_health(
    acq1_engine: AsyncEngine,
) -> None:
    factory = async_sessionmaker(acq1_engine, expire_on_commit=False)
    run_id = await create_queued_run(acq1_engine)
    results = await asyncio.gather(
        execute_with_fetcher(factory, run_id, fetcher=OfflineFetcher(), task_id="delivery-a"),
        execute_with_fetcher(factory, run_id, fetcher=OfflineFetcher(), task_id="delivery-b"),
    )
    assert sorted(results) == [False, True]
    async with AsyncSession(acq1_engine) as session:
        run = await session.get(CollectionRun, run_id)
        assert run is not None
        attempts = list(
            (
                await session.scalars(
                    select(AcquisitionAttempt).where(AcquisitionAttempt.run_id == run_id)
                )
            ).all()
        )
        state = await session.get(SourceAcquisitionState, run.source_id)
        assert run.status == CollectionRunStatus.SUCCEEDED
        assert run.claim_count == 1
        assert run.backend == "native_http"
        assert len(attempts) == 1
        assert attempts[0].status == "succeeded"
        assert attempts[0].decision_version == "acquisition-native-v1"
        assert state is not None
        assert state.success_count == 1
        assert state.failure_count == 0
        assert state.health_status == "healthy"


@pytest.mark.asyncio
async def test_unavailable_mode_and_network_policy_stop_before_transport(
    acq1_engine: AsyncEngine,
) -> None:
    factory = async_sessionmaker(acq1_engine, expire_on_commit=False)

    dynamic_run_id = await create_queued_run(
        acq1_engine,
        mode=AcquisitionMode.DYNAMIC,
    )
    dynamic_fetcher = OfflineFetcher()
    assert not await execute_with_fetcher(factory, dynamic_run_id, fetcher=dynamic_fetcher)
    assert not dynamic_fetcher.called

    blocked_run_id = await create_queued_run(
        acq1_engine,
        url="http://127.0.0.1/private",
    )
    blocked_fetcher = OfflineFetcher()
    assert not await execute_with_fetcher(factory, blocked_run_id, fetcher=blocked_fetcher)
    assert not blocked_fetcher.called

    async with AsyncSession(acq1_engine) as session:
        dynamic_run = await session.get(CollectionRun, dynamic_run_id)
        blocked_run = await session.get(CollectionRun, blocked_run_id)
        assert dynamic_run is not None
        assert blocked_run is not None
        assert dynamic_run.error_code == "acquisition_mode_unsupported"
        assert dynamic_run.backend is None
        assert blocked_run.error_code == "network_policy_denied"
        dynamic_attempts = await session.scalar(
            select(func.count())
            .select_from(AcquisitionAttempt)
            .where(AcquisitionAttempt.run_id == dynamic_run_id)
        )
        blocked_attempts = list(
            (
                await session.scalars(
                    select(AcquisitionAttempt).where(AcquisitionAttempt.run_id == blocked_run_id)
                )
            ).all()
        )
        assert dynamic_attempts == 0
        assert len(blocked_attempts) == 1
        assert blocked_attempts[0].status == "blocked"
        dynamic_state = await session.get(SourceAcquisitionState, dynamic_run.source_id)
        blocked_state = await session.get(SourceAcquisitionState, blocked_run.source_id)
        assert dynamic_state is not None
        assert blocked_state is not None
        assert dynamic_state.failure_count == 0
        assert dynamic_state.last_backend is None
        assert blocked_state.failure_count == 1
        assert blocked_state.last_backend == "native_http"
