"""ACQ-1C Router v1: static/native backend selection, ordered fallback, circuit gate,
adaptive throttle, cumulative budget ledger, and a closed decision trace.

Frozen by ADR-034 / docs/57-ACQ1-WP4-ROUTER-CONTRACT-ADDENDUM.md. While
``BROWSER_DYNAMIC_ENABLED`` is False the browser tail of the candidate table stays
disabled: browser backends are never selectable and ``allow_browser`` requests fail
closed with ``acquisition_browser_not_admitted``. This module performs no network,
filesystem, or database I/O.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from app.domains.acquisition_ports import SourceRuntimeFacts
from app.models.entities import AcquisitionMode, BackendName, SourceType
from app.services.acquisition_policy import EffectiveResourceBudget
from app.services.acquisition_types import CollectionError
from app.services.extraction_quality import quality_bucket

ROUTER_VERSION = "router-v1"

# Browser capability stays disabled until WP-3 is admitted; this is an admission
# requirement, not a user preference. It grants no switch and no hidden fallback.
BROWSER_DYNAMIC_ENABLED = False
BROWSER_BACKENDS = frozenset({BackendName.DYNAMIC_BROWSER, BackendName.ADVANCED_BROWSER})

# Safety-terminal codes never trigger a fallback stage or an internal retry; the
# frozen no-bypass/no-widening invariants make policy, budget, and browser refusals final.
SAFETY_TERMINAL_CODES = frozenset(
    {
        "acquisition_browser_not_admitted",
        "acquisition_no_backend",
        "acquisition_circuit_open",
        "acquisition_mode_unsupported",
        "source_profile_invalid",
        "network_policy_denied",
        "site_policy_denied",
        "ssrf_blocked",
        "unsupported_port",
        "acquisition_budget_exhausted",
    }
)

# Policy refusals are visible in counters but do not pressurize the remote endpoint,
# so they never advance the consecutive-failure counter or open the circuit.
STATE_NEUTRAL_CODES = frozenset(
    {
        "network_policy_denied",
        "site_policy_denied",
        "ssrf_blocked",
        "unsupported_port",
        "acquisition_budget_exhausted",
    }
)

CIRCUIT_FAILURE_THRESHOLD = 5
CIRCUIT_BASE_SECONDS = 900
CIRCUIT_MAX_SECONDS = 7200
CIRCUIT_BACKOFF_STEPS = 3

THROTTLE_BASE_MS = 250
THROTTLE_MAX_MS = 30_000
THROTTLE_SIGNAL_CODES = frozenset({"http_error", "request_timeout", "dns_resolution_failed"})

TRACE_KEYS = frozenset(
    {
        "decision_version",
        "ordinal",
        "backend",
        "outcome",
        "error_code",
        "retry_count",
        "requests",
        "pages",
        "bytes_received",
        "quality_score",
        "fallback_reason",
    }
)


@dataclass(frozen=True, slots=True)
class RouteCandidate:
    stage: int
    backend: BackendName
    reason: str


def select_candidates(
    *,
    source_type: SourceType,
    mode: AcquisitionMode,
    allow_browser: bool,
    allow_static_retry: bool = False,
) -> tuple[RouteCandidate, ...]:
    """Ordered static candidate chain; browser stages remain disabled by admission.

    ``allow_static_retry`` (closure Phase 1, ADR-038): when the effective budget can
    fund a second page/request the URL chain gains the controlled static-retry stage,
    which re-fetches through the same SafeFetcher pipeline. The default profile
    (``max_pages=1``) keeps the single-stage chain, so the budget refusal semantics of
    docs/57 §15.4 are unchanged.
    """
    if mode.value not in {AcquisitionMode.AUTO.value, AcquisitionMode.NATIVE.value}:
        raise CollectionError(
            "acquisition_mode_unsupported", "Acquisition mode is not available in this worker"
        )
    if allow_browser:
        raise CollectionError(
            "acquisition_browser_not_admitted",
            "Browser acquisition is not admitted",
        )
    if source_type == SourceType.API:
        raise CollectionError(
            "acquisition_no_backend", "No acquisition backend is available for this source"
        )
    if source_type == SourceType.RSS:
        return (RouteCandidate(1, BackendName.RSS, "rss_feed"),)
    # URL: native static stage first. The browser tail stays disabled: no candidate is
    # ever derived from it while BROWSER_DYNAMIC_ENABLED is False.
    candidates = [RouteCandidate(1, BackendName.NATIVE_HTTP, "native_static")]
    if allow_static_retry:
        candidates.append(RouteCandidate(2, BackendName.SCRAPLING_HTTP, "static_retry"))
    return tuple(candidates)


def quality_met(score: Decimal | None) -> bool:
    """Acceptable bucket passes; low/marginal escalate. Absent signal is not a failure."""
    if score is None:
        return True
    return quality_bucket(score) == "acceptable"


def counts_toward_circuit(error_code: str) -> bool:
    return error_code not in STATE_NEUTRAL_CODES


def circuit_open_seconds(consecutive_failures: int) -> int:
    steps = min(max(consecutive_failures - CIRCUIT_FAILURE_THRESHOLD, 0), CIRCUIT_BACKOFF_STEPS)
    window = CIRCUIT_BASE_SECONDS * (1 << steps)
    return min(window, CIRCUIT_MAX_SECONDS)


def circuit_open_until(now: datetime, consecutive_failures: int) -> datetime:
    return now + timedelta(seconds=circuit_open_seconds(consecutive_failures))


def circuit_blocks(facts: SourceRuntimeFacts | None, now: datetime) -> str | None:
    """Return the terminal code when the circuit is open, else None."""
    if facts is None or facts.circuit_open_until is None:
        return None
    if facts.circuit_open_until > now:
        return "acquisition_circuit_open"
    return None


def throttle_delay_ms(facts: SourceRuntimeFacts | None, *, crawl_delay_ms: int) -> int:
    """Adaptive delay; zero without a throttle signal, bounded by THROTTLE_MAX_MS."""
    if facts is None or facts.consecutive_failures < 1:
        return 0
    if facts.last_error_code not in THROTTLE_SIGNAL_CODES:
        return 0
    steps = min(facts.consecutive_failures, 7)
    adaptive = THROTTLE_BASE_MS * (1 << steps)
    return min(max(crawl_delay_ms, adaptive), THROTTLE_MAX_MS)


def attempt_usage(result_usage: Mapping[str, int] | None) -> dict[str, int]:
    usage = {"requests": 0, "pages": 0, "bytes_received": 0}
    if not result_usage:
        return usage
    for key in usage:
        value = result_usage.get(key)
        if type(value) is int and value >= 0:
            usage[key] = value
    return usage


def attempt_trace(
    *,
    ordinal: int,
    backend: BackendName,
    outcome: str,
    error_code: str | None,
    retry_count: int,
    usage: Mapping[str, int],
    quality_score: Decimal | None,
    fallback_reason: str | None,
) -> dict[str, object]:
    """Closed, leak-free trace; unknown fields cannot appear by construction."""
    return {
        "decision_version": ROUTER_VERSION,
        "ordinal": ordinal,
        "backend": backend.value,
        "outcome": outcome,
        "error_code": error_code,
        "retry_count": max(0, retry_count),
        "requests": int(usage.get("requests", 0)),
        "pages": int(usage.get("pages", 0)),
        "bytes_received": int(usage.get("bytes_received", 0)),
        "quality_score": None if quality_score is None else str(quality_score),
        "fallback_reason": fallback_reason,
    }


class RouteBudgetLedger:
    """Cumulative per-run usage across attempts, fallbacks, and redirect hops."""

    def __init__(self) -> None:
        self.totals: dict[str, int] = {"requests": 0, "pages": 0, "bytes_received": 0}

    def charge(self, usage: Mapping[str, int]) -> None:
        for key in self.totals:
            value = usage.get(key)
            if type(value) is int and value > 0:
                self.totals[key] += value

    def charge_requests(self, requests: int) -> None:
        self.totals["requests"] += max(0, requests)

    def enforce(self, budget: EffectiveResourceBudget) -> None:
        """Check whether one more request still fits the cumulative budget."""
        if (
            self.totals["requests"] + 1 > budget.max_requests
            or self.totals["pages"] + 1 > budget.max_pages
            or self.totals["bytes_received"] > budget.max_total_bytes
        ):
            raise CollectionError(
                "acquisition_budget_exhausted", "Acquisition resource budget is exhausted"
            )

    def exceeds(self, budget: EffectiveResourceBudget) -> bool:
        try:
            self.enforce(budget)
        except CollectionError:
            return True
        return False


def route_summary(
    traces: list[dict[str, object]],
    *,
    accepted_backend: BackendName | None,
    discovery: dict[str, object] | None = None,
    throttle: dict[str, object] | None = None,
) -> dict[str, object]:
    """Closed run-level summary stored on CollectionRun.budget_summary."""
    summary: dict[str, object] = {
        "decision_version": ROUTER_VERSION,
        "stages": len(traces),
        "fallbacks": max(0, len(traces) - 1),
        "accepted_backend": None if accepted_backend is None else accepted_backend.value,
        "trace": traces,
    }
    if discovery is not None:
        summary["discovery"] = discovery
    if throttle is not None:
        summary["site_throttle"] = throttle
    return summary
