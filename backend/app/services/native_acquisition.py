from __future__ import annotations

import time

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
from app.services.safe_fetcher import SafeFetcher, fetch_with_retries


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

        def validate_target(target_url: str) -> None:
            network_policy.validate(target_url)
            site_policy.validate_target(target_url)

        validate_target(request.target_url)
        fetcher: AcquisitionFetcher
        if isinstance(self._fetcher, SafeFetcher):
            fetcher = self._fetcher.with_target_validator(validate_target)
        else:
            fetcher = self._fetcher or SafeFetcher(target_validator=validate_target)
        response, retries = await fetch_with_retries(
            fetcher,
            request.target_url,
            request.source_type,
            max_retries=min(budget.max_retries_per_target, budget.max_requests - 1),
        )
        site_policy.validate_content_type(response.content_type)
        duration = time.monotonic() - started
        budget.validate_usage(
            requests=retries + 1,
            pages=1,
            bytes_received=len(response.body),
            duration_seconds=duration,
        )
        return AcquisitionResult(
            response=response,
            retry_count=retries,
            budget_used={
                "requests": retries + 1,
                "pages": 1,
                "bytes_received": len(response.body),
            },
        )
