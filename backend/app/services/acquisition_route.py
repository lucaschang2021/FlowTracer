"""ACQ-1C Router v1 run execution: circuit gate, ordered static stages, quality gate,
cumulative budget ledger, leak-free decision traces, and the WP-5 I2 crawl wiring
(ADR-034 / docs/57 / docs/61). The routed run path lives here; the legacy
single-backend path stays in ``app.services.acquisition`` and Browser backends are
never selected (the candidate table is static and the browser tail stays disabled).
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
    CrawlTransport,
    RunClaim,
    SourceRuntimeFacts,
)
from app.models.entities import BackendName, Source, SourceType
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
from app.services.discovery_crawl import (
    CrawlOutcome,
    crawl_context_for,
    discovery_enabled,
    execute_discovery_crawl,
    plan_seed_page,
)
from app.services.discovery_frontier import DiscoveryPlan
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
        discovery_transport: CrawlTransport | None = None,
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
        self.discovery_transport = discovery_transport
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
    discovery_transport: CrawlTransport | None = None,
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
        discovery_transport=discovery_transport,
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
    now = datetime.now(UTC)
    blocked = circuit_blocks(facts, now)
    if blocked is not None:
        raise CollectionError(blocked, "Source circuit is open", retryable=False)
    if facts is not None and facts.circuit_open_until is not None:
        # The window has expired (circuit_blocks admitted it): this is the half-open
        # state. Exactly one probe may proceed — the atomic claim loses for every
        # concurrent run, which refuses without transmitting.
        if not await route.repository.claim_circuit_probe(route.source.id, now=now):
            raise CollectionError(
                "acquisition_circuit_open", "Source circuit is open", retryable=False
            )
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
    effective = effective_resource_budget(profile)
    # The controlled static-retry stage exists only when the effective budget can fund
    # a second page/request (ADR-038); the default profile stays single-stage.
    allow_static_retry = effective.max_pages >= 2 and effective.max_requests >= 2
    candidates = select_candidates(
        source_type=route.source.source_type,
        mode=route.source.acquisition_mode,
        allow_browser=bool(profile.allow_browser),
        allow_static_retry=allow_static_retry,
    )
    chain: list[tuple[RouteCandidate, RunBackend]] = []
    for candidate in candidates:
        implementation = route.backends.get(candidate.backend)
        if implementation is None:
            if candidate.stage > 1:
                # A fallback stage whose backend is not wired in this worker is simply
                # unavailable; the primary stage must always resolve.
                continue
            raise CollectionError(
                "acquisition_no_backend",
                "No acquisition backend is available for this source",
            )
        chain.append((candidate, implementation))
    if not chain:  # pragma: no cover - the primary candidate is always present
        raise CollectionError(
            "acquisition_no_backend", "No acquisition backend is available for this source"
        )
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
    crawl = await _run_crawl(route, candidate, plan)
    discovery_summary: dict[str, Any] | None = None
    if plan is not None:
        discovery_summary = dict(plan.summary)
        discovery_summary["crawl"] = (
            {"skipped_reason": "no_crawl_transport"} if crawl is None else crawl.summary
        )
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
            discovery=discovery_summary,
            throttle={
                **route.throttle_snapshot,
                "delays_applied_ms": tuple(route.site_gate.delays_applied_ms),
            },
        ),
        decision_version=ROUTER_VERSION,
        attempt_budget_used={**evaluation.usage, "trace": evaluation.trace},
        discovery_checkpoint=(plan.checkpoint if plan is not None and crawl is None else None),
        crawl_pages_fetched=0 if crawl is None else crawl.pages_fetched,
        crawl_pages_failed=0 if crawl is None else crawl.pages_failed,
        crawl_observed=(None if crawl is None or not crawl.started else crawl.observed_keys),
    )
    if completion is None:
        return False
    await _publish_repository_event(route.repository, route.run_id, route.publisher)
    crawl_item_ids = () if crawl is None else crawl.raw_item_ids
    _dispatch_raw_items(route, completion.raw_item_ids + crawl_item_ids)
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


def _plan_discovery(route: _RouteRun, evaluation: _StageEvaluation) -> DiscoveryPlan | None:
    if route.profile is None or not discovery_enabled(
        route.source.source_type, route.source.discovery_mode
    ):
        return None
    if not evaluation.met:  # planning follows only accepted-quality pages
        return None
    return plan_seed_page(
        source=route.source,
        profile=route.profile,
        response=evaluation.result.response,
        checkpoint=route.discovery_checkpoint,
    )


async def _run_crawl(
    route: _RouteRun, candidate: RouteCandidate, plan: DiscoveryPlan | None
) -> CrawlOutcome | None:
    if plan is None or route.discovery_transport is None or route.profile is None:
        return None  # I1 path: no crawl transport wired into this worker
    return await execute_discovery_crawl(
        crawl_context_for(
            repository=route.repository,
            claim=route.claimed,
            source=route.source,
            profile=route.profile,
            plan=plan,
            transport=route.discovery_transport,
            site_gate=route.site_gate,
            backend_name=candidate.backend,
            base_ordinal=candidate.stage,
            seed_started_monotonic=route.started,
            ledger=route.ledger.totals,
        )
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
