"""ACQ-1E WP-5 I2 crawl execution: loop, robots integration, run evidence (docs/61).

Consumes the persistent frontier through claim-guarded CAS checkpoint steps
(``commit_crawl_step``): a stale worker stops at the next step boundary, a
re-claimed run resumes without re-fetching committed pages and without dropping
pending targets. Every fetch goes through the injected ``CrawlTransport`` port
(production: ``SafeCrawlTransport`` over ``SafeFetcher``); robots.txt is fetched
per origin through the same transport and enforced per ``robots_mode``; traversal
is bounded across pages by the run budget and stops *before* a request that could
not be afforded. Per-page steps live in ``discovery_pages``; robots in
``discovery_robots``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

from app.domains.acquisition_ports import CrawlTransport, RunClaim
from app.models.entities import BackendName, DiscoveryMode, Source, SourceType
from app.services.acquisition_policy import effective_resource_budget, effective_site_policy
from app.services.discovery_frontier import (
    FRONTIER_HARD_CAP,
    DiscoveryPlan,
    checkpoint_view,
    crawl_lease,
    frontier_entry_hash,
    lease_is_active,
    merge_entries,
    next_crawl_target,
    plan_discovery,
    set_crawl_lease,
)
from app.services.discovery_pages import (
    CrawlContext,
    CrawlState,
    RunRepository,
    budget_gap,
    cas_crawl_step,
    crawl_deadline,
    crawl_totals,
    fetch_and_commit,
)
from app.services.discovery_policy import MAX_FRONTIER_SIZE_DEFAULT, MIN_SCORE_DEFAULT
from app.services.discovery_robots import (
    RobotsVerdict,
    evaluate_robots,
    fetch_robots,
)
from app.services.site_gate import SiteGate

CRAWL_EXECUTOR_VERSION = "discovery-crawl-v1"
CRAWL_LEASE_SECONDS = 300


@dataclass(frozen=True, slots=True)
class CrawlOutcome:
    started: bool
    summary: dict[str, Any]
    observed_keys: tuple[str, ...]
    raw_item_ids: tuple[UUID, ...]
    pages_fetched: int
    pages_failed: int
    complete: bool
    requests_used: int
    bytes_used: int


def discovery_enabled(source_type: SourceType, mode: DiscoveryMode) -> bool:
    """Discovery planning applies to URL sources that opted into a scope beyond single page."""
    return source_type == SourceType.URL and mode != DiscoveryMode.SINGLE_PAGE


def plan_seed_page(
    *,
    source: Source,
    profile: Any,
    response: Any,
    checkpoint: dict[str, Any] | None,
) -> DiscoveryPlan:
    """Seed-page discovery planning shared by the I1 path and the crawl executor."""
    policy = effective_site_policy(profile, source.normalized_url)
    profile_budget = profile.resource_budget
    return plan_discovery(
        seed_url=source.normalized_url,
        body=response.body,
        content_type=response.content_type,
        final_url=response.final_url,
        scope=source.discovery_mode,
        approved_domains=frozenset(policy.approved_domains),
        allow_paths=policy.allow_paths,
        deny_paths=policy.deny_paths,
        checkpoint=checkpoint,
        max_depth=int(profile_budget.max_depth),
        max_frontier_size=MAX_FRONTIER_SIZE_DEFAULT,
        max_discovered_urls=max(0, int(profile_budget.max_pages)) * 5,
        min_score=MIN_SCORE_DEFAULT,
    )


def crawl_context_for(
    *,
    repository: RunRepository,
    claim: RunClaim[Source],
    source: Source,
    profile: Any,
    plan: DiscoveryPlan,
    transport: CrawlTransport,
    site_gate: SiteGate,
    backend_name: BackendName,
    base_ordinal: int,
    seed_started_monotonic: float,
    ledger: dict[str, int],
) -> CrawlContext:
    """Assemble the crawl context from the routed run state."""
    policy = effective_site_policy(profile, source.normalized_url)
    profile_budget = profile.resource_budget
    return CrawlContext(
        repository=repository,
        claim=claim,
        seed_url=source.normalized_url,
        scope=source.discovery_mode,
        approved_domains=frozenset(policy.approved_domains),
        policy=policy,
        budget=effective_resource_budget(profile),
        plan=plan,
        transport=transport,
        site_gate=site_gate,
        backend_name=backend_name,
        base_ordinal=base_ordinal,
        max_depth=int(profile_budget.max_depth),
        max_frontier_size=MAX_FRONTIER_SIZE_DEFAULT,
        max_discovered_urls=max(0, int(profile_budget.max_pages)) * 5,
        min_score=MIN_SCORE_DEFAULT,
        source_family=source.source_family,
        content_profile=profile.content_profile.value,
        seed_started_monotonic=seed_started_monotonic,
        ledger_requests=int(ledger.get("requests", 0)),
        ledger_pages=int(ledger.get("pages", 0)),
        ledger_bytes=int(ledger.get("bytes_received", 0)),
    )


def _skipped(summary_reason: str) -> CrawlOutcome:
    return CrawlOutcome(
        started=False,
        summary={
            "executor_version": CRAWL_EXECUTOR_VERSION,
            "started": False,
            "skipped_reason": summary_reason,
            "stopped_reason": summary_reason,
            "complete": False,
            "pages_fetched": 0,
            "pages_failed": 0,
            "requests_used": 0,
            "bytes_received": 0,
        },
        observed_keys=(),
        raw_item_ids=(),
        pages_fetched=0,
        pages_failed=0,
        complete=False,
        requests_used=0,
        bytes_used=0,
    )


async def execute_discovery_crawl(ctx: CrawlContext) -> CrawlOutcome:
    """Run the bounded crawl loop and return the outcome evidence for the run."""
    base, version = await ctx.repository.crawl_checkpoint(ctx.claim.source.id)
    now = datetime.now(UTC)
    lease = crawl_lease(base)
    held_elsewhere = (
        lease is not None
        and lease_is_active(lease, now=now)
        and str(lease.get("run_id")) != str(ctx.claim.run_id)
    )
    if held_elsewhere:
        return _skipped("checkpoint_conflict")
    document = set_crawl_lease(
        merge_entries(base, ctx.plan.entries, frontier_cap=_frontier_cap(ctx)),
        lease=_lease_payload(ctx.claim.run_id, now),
    )
    committed = await cas_crawl_step(
        ctx.repository, ctx.claim, version=version, document=document, allow_takeover=True
    )
    if committed is None:
        return _skipped("checkpoint_conflict")
    state = CrawlState(
        ctx=ctx,
        checkpoint=document,
        version=committed.version,
        ordinal_cursor=ctx.base_ordinal + 1,
    )
    await _crawl_loop(state)
    if not state.claim_lost:
        released = set_crawl_lease(state.checkpoint, lease=None)
        cleared = await cas_crawl_step(
            ctx.repository, ctx.claim, version=state.version, document=released
        )
        if cleared is None:
            state.claim_lost = True
        else:
            state.checkpoint = released
            state.version = cleared.version
    return _outcome(state)


def _gap_now(state: CrawlState) -> str | None:
    """Budget gap for the next request as of this instant (see ``budget_gap``)."""
    pages_used, requests_used, bytes_used = crawl_totals(state)
    return budget_gap(
        pages_used=pages_used,
        requests_used=requests_used,
        bytes_used=bytes_used,
        seconds_left=crawl_deadline(state) - time.monotonic(),
        budget=state.ctx.budget,
    )


async def _crawl_loop(state: CrawlState) -> None:
    ctx = state.ctx
    while True:
        entry = next_crawl_target(state.checkpoint, skip_hashes=frozenset(state.skipped))
        if entry is None:
            state.stopped = "frontier_empty" if not state.skipped else "targets_deferred"
            return
        if not await ctx.repository.claim_alive(ctx.claim):
            state.claim_lost = True
            state.stopped = "claim_lost"
            return
        gap = _gap_now(state)
        if gap is not None:
            state.stopped = gap
            return
        verdict = await _robots_verdict(state, entry)
        if verdict.kind == "stop":
            state.stopped = verdict.detail
            return
        if verdict.kind == "skip":
            state.skipped.add(frontier_entry_hash(entry))
            state.robots_skipped += 1
            continue
        # The robots fetch may have consumed the marginal request: re-check before
        # the page request itself so the crawl still stops *before* exceeding.
        gap = _gap_now(state)
        if gap is not None:
            state.stopped = gap
            return
        await fetch_and_commit(state, entry, robots_delay_ms=verdict.delay_ms)
        if state.claim_lost:
            state.stopped = "claim_lost"
            return


def _origin(url: str) -> str:
    parsed = urlsplit(url)
    scheme = (parsed.scheme or "https").lower()
    host = (parsed.hostname or "").rstrip(".").lower()
    if parsed.port is not None:
        return f"{scheme}://{host}:{parsed.port}"
    return f"{scheme}://{host}"


async def _robots_verdict(state: CrawlState, entry: dict[str, Any]) -> RobotsVerdict:
    """Allow / skip-target / stop decision for one target, one robots fetch per origin."""
    ctx = state.ctx
    target_url = str(entry["url"])
    origin = _origin(target_url)
    rule = state.robots_cache.get(origin)
    if rule is None:
        if crawl_deadline(state) - time.monotonic() <= 0:
            return RobotsVerdict("stop", detail="time_budget")
        _, requests_used, bytes_used = crawl_totals(state)
        if requests_used + 1 > ctx.budget.max_requests:
            return RobotsVerdict("stop", detail="request_budget")
        if bytes_used >= ctx.budget.max_total_bytes:
            return RobotsVerdict("stop", detail="byte_budget")
        rule, used, received = await fetch_robots(
            ctx.transport,
            site_gate=ctx.site_gate,
            policy=ctx.policy,
            robots_url=f"{origin}/robots.txt",
            deadline_monotonic=crawl_deadline(state),
            max_bytes=max(0, ctx.budget.max_total_bytes - bytes_used),
        )
        state.requests_used += used
        state.bytes_used += received
        state.robots_cache[origin] = rule
    return evaluate_robots(rule, policy=ctx.policy, target_url=target_url)


def _frontier_cap(ctx: CrawlContext) -> int:
    return max(0, min(ctx.max_frontier_size, FRONTIER_HARD_CAP))


def _lease_payload(run_id: Any, now: datetime) -> dict[str, Any]:
    return {
        "run_id": str(run_id),
        "claimed_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=CRAWL_LEASE_SECONDS)).isoformat(),
    }


def _outcome(state: CrawlState) -> CrawlOutcome:
    _, frontier, _ = checkpoint_view(state.checkpoint)
    complete = state.stopped == "frontier_empty" and not state.claim_lost
    summary: dict[str, Any] = {
        "executor_version": CRAWL_EXECUTOR_VERSION,
        "started": True,
        "complete": complete,
        "stopped_reason": state.stopped,
        "claim_lost": state.claim_lost,
        "pages_fetched": state.pages_fetched,
        "pages_failed": state.pages_failed,
        "raw_items_created": len(state.raw_item_ids),
        "robots_skipped": state.robots_skipped,
        "requests_used": state.requests_used,
        "bytes_received": state.bytes_used,
        "frontier_remaining": len(frontier),
        "robots": {origin: rule.status for origin, rule in sorted(state.robots_cache.items())},
    }
    return CrawlOutcome(
        started=True,
        summary=summary,
        observed_keys=tuple(state.observed),
        raw_item_ids=tuple(state.raw_item_ids),
        pages_fetched=state.pages_fetched,
        pages_failed=state.pages_failed,
        complete=complete,
        requests_used=state.requests_used,
        bytes_used=state.bytes_used,
    )
