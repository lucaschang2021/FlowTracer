"""ACQ-1C Router v1 run execution: circuit gate, ordered static stages, quality gate,
cumulative budget ledger, and leak-free decision traces (ADR-034 / docs/57).

This module owns the routed run path; ``app.services.acquisition`` keeps the legacy
single-backend path. Browser backends are never selected here: candidate stages come
from the frozen static table while the browser tail stays disabled.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.logging import get_logger
from app.domains.acquisition_ports import (
    AcquisitionBackend as AcquisitionBackendPort,
)
from app.domains.acquisition_ports import (
    AcquisitionRunRepository,
    PublishedEvent,
    RunClaim,
    SourceRuntimeFacts,
)
from app.models.entities import (
    AcquisitionAttempt,
    AcquisitionAttemptStatus,
    BackendName,
    CollectionRun,
    CollectionRunStatus,
    Source,
    SourceAcquisitionState,
    SourceType,
)
from app.schemas.resources import AcquisitionProfileV1
from app.services.acquisition_parsers import parse_feed, parse_html
from app.services.acquisition_policy import (
    EffectiveResourceBudget,
    effective_resource_budget,
    effective_site_policy,
)
from app.services.acquisition_router import (
    ROUTER_VERSION,
    SAFETY_TERMINAL_CODES,
    RouteBudgetLedger,
    RouteCandidate,
    attempt_trace,
    attempt_usage,
    circuit_blocks,
    quality_met,
    route_summary,
    select_candidates,
    throttle_delay_ms,
)
from app.services.acquisition_types import (
    AcquisitionRequest,
    AcquisitionResult,
    CollectionError,
    ParseResult,
)
from app.services.events import EventPublisher, publish_safely
from app.services.extraction import attach_extraction_observations
from app.services.extraction_quality import aggregate_quality

DECISION_VERSION = "acquisition-native-v1"
Dispatch = Callable[[str, str], None]
RunRepository = AcquisitionRunRepository[Source, AcquisitionResult, ParseResult, Any]
RunBackend = AcquisitionBackendPort[AcquisitionRequest, AcquisitionResult]


def _attempt(
    *,
    run_id: UUID,
    source_id: UUID,
    backend: BackendName,
    started_at: datetime,
    finished_at: datetime,
    status: AcquisitionAttemptStatus,
    requested_url: str,
    response_url: str | None = None,
    status_code: int | None = None,
    content_type: str | None = None,
    retry_count: int = 0,
    bytes_received: int = 0,
    error: CollectionError | None = None,
    quality_score: Decimal | None = None,
    ordinal: int = 1,
    fallback_reason: str | None = None,
    budget_used: dict[str, Any] | None = None,
    decision_version: str = DECISION_VERSION,
) -> AcquisitionAttempt:
    pages = 1 if status == AcquisitionAttemptStatus.SUCCEEDED else 0
    return AcquisitionAttempt(
        run_id=run_id,
        source_id=source_id,
        ordinal=ordinal,
        backend=backend,
        started_at=started_at,
        finished_at=finished_at,
        status=status,
        requested_url=requested_url,
        final_url=response_url,
        status_code=status_code,
        content_type=content_type,
        duration_ms=max(0, round((finished_at - started_at).total_seconds() * 1000)),
        retry_count=retry_count,
        pages=pages,
        bytes_received=bytes_received,
        budget_used=(
            budget_used
            if budget_used is not None
            else {
                "requests": retry_count + 1,
                "pages": pages,
                "bytes_received": bytes_received,
            }
        ),
        error_code=None if error is None else error.code,
        safe_error=None if error is None else error.safe_message,
        decision_version=decision_version,
        quality_score=quality_score,
        fallback_reason=fallback_reason,
    )


async def _circuit_facts(
    factory: async_sessionmaker[AsyncSession], source_id: UUID
) -> SourceRuntimeFacts | None:
    async with factory() as session:
        state = await session.scalar(
            select(SourceAcquisitionState).where(SourceAcquisitionState.source_id == source_id)
        )
        if state is None:
            return None
        return SourceRuntimeFacts(
            health_status=state.health_status.value,
            consecutive_failures=state.consecutive_failures,
            circuit_open_until=state.circuit_open_until,
            last_error_code=state.last_error_code,
            latency_ewma_ms=state.latency_ewma_ms,
        )


async def _record_attempt(
    factory: async_sessionmaker[AsyncSession],
    run_id: UUID,
    claim_token: UUID,
    *,
    source_id: UUID,
    ordinal: int,
    backend: BackendName,
    requested_url: str,
    started_at: datetime,
    finished_at: datetime,
    status: AcquisitionAttemptStatus,
    retry_count: int,
    error_code: str,
    safe_error: str,
    quality_score: Decimal | None = None,
    fallback_reason: str | None = None,
    budget_used: dict[str, Any] | None = None,
    bytes_received: int = 0,
    decision_version: str = ROUTER_VERSION,
) -> bool:
    """Persist one intermediate route attempt without touching run or source state."""
    async with factory() as session:
        run = await session.scalar(
            select(CollectionRun).where(
                CollectionRun.id == run_id,
                CollectionRun.status == CollectionRunStatus.RUNNING,
                CollectionRun.claim_token == claim_token,
            )
        )
        if run is None:
            return False
        session.add(
            _attempt(
                run_id=run_id,
                source_id=source_id,
                backend=backend,
                started_at=started_at,
                finished_at=finished_at,
                status=status,
                requested_url=requested_url,
                retry_count=retry_count,
                bytes_received=bytes_received,
                error=CollectionError(error_code, safe_error),
                quality_score=quality_score,
                ordinal=ordinal,
                fallback_reason=fallback_reason,
                budget_used=budget_used,
                decision_version=decision_version,
            )
        )
        await session.commit()
        return True


async def _repository_heartbeat_loop(repository: RunRepository, claim: RunClaim[Source]) -> None:
    while True:
        await asyncio.sleep(60)
        if not await repository.heartbeat(claim.run_id, claim.claim_token):
            return


async def _publish_repository_event(
    repository: RunRepository,
    run_id: UUID,
    publisher: EventPublisher | None,
) -> None:
    published: PublishedEvent[Any] | None = await repository.event_for(run_id)
    if published is not None:
        await publish_safely(
            publisher,
            user_id=published.user_id,
            event=published.event,
            resource_id=run_id,
        )


@dataclass(frozen=True, slots=True)
class _StageEvaluation:
    met: bool
    parsed: ParseResult
    result: AcquisitionResult
    aggregate: Decimal | None
    usage: dict[str, int]
    trace: dict[str, object]


class _RouteRun:
    """Mutable per-run route state shared by the staged helpers."""

    def __init__(
        self,
        repository: RunRepository,
        claimed: RunClaim[Source],
        run_id: UUID,
        *,
        backends: Mapping[BackendName, RunBackend],
        correlation_id: str | None,
        task_id: str | None,
        raw_dispatch: Dispatch | None,
        publisher: EventPublisher | None,
        started: float,
    ) -> None:
        self.repository = repository
        self.claimed = claimed
        self.run_id = run_id
        self.source = claimed.source
        self.backends = backends
        self.correlation_id = correlation_id
        self.task_id = task_id
        self.raw_dispatch = raw_dispatch
        self.publisher = publisher
        self.started = started
        self.router_started_at = datetime.now(UTC)
        self.stage_started_at = self.router_started_at
        self.backend_name = (
            BackendName.RSS
            if self.source.source_type == SourceType.RSS
            else BackendName.NATIVE_HTTP
        )
        self.stage = 1
        self.refusal_before_transport = False
        self.ledger = RouteBudgetLedger()
        self.traces: list[dict[str, object]] = []
        self.fallback_reason: str | None = None
        self.budget: EffectiveResourceBudget | None = None
        self.chain: list[tuple[RouteCandidate, RunBackend]] = []


async def execute_route_run(
    repository: RunRepository,
    run_id: UUID,
    *,
    backends: Mapping[BackendName, RunBackend],
    correlation_id: str | None = None,
    task_id: str | None = None,
    raw_dispatch: Dispatch | None = None,
    publisher: EventPublisher | None = None,
) -> bool:
    """Routed run entrypoint: claim, then execute the ordered static stage chain."""
    started = time.monotonic()
    worker_id = (task_id or correlation_id or f"worker-{uuid.uuid4()}").strip()
    claimed = await repository.claim_run(run_id, worker_id=worker_id)
    if claimed is None:
        await _publish_repository_event(repository, run_id, publisher)
        return False
    route = _RouteRun(
        repository,
        claimed,
        run_id,
        backends=backends,
        correlation_id=correlation_id,
        task_id=task_id,
        raw_dispatch=raw_dispatch,
        publisher=publisher,
        started=started,
    )
    return await _run_claimed(route)


async def _run_claimed(route: _RouteRun) -> bool:
    heartbeat = asyncio.create_task(_repository_heartbeat_loop(route.repository, route.claimed))
    await _publish_repository_event(route.repository, route.run_id, route.publisher)
    try:
        try:
            return await _route_attempts(route)
        except CollectionError as exc:
            return await _finalize_failure(route, exc)
        except Exception:
            error = CollectionError("internal_collection_error", "Collection failed unexpectedly")
            return await _finalize_failure(route, error)
    finally:
        heartbeat.cancel()
        with suppress(asyncio.CancelledError):
            await heartbeat


async def _route_attempts(route: _RouteRun) -> bool:
    try:
        profile = AcquisitionProfileV1.model_validate(route.source.acquisition_profile)
    except ValueError:
        raise CollectionError(
            "source_profile_invalid", "Source acquisition profile is invalid"
        ) from None
    route.chain = _select_chain(route, profile)
    facts = await route.repository.circuit_facts(route.source.id)
    blocked = circuit_blocks(facts, datetime.now(UTC))
    if blocked is not None:
        raise CollectionError(blocked, "Source circuit is open", retryable=False)
    await _apply_throttle(route, facts, profile)
    route.budget = effective_resource_budget(profile)
    request = AcquisitionRequest(
        source_id=route.source.id,
        run_id=route.run_id,
        target_url=route.source.normalized_url,
        source_type=route.source.source_type,
        source_family=route.source.source_family,
        mode=route.source.acquisition_mode,
        discovery_mode=route.source.discovery_mode,
        profile=profile,
        correlation_id=route.correlation_id,
    )
    for candidate, implementation in route.chain:
        evaluation = await _run_stage(route, candidate, implementation, request, profile)
        if evaluation is None:
            continue
        if not evaluation.met and candidate.stage != len(route.chain):
            await _persist_quality_miss(route, candidate, evaluation)
            continue
        return await _finalize_success(route, candidate, evaluation)
    raise CollectionError("internal_collection_error", "Collection failed unexpectedly")


def _select_chain(
    route: _RouteRun, profile: AcquisitionProfileV1
) -> list[tuple[RouteCandidate, RunBackend]]:
    candidates = select_candidates(
        source_type=route.source.source_type,
        mode=route.source.acquisition_mode,
        profile=profile,
    )
    chain: list[tuple[RouteCandidate, RunBackend]] = []
    for candidate in candidates:
        implementation = route.backends.get(candidate.backend)
        if implementation is None:
            raise CollectionError(
                "acquisition_no_backend",
                "No acquisition backend is available for this source",
            )
        chain.append((candidate, implementation))
    return chain


async def _apply_throttle(
    route: _RouteRun,
    facts: SourceRuntimeFacts | None,
    profile: AcquisitionProfileV1,
) -> None:
    crawl_delay_ms = effective_site_policy(profile, route.source.normalized_url).crawl_delay_ms
    delay_ms = throttle_delay_ms(facts, crawl_delay_ms=crawl_delay_ms)
    if delay_ms <= 0:
        return
    get_logger().info(
        "collection_throttled",
        message="Adaptive throttle delay applied",
        run_id=str(route.run_id),
        source_id=str(route.source.id),
        correlation_id=route.correlation_id,
        delay_ms=delay_ms,
    )
    await asyncio.sleep(delay_ms / 1000)


def _evaluate_stage(
    route: _RouteRun, result: AcquisitionResult, profile: AcquisitionProfileV1
) -> tuple[ParseResult, AcquisitionResult, Decimal | None, dict[str, int]]:
    response = result.response
    parsed = (
        parse_feed(response)
        if route.source.source_type == SourceType.RSS
        else parse_html(response, route.source.normalized_url)
    )
    result = attach_extraction_observations(
        result,
        family=route.source.source_family,
        content_profile=profile.content_profile.value,
        source_type=route.source.source_type,
        parsed=parsed,
    )
    aggregate = aggregate_quality(
        [observation.evidence.quality_score for observation in result.observations]
    )
    return parsed, result, aggregate, attempt_usage(result.budget_used)


async def _run_stage(
    route: _RouteRun,
    candidate: RouteCandidate,
    implementation: RunBackend,
    request: AcquisitionRequest,
    profile: AcquisitionProfileV1,
) -> _StageEvaluation | None:
    route.stage = candidate.stage
    route.backend_name = candidate.backend
    if route.budget is not None and route.ledger.exceeds(route.budget):
        # No transport reaches this stage; the refusal is recorded on the run only.
        route.refusal_before_transport = True
        raise CollectionError(
            "acquisition_budget_exhausted", "Acquisition resource budget is exhausted"
        )
    route.stage_started_at = datetime.now(UTC)
    try:
        result = await implementation.acquire(request)
    except CollectionError as exc:
        usage = attempt_usage({"requests": exc.retry_count + 1})
        route.ledger.charge_requests(exc.retry_count + 1)
        trace = attempt_trace(
            ordinal=candidate.stage,
            backend=candidate.backend,
            outcome="failed",
            error_code=exc.code,
            retry_count=exc.retry_count,
            usage=usage,
            quality_score=None,
            fallback_reason=route.fallback_reason,
        )
        route.traces.append(trace)
        if exc.code in SAFETY_TERMINAL_CODES or candidate.stage == len(route.chain):
            raise
        await _persist_stage_failure(route, candidate, exc, trace, usage)
        return None
    parsed, result, aggregate, usage = _evaluate_stage(route, result, profile)
    route.ledger.charge(usage)
    met = quality_met(aggregate)
    trace = attempt_trace(
        ordinal=candidate.stage,
        backend=candidate.backend,
        outcome="succeeded" if met else "failed",
        error_code=None if met else "acquisition_quality_unmet",
        retry_count=result.retry_count,
        usage=usage,
        quality_score=aggregate,
        fallback_reason=route.fallback_reason,
    )
    route.traces.append(trace)
    return _StageEvaluation(met, parsed, result, aggregate, usage, trace)


async def _persist_stage_failure(
    route: _RouteRun,
    candidate: RouteCandidate,
    exc: CollectionError,
    trace: dict[str, object],
    usage: dict[str, int],
) -> None:
    persisted = await route.repository.record_attempt(
        route.claimed,
        ordinal=candidate.stage,
        backend_name=candidate.backend.value,
        attempt_started_at=route.stage_started_at,
        attempt_finished_at=datetime.now(UTC),
        status="failed",
        retry_count=exc.retry_count,
        error_code=exc.code,
        safe_error=exc.safe_message,
        fallback_reason=route.fallback_reason,
        budget_used={**usage, "trace": trace},
    )
    if not persisted:
        raise CollectionError("internal_collection_error", "Collection failed unexpectedly")
    route.fallback_reason = exc.code


async def _persist_quality_miss(
    route: _RouteRun,
    candidate: RouteCandidate,
    evaluation: _StageEvaluation,
) -> None:
    persisted = await route.repository.record_attempt(
        route.claimed,
        ordinal=candidate.stage,
        backend_name=candidate.backend.value,
        attempt_started_at=route.stage_started_at,
        attempt_finished_at=datetime.now(UTC),
        status="failed",
        retry_count=evaluation.result.retry_count,
        error_code="acquisition_quality_unmet",
        safe_error="Extraction quality did not reach the acceptable bucket",
        quality_score=evaluation.aggregate,
        fallback_reason=route.fallback_reason,
        budget_used={**evaluation.usage, "trace": evaluation.trace},
        bytes_received=len(evaluation.result.response.body),
    )
    if not persisted:
        raise CollectionError("internal_collection_error", "Collection failed unexpectedly")
    route.fallback_reason = "quality_unmet"


async def _finalize_success(
    route: _RouteRun,
    candidate: RouteCandidate,
    evaluation: _StageEvaluation,
) -> bool:
    completion = await route.repository.finish_success(
        route.claimed,
        backend_name=candidate.backend.value,
        attempt_started_at=route.stage_started_at,
        run_started_at=route.router_started_at,
        result=evaluation.result,
        parsed=evaluation.parsed,
        quality_score=evaluation.aggregate,
        quality_met=evaluation.met,
        fallback_count=candidate.stage - 1,
        attempt_ordinal=candidate.stage,
        fallback_reason=route.fallback_reason,
        budget_summary=route_summary(route.traces, accepted_backend=candidate.backend),
        decision_version=ROUTER_VERSION,
        attempt_budget_used={**evaluation.usage, "trace": evaluation.trace},
    )
    if completion is None:
        return False
    await _publish_repository_event(route.repository, route.run_id, route.publisher)
    _dispatch_raw_items(route, completion.raw_item_ids)
    get_logger().info(
        "collection_completed",
        message="Collection run completed",
        run_id=str(route.run_id),
        source_id=str(route.source.id),
        correlation_id=route.correlation_id,
        task_id=route.task_id,
        status=completion.status,
        backend=candidate.backend.value,
        fallback_count=candidate.stage - 1,
        fetched_count=completion.fetched_count,
        created_count=completion.created_count,
        duplicate_count=completion.duplicate_count,
        failed_count=completion.failed_count,
        retry_count=evaluation.result.retry_count,
        duration_ms=round((time.monotonic() - route.started) * 1000),
    )
    return True


def _dispatch_raw_items(route: _RouteRun, raw_item_ids: tuple[UUID, ...]) -> None:
    if route.raw_dispatch is None:
        return
    for raw_item_id in raw_item_ids:
        try:
            route.raw_dispatch(str(raw_item_id), route.correlation_id or str(raw_item_id))
        except Exception:
            get_logger().warning(
                "cleaning_queue_unavailable",
                message="Cleaning queue is temporarily unavailable",
                raw_item_id=str(raw_item_id),
                correlation_id=route.correlation_id,
                error_code="analysis_queue_unavailable",
            )


async def _finalize_failure(route: _RouteRun, exc: CollectionError) -> bool:
    updated = await route.repository.finish_failure(
        route.claimed,
        backend_name=route.backend_name.value,
        attempt_started_at=route.stage_started_at,
        retries=exc.retry_count,
        error_code=exc.code,
        safe_error=exc.safe_message,
        run_started_at=route.router_started_at,
        attempt_ordinal=route.stage,
        fallback_count=max(0, route.stage - 1),
        record_attempt=not route.refusal_before_transport,
    )
    await _publish_repository_event(route.repository, route.run_id, route.publisher)
    if not updated:
        return False
    get_logger().warning(
        "collection_failed",
        message=exc.safe_message,
        run_id=str(route.run_id),
        source_id=str(route.source.id),
        correlation_id=route.correlation_id,
        task_id=route.task_id,
        status="failed",
        error_code=exc.code,
        backend=route.backend_name.value,
        fallback_count=max(0, route.stage - 1),
        fetched_count=0,
        created_count=0,
        duplicate_count=0,
        failed_count=1,
        retry_count=exc.retry_count,
        duration_ms=round((time.monotonic() - route.started) * 1000),
    )
    return False
