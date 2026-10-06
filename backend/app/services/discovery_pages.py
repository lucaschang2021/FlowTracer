"""Per-page crawl steps for the WP-5 I2 crawl execution (docs/61 §5/§6).

One module owns the mutable crawl state and every step that persists a page
attempt: validated fetch through the injected transport, page evaluation, child
planning, and the claim-guarded CAS commit of the checkpoint together with the
page record. The loop/budget/robots control lives in ``discovery_crawl``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

from app.domains.acquisition_ports import (
    AcquisitionRunRepository as RunRepositoryPort,
)
from app.domains.acquisition_ports import (
    CrawlFetched,
    CrawlPageRecord,
    CrawlStepResult,
    CrawlTransport,
    RunClaim,
)
from app.models.entities import BackendName, DiscoveryMode, Source, SourceFamily, SourceType
from app.services.acquisition_parsers import parse_html
from app.services.acquisition_policy import (
    EffectiveResourceBudget,
    EffectiveSitePolicy,
    NetworkPolicy,
)
from app.services.acquisition_router import quality_met
from app.services.acquisition_types import (
    AcquisitionResult,
    CollectionError,
    FetchResponse,
    ParseResult,
)
from app.services.change_tracking import artifact_key_for
from app.services.discovery_frontier import (
    DiscoveryPlan,
    crawl_begin_page,
    crawl_fail_page,
    crawl_finish_success,
    crawl_lease,
    frontier_entry_hash,
    lease_is_active,
    plan_discovery,
)
from app.services.discovery_policy import scope_allows
from app.services.extraction import attach_extraction_observations
from app.services.extraction_quality import aggregate_quality
from app.services.site_gate import SiteGate

RunRepository = RunRepositoryPort[Source, AcquisitionResult, ParseResult, Any]

MAX_TARGET_ATTEMPTS = 3


@dataclass(frozen=True, slots=True)
class CrawlContext:
    """Everything one crawl execution needs, assembled by the routed run path."""

    repository: RunRepository
    claim: RunClaim[Source]
    seed_url: str
    scope: DiscoveryMode
    approved_domains: frozenset[str]
    policy: EffectiveSitePolicy
    budget: EffectiveResourceBudget
    plan: DiscoveryPlan
    transport: CrawlTransport
    site_gate: SiteGate
    backend_name: BackendName
    base_ordinal: int
    max_depth: int
    max_frontier_size: int
    max_discovered_urls: int
    min_score: int
    source_family: SourceFamily
    content_profile: str
    seed_started_monotonic: float
    ledger_requests: int
    ledger_pages: int
    ledger_bytes: int


@dataclass(slots=True)
class CrawlState:
    ctx: CrawlContext
    checkpoint: dict[str, Any]
    version: int
    ordinal_cursor: int
    skipped: set[str] = field(default_factory=set)
    observed: list[str] = field(default_factory=list)
    raw_item_ids: list[UUID] = field(default_factory=list)
    pages_fetched: int = 0
    pages_failed: int = 0
    robots_skipped: int = 0
    requests_used: int = 0
    bytes_used: int = 0
    robots_cache: dict[str, Any] = field(default_factory=dict)
    stopped: str = "frontier_empty"
    claim_lost: bool = False


def budget_gap(
    *,
    pages_used: int,
    requests_used: int,
    bytes_used: int,
    seconds_left: float | None,
    budget: EffectiveResourceBudget,
) -> str | None:
    """Which cap blocks the next request, or None when one more still fits.

    Checked before every request, so execution stops *at* the boundary without
    exceeding it: ``used == max`` already blocks the next one."""
    if seconds_left is not None and seconds_left <= 0:
        return "time_budget"
    if pages_used + 1 > budget.max_pages:
        return "page_budget"
    if requests_used + 1 > budget.max_requests:
        return "request_budget"
    if bytes_used >= budget.max_total_bytes:
        return "byte_budget"
    return None


def crawl_deadline(state: CrawlState) -> float:
    ctx = state.ctx
    return ctx.seed_started_monotonic + float(ctx.budget.max_duration_seconds)


def crawl_totals(state: CrawlState) -> tuple[int, int, int]:
    """(pages, requests, bytes) used across the run ledger and this crawl."""
    ctx = state.ctx
    return (
        ctx.ledger_pages + state.pages_fetched,
        ctx.ledger_requests + state.requests_used,
        ctx.ledger_bytes + state.bytes_used,
    )


def target_validator(ctx: CrawlContext) -> Callable[[str], None]:
    """Per-hop gate: network policy + site policy + discovery scope, fail-closed."""
    network = NetworkPolicy()

    def validator(url: str) -> None:
        network.validate(url)
        ctx.policy.validate_target(url)
        if not scope_allows(
            seed_url=ctx.seed_url,
            target_url=url,
            scope=ctx.scope,
            approved_domains=ctx.approved_domains,
        ):
            raise CollectionError("site_policy_denied", "Target is outside the discovery scope")

    return validator


def lease_owned_by(checkpoint: dict[str, Any] | None, run_id: Any) -> bool:
    lease = crawl_lease(checkpoint)
    return lease is not None and str(lease.get("run_id")) == str(run_id)


async def cas_crawl_step(
    repository: RunRepository,
    claim: RunClaim[Source],
    *,
    version: int,
    document: dict[str, Any],
    page: CrawlPageRecord | None = None,
    allow_takeover: bool = False,
) -> CrawlStepResult | None:
    """Commit one claim-guarded CAS step, absorbing benign version bumps.

    A failed CAS is retried only while the claimant still holds the run claim and
    the frontier lease still belongs to it (or, for acquisition, is free/expired):
    a version moved by an unrelated writer (another run finishing its own stage)
    must not abort an otherwise healthy crawl, while a taken-over frontier stops
    it immediately."""
    current = version
    for _ in range(3):
        committed = await repository.commit_crawl_step(
            claim, expected_version=current, checkpoint=document, page=page
        )
        if committed is not None:
            return committed
        if not await repository.claim_alive(claim):
            return None
        fresh, fresh_version = await repository.crawl_checkpoint(claim.source.id)
        if allow_takeover:
            lease = crawl_lease(fresh)
            held_elsewhere = (
                lease is not None
                and lease_is_active(lease, now=datetime.now(UTC))
                and str(lease.get("run_id")) != str(claim.run_id)
            )
            if held_elsewhere:
                return None
        elif not lease_owned_by(fresh, claim.run_id):
            return None
        current = fresh_version
    return None


async def fetch_and_commit(
    state: CrawlState, entry: dict[str, Any], *, robots_delay_ms: int
) -> None:
    """Fetch one frontier target through the transport and persist its outcome."""
    ctx = state.ctx
    target_url = str(entry["url"])
    entry_hash = frontier_entry_hash(entry)
    _, requests_used, bytes_used = crawl_totals(state)
    remaining_requests = max(1, ctx.budget.max_requests - requests_used)
    remaining_bytes = max(0, ctx.budget.max_total_bytes - bytes_used)
    delay_ms = max(ctx.policy.crawl_delay_ms, robots_delay_ms)
    spacing_ms = ctx.site_gate.spacing_ms(
        crawl_delay_ms=delay_ms, requests_per_minute=ctx.policy.requests_per_minute
    )
    started_at = datetime.now(UTC)
    try:
        async with ctx.site_gate.guard(
            _host(target_url),
            crawl_delay_ms=delay_ms,
            requests_per_minute=ctx.policy.requests_per_minute,
        ):
            fetched = await ctx.transport.fetch_page(
                target_url,
                validator=target_validator(ctx),
                max_requests=remaining_requests,
                max_bytes=remaining_bytes,
                deadline_monotonic=crawl_deadline(state),
                max_retries=min(ctx.budget.max_retries_per_target, max(0, remaining_requests - 1)),
                min_delay_seconds=spacing_ms / 1000,
            )
    except CollectionError as exc:
        requests_made = max(exc.retry_count + 1, exc.requests_made or 0)
        state.requests_used += requests_made
        state.skipped.add(entry_hash)
        record = CrawlPageRecord(
            requested_url=target_url,
            ordinal=state.ordinal_cursor,
            status="failed",
            started_at=started_at,
            finished_at=datetime.now(UTC),
            backend_name=ctx.backend_name.value,
            decision_version="discovery-crawl-v1",
            status_code=exc.status_code,
            retry_count=exc.retry_count,
            requests_used=requests_made,
            error_code=exc.code,
            safe_error=exc.safe_message,
        )
        await commit_failure(state, entry_hash=entry_hash, record=record)
        return
    state.requests_used += fetched.requests_used
    state.bytes_used += len(fetched.body)
    await _commit_success(state, entry, fetched=fetched, started_at=started_at)


async def commit_failure(state: CrawlState, *, entry_hash: str, record: CrawlPageRecord) -> None:
    """Persist one failed page attempt; the target keeps its frontier slot."""
    document, _abandoned = crawl_fail_page(
        state.checkpoint, entry_hash=entry_hash, max_attempts=MAX_TARGET_ATTEMPTS
    )
    committed = await cas_crawl_step(
        state.ctx.repository,
        state.ctx.claim,
        version=state.version,
        document=document,
        page=record,
    )
    if committed is None:
        state.claim_lost = True
        return
    state.checkpoint = document
    state.version = committed.version
    state.pages_failed += 1
    state.ordinal_cursor += 1


async def _commit_success(
    state: CrawlState, entry: dict[str, Any], *, fetched: CrawlFetched, started_at: datetime
) -> None:
    ctx = state.ctx
    entry_hash = frontier_entry_hash(entry)
    target_url = str(entry["url"])
    response = FetchResponse(
        final_url=fetched.final_url,
        content_type=fetched.content_type,
        body=fetched.body,
        status_code=fetched.status_code,
    )
    try:
        parsed, quality = _evaluate_page(state, response)
    except CollectionError as exc:
        state.skipped.add(entry_hash)
        record = _fetched_page_record(
            state,
            fetched,
            requested_url=target_url,
            started_at=started_at,
            status="failed",
            error=exc,
        )
        await commit_failure(state, entry_hash=entry_hash, record=record)
        return
    begin = crawl_begin_page(state.checkpoint, entry_hash=entry_hash)
    document = begin
    if quality_met(quality):
        document = _child_plan(state, entry, fetched=fetched, checkpoint=begin).checkpoint
    document = crawl_finish_success(document)
    candidate = parsed.candidates[0]
    record = _fetched_page_record(
        state,
        fetched,
        requested_url=target_url,
        started_at=started_at,
        quality=quality,
        evidence={
            "text": candidate.raw_text,
            "title": candidate.title,
            "canonical_url": candidate.canonical_url,
            "content_type": candidate.content_type,
            "external_id": candidate.external_id,
            "published_at": candidate.published_at,
            "metadata": candidate.metadata,
            "body": fetched.body,
        },
    )
    committed = await cas_crawl_step(
        ctx.repository, ctx.claim, version=state.version, document=document, page=record
    )
    if committed is None:
        state.claim_lost = True
        return
    state.checkpoint = document
    state.version = committed.version
    state.pages_fetched += 1
    state.ordinal_cursor += 1
    state.observed.append(artifact_key_for(candidate))
    if committed.raw_item_id is not None:
        state.raw_item_ids.append(committed.raw_item_id)


def _fetched_page_record(
    state: CrawlState,
    fetched: CrawlFetched,
    *,
    requested_url: str,
    started_at: datetime,
    status: str = "succeeded",
    quality: Decimal | None = None,
    error: CollectionError | None = None,
    evidence: dict[str, Any] | None = None,
) -> CrawlPageRecord:
    """Bounded per-page record shared by the success and parse-failure paths."""
    ctx = state.ctx
    return CrawlPageRecord(
        requested_url=requested_url,
        ordinal=state.ordinal_cursor,
        status=status,
        started_at=started_at,
        finished_at=datetime.now(UTC),
        backend_name=ctx.backend_name.value,
        decision_version="discovery-crawl-v1",
        status_code=fetched.status_code,
        response_url=fetched.final_url,
        content_type=fetched.content_type,
        retry_count=fetched.retry_count,
        bytes_received=len(fetched.body),
        requests_used=fetched.requests_used,
        error_code=None if error is None else error.code,
        safe_error=None if error is None else error.safe_message,
        quality_score=quality,
        evidence=evidence,
    )


def _evaluate_page(
    state: CrawlState, response: FetchResponse
) -> tuple[ParseResult, Decimal | None]:
    ctx = state.ctx
    parsed = parse_html(response, response.final_url)
    result = AcquisitionResult(response=response, retry_count=0, budget_used={"requests": 0})
    result = attach_extraction_observations(
        result,
        family=ctx.source_family,
        content_profile=ctx.content_profile,
        source_type=SourceType.URL,
        parsed=parsed,
    )
    quality = aggregate_quality(
        [observation.evidence.quality_score for observation in result.observations]
    )
    return parsed, quality


def _child_plan(
    state: CrawlState,
    entry: dict[str, Any],
    *,
    fetched: CrawlFetched,
    checkpoint: dict[str, Any],
) -> DiscoveryPlan:
    ctx = state.ctx
    return plan_discovery(
        seed_url=ctx.seed_url,
        body=fetched.body,
        content_type=fetched.content_type,
        final_url=fetched.final_url,
        scope=ctx.scope,
        approved_domains=ctx.approved_domains,
        allow_paths=ctx.policy.allow_paths,
        deny_paths=ctx.policy.deny_paths,
        checkpoint=checkpoint,
        max_depth=ctx.max_depth,
        max_frontier_size=ctx.max_frontier_size,
        max_discovered_urls=ctx.max_discovered_urls,
        min_score=ctx.min_score,
        base_depth=int(entry.get("depth", 1)),
    )


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").rstrip(".").lower()
