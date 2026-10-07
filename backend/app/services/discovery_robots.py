"""robots.txt fetching, parsing and enforcement for the WP-5 I2 crawl (docs/61 §5).

The fetch goes through the injected ``CrawlTransport`` (production: SafeFetcher),
so SSRF/redirect validation and request billing stay in the one safe pipeline.
Policy semantics: ``respect`` obeys the rules when a robots.txt is present and
treats missing/unavailable robots as "no rules known"; ``deny_if_unavailable``
refuses the whole crawl whenever no usable robots.txt could be established.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from app.domains.acquisition_ports import CrawlTransport
from app.services.acquisition_policy import (
    EffectiveSitePolicy,
    NetworkPolicy,
    robots_deny_when_unavailable,
)
from app.services.acquisition_types import CollectionError
from app.services.site_gate import SiteGate

ROBOTS_MAX_BYTES = 512 * 1024
ROBOTS_USER_AGENT_PRODUCT = "FlowTracer-Alpha"
ROBOTS_CONTENT_TYPES = frozenset({"text/plain"})
ROBOTS_MISSING_STATUSES = frozenset({404, 410})


@dataclass(frozen=True, slots=True)
class RobotsRule:
    status: str  # "fetched" | "missing" | "unavailable"
    parser: RobotFileParser | None = None
    delay_ms: int = 0


@dataclass(frozen=True, slots=True)
class RobotsVerdict:
    kind: str  # "allow" | "skip" | "stop"
    delay_ms: int = 0
    detail: str = ""


def robots_validator(
    *, origin_host: str, approved_domains: frozenset[str]
) -> Callable[[str], None]:
    """Robots targets must stay on the origin (or an approved domain); no path gates."""
    network = NetworkPolicy()

    def validator(url: str) -> None:
        network.validate(url)
        host = (urlsplit(url).hostname or "").rstrip(".").lower()
        if host != origin_host and host not in approved_domains:
            raise CollectionError("site_policy_denied", "Robots target is denied by site policy")

    return validator


async def fetch_robots(
    transport: CrawlTransport,
    *,
    site_gate: SiteGate,
    policy: EffectiveSitePolicy,
    robots_url: str,
    deadline_monotonic: float,
    max_bytes: int,
) -> tuple[RobotsRule, int, int]:
    """Fetch and parse one origin's robots.txt; returns (rule, requests, bytes)."""
    validator = robots_validator(
        origin_host=(urlsplit(robots_url).hostname or "").rstrip(".").lower(),
        approved_domains=policy.approved_domains,
    )
    host = (urlsplit(robots_url).hostname or "").rstrip(".").lower()
    try:
        async with site_gate.guard(
            host,
            crawl_delay_ms=policy.crawl_delay_ms,
            requests_per_minute=policy.requests_per_minute,
        ):
            fetched = await transport.fetch_page(
                robots_url,
                validator=validator,
                max_requests=2,
                max_bytes=min(ROBOTS_MAX_BYTES, max_bytes),
                deadline_monotonic=deadline_monotonic,
                max_retries=0,
                min_delay_seconds=0.0,
                content_types=ROBOTS_CONTENT_TYPES,
            )
    except CollectionError as exc:
        requests = max(exc.retry_count + 1, exc.requests_made or 0)
        if exc.status_code in ROBOTS_MISSING_STATUSES:
            return RobotsRule("missing"), requests, 0
        return RobotsRule("unavailable"), requests, 0
    if len(fetched.body) > ROBOTS_MAX_BYTES:
        return RobotsRule("unavailable"), fetched.requests_used, len(fetched.body)
    parser = RobotFileParser()
    parser.parse(fetched.body.decode("utf-8", errors="replace").splitlines())
    delay = parser.crawl_delay(ROBOTS_USER_AGENT_PRODUCT)
    delay_ms = max(0, int(delay * 1000)) if delay else 0
    return RobotsRule("fetched", parser, delay_ms), fetched.requests_used, len(fetched.body)


def evaluate_robots(
    rule: RobotsRule, *, policy: EffectiveSitePolicy, target_url: str
) -> RobotsVerdict:
    """Allow / skip-target / stop-crawl decision for one target under this policy."""
    if rule.status != "fetched":
        if robots_deny_when_unavailable(policy):
            return RobotsVerdict("stop", detail="robots_unavailable")
        return RobotsVerdict("allow")
    parser = rule.parser
    if parser is not None and not parser.can_fetch(ROBOTS_USER_AGENT_PRODUCT, target_url):
        return RobotsVerdict("skip", delay_ms=rule.delay_ms, detail="robots_disallowed")
    return RobotsVerdict("allow", delay_ms=rule.delay_ms)
