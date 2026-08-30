from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from urllib.parse import urlsplit

from app.schemas.resources import AcquisitionProfileV1, RobotsMode
from app.services.acquisition_types import CollectionError

_METADATA_HOSTS = frozenset(
    {
        "metadata.google.internal",
        "metadata.google",
        "instance-data",
        "instance-data.ec2.internal",
        "metadata.azure.internal",
    }
)


@dataclass(frozen=True, slots=True)
class NetworkPolicy:
    allowed_schemes: frozenset[str] = frozenset({"http", "https"})
    allowed_ports: frozenset[int] = frozenset({80, 443})

    def validate(self, url: str) -> None:
        try:
            parsed = urlsplit(url)
            port = parsed.port
        except ValueError:
            raise CollectionError(
                "network_policy_denied", "Target is denied by network policy"
            ) from None
        scheme = parsed.scheme.lower()
        if (
            scheme not in self.allowed_schemes
            or parsed.hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or "@" in parsed.netloc
        ):
            raise CollectionError("network_policy_denied", "Target is denied by network policy")
        hostname = parsed.hostname.rstrip(".").lower()
        effective_port = port if port is not None else (443 if scheme == "https" else 80)
        if effective_port not in self.allowed_ports:
            raise CollectionError("network_policy_denied", "Target is denied by network policy")
        if hostname in _METADATA_HOSTS or hostname.endswith(".internal"):
            raise CollectionError("network_policy_denied", "Target is denied by network policy")
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            return
        if not address.is_global:
            raise CollectionError("network_policy_denied", "Target is denied by network policy")


@dataclass(frozen=True, slots=True)
class OperatorSitePolicy:
    robots_mode: RobotsMode = RobotsMode.RESPECT
    crawl_delay_ms: int = 0
    requests_per_minute: int = 60
    max_parallel_requests: int = 8
    allowed_content_types: frozenset[str] = frozenset(
        {
            "text/html",
            "application/rss+xml",
            "application/atom+xml",
            "application/xml",
            "text/xml",
        }
    )
    allow_paths: tuple[str, ...] = ()
    deny_paths: tuple[str, ...] = ()
    approved_domains: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class EffectiveSitePolicy:
    robots_mode: RobotsMode
    crawl_delay_ms: int
    requests_per_minute: int
    max_parallel_requests: int
    allowed_content_types: frozenset[str]
    allow_paths: tuple[str, ...]
    deny_paths: tuple[str, ...]
    origin_host: str
    approved_domains: frozenset[str]

    def validate_target(self, url: str) -> None:
        parsed = urlsplit(url)
        hostname = (parsed.hostname or "").rstrip(".").lower()
        if hostname != self.origin_host and hostname not in self.approved_domains:
            raise CollectionError("site_policy_denied", "Target is denied by site policy")
        path = parsed.path or "/"
        if any(path.startswith(prefix) for prefix in self.deny_paths):
            raise CollectionError("site_policy_denied", "Target is denied by site policy")
        if self.allow_paths and not any(path.startswith(prefix) for prefix in self.allow_paths):
            raise CollectionError("site_policy_denied", "Target is denied by site policy")

    def validate_content_type(self, value: str) -> None:
        media_type = value.split(";", 1)[0].strip().lower()
        if media_type not in self.allowed_content_types:
            raise CollectionError("site_policy_denied", "Response is denied by site policy")


@dataclass(frozen=True, slots=True)
class OperatorResourceBudget:
    max_requests: int = 1000
    max_pages: int = 100
    max_depth: int = 3
    max_duration_seconds: int = 900
    max_concurrency: int = 8
    max_browser_pages: int = 10
    max_retries_per_target: int = 2
    max_total_bytes: int = 52_428_800


DEFAULT_OPERATOR_SITE_POLICY = OperatorSitePolicy()
DEFAULT_OPERATOR_RESOURCE_BUDGET = OperatorResourceBudget()


@dataclass(frozen=True, slots=True)
class EffectiveResourceBudget:
    max_requests: int
    max_pages: int
    max_depth: int
    max_duration_seconds: int
    max_concurrency: int
    max_browser_pages: int
    max_retries_per_target: int
    max_total_bytes: int

    def validate_usage(
        self, *, requests: int, pages: int, bytes_received: int, duration_seconds: float
    ) -> None:
        if (
            requests > self.max_requests
            or pages > self.max_pages
            or bytes_received > self.max_total_bytes
            or duration_seconds > self.max_duration_seconds
        ):
            raise CollectionError(
                "acquisition_budget_exhausted", "Acquisition resource budget is exhausted"
            )


def _intersect_path_prefixes(source: tuple[str, ...], operator: tuple[str, ...]) -> tuple[str, ...]:
    if not source:
        return operator
    if not operator:
        return source
    intersections: set[str] = set()
    for source_prefix in source:
        for operator_prefix in operator:
            if source_prefix.startswith(operator_prefix):
                intersections.add(source_prefix)
            elif operator_prefix.startswith(source_prefix):
                intersections.add(operator_prefix)
    return tuple(sorted(intersections))


def effective_site_policy(
    profile: AcquisitionProfileV1,
    target_url: str,
    operator: OperatorSitePolicy = DEFAULT_OPERATOR_SITE_POLICY,
) -> EffectiveSitePolicy:
    source = profile.site_policy
    source_types = frozenset(source.allowed_content_types)
    approved = frozenset(profile.approved_domains) & operator.approved_domains
    origin_host = (urlsplit(target_url).hostname or "").rstrip(".").lower()
    return EffectiveSitePolicy(
        robots_mode=(
            RobotsMode.DENY_IF_UNAVAILABLE
            if RobotsMode.DENY_IF_UNAVAILABLE in {source.robots_mode, operator.robots_mode}
            else RobotsMode.RESPECT
        ),
        crawl_delay_ms=max(source.crawl_delay_ms, operator.crawl_delay_ms),
        requests_per_minute=min(source.requests_per_minute, operator.requests_per_minute),
        max_parallel_requests=min(source.max_parallel_requests, operator.max_parallel_requests),
        allowed_content_types=source_types & operator.allowed_content_types,
        allow_paths=_intersect_path_prefixes(tuple(source.allow_paths), operator.allow_paths),
        deny_paths=tuple(sorted(set(source.deny_paths) | set(operator.deny_paths))),
        origin_host=origin_host,
        approved_domains=approved,
    )


def effective_resource_budget(
    profile: AcquisitionProfileV1,
    operator: OperatorResourceBudget = DEFAULT_OPERATOR_RESOURCE_BUDGET,
) -> EffectiveResourceBudget:
    source = profile.resource_budget
    return EffectiveResourceBudget(
        max_requests=min(source.max_requests, operator.max_requests),
        max_pages=min(source.max_pages, operator.max_pages),
        max_depth=min(source.max_depth, operator.max_depth),
        max_duration_seconds=min(source.max_duration_seconds, operator.max_duration_seconds),
        max_concurrency=min(source.max_concurrency, operator.max_concurrency),
        max_browser_pages=min(source.max_browser_pages, operator.max_browser_pages),
        max_retries_per_target=min(source.max_retries_per_target, operator.max_retries_per_target),
        max_total_bytes=min(source.max_total_bytes, operator.max_total_bytes),
    )
