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
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.core.logging import get_logger
from app.domains.acquisition_ports import (
    AcquisitionBackend as AcquisitionBackendPort,
)
from app.domains.acquisition_ports import (
    AcquisitionRunRepository,
    RunClaim,
    SourceRuntimeFacts,
)
from app.models.entities import BackendName, DiscoveryMode, Source, SourceType
from app.services.acquisition import (
    _publish_repository_event,
    _repository_heartbeat_loop,
    validate_source_profile,
)
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
    AttemptBudget,
    CollectionError,
    ParseResult,
)
from app.services.discovery_frontier import DiscoveryPlan, plan_discovery
from app.services.extraction import attach_extraction_observations
from app.services.extraction_quality import aggregate_quality
from app.services.site_gate import SiteGate

Dispatch = Callable[[str, str], None]
RunRepository = AcquisitionRunRepository[Source, AcquisitionResult, ParseResult, Any]
RunBackend = AcquisitionBackendPort[AcquisitionRequest, AcquisitionResult]


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
        publisher: Any | None,
        started: float,
        site_gate: SiteGate | None = None,
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
        self.site_gate = site_gate if site_gate is not None else SiteGate()
        self.throttle_snapshot: dict[str, int] = {}
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
        self.profile: Any | None = None
        self.discovery_checkpoint: dict[str, Any] | None = None


async def execute_route_run(
    repository: RunRepository,
    run_id: UUID,
    *,
    backends: Mapping[BackendName, RunBackend],
    correlation_id: str | None = None,
    task_id: str | None = None,
    raw_dispatch: Dispatch | None = None,
    publisher: Any | None = None,
    site_gate: SiteGate | None = None,
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
        site_gate=site_gate,
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
        profile = validate_source_profile(route.source.acquisition_profile)
    except ValueError:
        raise CollectionError(
            "source_profile_invalid", "Source acquisition profile is invalid"
        ) from None
    route.profile = profile
    route.chain = _select_chain(route, profile)
    facts = await route.repository.circuit_facts(route.source.id)
    blocked = circuit_blocks(facts, datetime.now(UTC))
    if blocked is not None:
        raise CollectionError(blocked, "Source circuit is open", retryable=False)
    await _apply_throttle(route, facts, profile)
    route.budget = effective_resource_budget(profile)
    if discovery_enabled(route.source.source_type, route.source.discovery_mode):
        route.discovery_checkpoint = await route.repository.discovery_checkpoint(route.source.id)
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


def _select_chain(route: _RouteRun, profile: Any) -> list[tuple[RouteCandidate, RunBackend]]:
    candidates = select_candidates(
        source_type=route.source.source_type,
        mode=route.source.acquisition_mode,
        allow_browser=bool(profile.allow_browser),
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
    profile: Any,
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
    route: _RouteRun, result: AcquisitionResult, profile: Any
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


def _remaining_attempt_budget(route: _RouteRun) -> AttemptBudget | None:
    """Remaining effective budget for the next attempt, from the cumulative ledger."""
    if route.budget is None:
        return None
    remaining_requests = max(1, route.budget.max_requests - route.ledger.totals["requests"])
    remaining_bytes = max(0, route.budget.max_total_bytes - route.ledger.totals["bytes_received"])
    return AttemptBudget(
        max_requests=remaining_requests,
        max_bytes=remaining_bytes,
        deadline_monotonic=route.started + float(route.budget.max_duration_seconds),
    )


async def _run_stage(
    route: _RouteRun,
    candidate: RouteCandidate,
    implementation: RunBackend,
    request: AcquisitionRequest,
    profile: Any,
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
    site_policy = effective_site_policy(profile, route.source.normalized_url)
    route.throttle_snapshot = {
        "crawl_delay_ms": site_policy.crawl_delay_ms,
        "requests_per_minute": site_policy.requests_per_minute,
        "max_parallel_requests": site_policy.max_parallel_requests,
        "enforced_in_flight": route.site_gate.enforced_in_flight,
    }
    stage_request = replace(request, remaining_budget=_remaining_attempt_budget(route))
    try:
        # Every request passes the execution gate: crawl delay / RPM spacing are slept
        # out between requests, and same-host requests are serialized.
        async with route.site_gate.guard(
            site_policy.origin_host,
            crawl_delay_ms=site_policy.crawl_delay_ms,
            requests_per_minute=site_policy.requests_per_minute,
        ):
            result = await implementation.acquire(stage_request)
    except CollectionError as exc:
        # Bill the real request count (initial + redirect hops + retries); fall back to
        # the conservative retry-derived count when the failure carries no transport count.
        requests_made = max(exc.retry_count + 1, exc.requests_made or 0)
        usage = attempt_usage({"requests": requests_made})
        route.ledger.charge_requests(requests_made)
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
    plan = _plan_discovery(route, evaluation)
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
        budget_summary=route_summary(
            route.traces,
            accepted_backend=candidate.backend,
            discovery=None if plan is None else plan.summary,
            throttle={
                **route.throttle_snapshot,
                "delays_applied_ms": tuple(route.site_gate.delays_applied_ms),
            },
        ),
        decision_version=ROUTER_VERSION,
        attempt_budget_used={**evaluation.usage, "trace": evaluation.trace},
        discovery_checkpoint=None if plan is None else plan.checkpoint,
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


def discovery_enabled(source_type: SourceType, mode: DiscoveryMode) -> bool:
    """Discovery planning applies to URL sources that opted into a scope beyond single page."""
    return source_type == SourceType.URL and mode != DiscoveryMode.SINGLE_PAGE


def _plan_discovery(route: _RouteRun, evaluation: _StageEvaluation) -> DiscoveryPlan | None:
    """Plan+checkpoint for one accepted URL page; None when discovery is inactive."""
    if route.profile is None or not discovery_enabled(
        route.source.source_type, route.source.discovery_mode
    ):
        return None
    if not evaluation.met:
        return None
    policy = effective_site_policy(route.profile, route.source.normalized_url)
    budget = route.profile.resource_budget
    response = evaluation.result.response
    return plan_discovery(
        seed_url=route.source.normalized_url,
        body=response.body,
        content_type=response.content_type,
        final_url=response.final_url,
        scope=route.source.discovery_mode,
        approved_domains=frozenset(policy.approved_domains),
        allow_paths=policy.allow_paths,
        deny_paths=policy.deny_paths,
        checkpoint=route.discovery_checkpoint,
        max_depth=int(budget.max_depth),
        max_discovered_urls=max(0, int(budget.max_pages)) * 5,
    )


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
