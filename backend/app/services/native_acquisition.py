from __future__ import annotations

import time
from collections.abc import Callable

from app.domains.acquisition_ports import CrawlFetched
from app.models.entities import SourceType
from app.services.acquisition_policy import (
    NetworkPolicy,
    effective_resource_budget,
    effective_site_policy,
)
from app.services.acquisition_types import (
    AcquisitionFetcher,
    AcquisitionRequest,
    AcquisitionResult,
    CollectionError,
)
from app.services.safe_fetcher import FetchSession, SafeFetcher, fetch_with_retries


class NativeAcquisitionBackend:
    def __init__(self, fetcher: AcquisitionFetcher | None = None) -> None:
        self._fetcher = fetcher

    async def acquire(self, request: AcquisitionRequest) -> AcquisitionResult:
        if request.mode.value not in {"auto", "native"}:
            raise CollectionError(
                "acquisition_mode_unsupported",
                "Acquisition mode is not available in this worker",
            )
        network_policy = NetworkPolicy()
        site_policy = effective_site_policy(request.profile, request.target_url)
        budget = effective_resource_budget(request.profile)
        started = time.monotonic()
        # Remaining effective budget from the run ledger; without one, the profile's
        # full effective budget applies to this attempt.
        remaining = request.remaining_budget
        session = FetchSession(
            max_requests=max(
                1, budget.max_requests if remaining is None else remaining.max_requests
            ),
            max_bytes=min(
                budget.max_total_bytes if remaining is None else remaining.max_bytes,
                budget.max_total_bytes,
            ),
            deadline_monotonic=None if remaining is None else remaining.deadline_monotonic,
        )

        def validate_target(target_url: str) -> None:
            network_policy.validate(target_url)
            site_policy.validate_target(target_url)

        validate_target(request.target_url)
        fetcher: AcquisitionFetcher
        if isinstance(self._fetcher, SafeFetcher):
            fetcher = self._fetcher.with_target_validator(validate_target)
        else:
            fetcher = self._fetcher or SafeFetcher(target_validator=validate_target)
        # Retries count as real requests, so they wait at least the site's spacing floor
        # (crawl delay / RPM spacing) in addition to the exponential backoff.
        spacing_floor = max(
            site_policy.crawl_delay_ms,
            60_000 // max(1, site_policy.requests_per_minute),
        )
        try:
            response, retries = await fetch_with_retries(
                fetcher,
                request.target_url,
                request.source_type,
                max_retries=min(
                    budget.max_retries_per_target,
                    max(0, session.max_requests - 1) if session.max_requests else 0,
                ),
                session=session,
                min_delay=spacing_floor / 1000,
            )
        except CollectionError as exc:
            # Real requests issued (initial + redirect hops + retries) travel with the
            # failure so the run ledger bills the true request count.
            if exc.requests_made is None and session.requests_made:
                exc.requests_made = session.requests_made
            raise
        site_policy.validate_content_type(response.content_type)
        duration = time.monotonic() - started
        requests_used = max(session.requests_made, retries + 1)
        budget.validate_usage(
            requests=requests_used,
            pages=1,
            bytes_received=len(response.body),
            duration_seconds=duration,
        )
        return AcquisitionResult(
            response=response,
            retry_count=retries,
            budget_used={
                "requests": requests_used,
                "pages": 1,
                "bytes_received": len(response.body),
            },
        )


class SafeCrawlTransport:
    """WP-5 I2 crawl transport: every crawl request goes through SafeFetcher.

    The validator is invoked before every request (initial, redirect hops), hop and
    retry accounting is billed to the caller, and budgets are enforced during the
    fetch by the shared ``FetchSession``; no crawl request bypasses the pipeline.
    """

    def __init__(self, fetcher: SafeFetcher | None = None) -> None:
        self._fetcher = fetcher or SafeFetcher()

    async def fetch_page(
        self,
        url: str,
        *,
        validator: Callable[[str], None],
        max_requests: int,
        max_bytes: int,
        deadline_monotonic: float | None,
        max_retries: int,
        min_delay_seconds: float,
        content_types: frozenset[str] | None = None,
    ) -> CrawlFetched:
        session = FetchSession(
            max_requests=max(1, max_requests),
            max_bytes=max(0, max_bytes),
            deadline_monotonic=deadline_monotonic,
        )
        fetcher = self._fetcher.with_target_validator(validator)
        try:
            response, retries = await fetch_with_retries(
                fetcher,
                url,
                SourceType.URL,
                max_retries=max(0, max_retries),
                session=session,
                min_delay=min_delay_seconds,
                content_types=content_types,
            )
        except CollectionError as exc:
            if exc.requests_made is None and session.requests_made:
                exc.requests_made = session.requests_made
            raise
        return CrawlFetched(
            final_url=response.final_url,
            content_type=response.content_type,
            body=response.body,
            status_code=response.status_code,
            retry_count=retries,
            requests_used=max(session.requests_made, retries + 1),
        )
