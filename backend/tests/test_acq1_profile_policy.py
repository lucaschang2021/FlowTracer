from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.models.entities import AcquisitionMode, DiscoveryMode, SourceFamily, SourceType
from app.schemas.resources import (
    AcquisitionProfileV1,
    SourceCreate,
    SourceResponse,
)
from app.services.acquisition_policy import (
    NetworkPolicy,
    OperatorResourceBudget,
    OperatorSitePolicy,
    effective_resource_budget,
    effective_site_policy,
)
from app.services.acquisition_types import AcquisitionRequest, CollectionError, FetchResponse
from app.services.native_acquisition import NativeAcquisitionBackend
from app.services.safe_fetcher import SafeFetcher, WireResponse


def test_legacy_source_materializes_complete_profile_defaults() -> None:
    source = SourceCreate.model_validate(
        {
            "name": "Legacy",
            "source_type": "rss",
            "url": "https://example.com/feed",
        }
    )
    assert source.source_family == SourceFamily.GENERIC_WEB
    assert source.acquisition_mode == AcquisitionMode.AUTO
    assert source.discovery_mode == DiscoveryMode.SINGLE_PAGE
    assert source.profile_version == "acq-source-v1"
    profile = source.acquisition_profile.storage_dict()
    assert set(profile) == {
        "content_profile",
        "priority",
        "allow_browser",
        "change_detection",
        "resource_budget",
        "site_policy",
        "approved_domains",
        "family_options",
    }
    assert profile["change_detection"]["materiality_threshold"] == 0.15
    assert profile["resource_budget"]["max_total_bytes"] == 5_242_880
    assert profile["family_options"] == {}


@pytest.mark.parametrize(
    "profile",
    [
        {"unknown": True},
        {"family_options": {"selector": "main"}},
        {"resource_budget": {"max_requests": True}},
        {"resource_budget": {"max_total_bytes": 1023}},
        {"change_detection": {"materiality_threshold": float("nan")}},
        {"site_policy": {"allowed_content_types": ["text/*"]}},
        {"site_policy": {"allow_paths": ["https://example.com/private"]}},
        {"site_policy": {"allow_paths": ["/safe\\..\\private"]}},
        {"site_policy": {"deny_paths": ["/safe?secret=yes"]}},
        {"approved_domains": ["*.example.com"]},
        {"approved_domains": ["127.0.0.1"]},
        {"authorization": "Bearer secret"},
    ],
)
def test_profile_v1_is_closed_finite_and_strict(profile: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        AcquisitionProfileV1.model_validate(profile)


def test_profile_normalizes_mime_paths_domains_and_decimal() -> None:
    profile = AcquisitionProfileV1.model_validate(
        {
            "change_detection": {"materiality_threshold": 0.2},
            "site_policy": {
                "allowed_content_types": [" Text/HTML ", "text/html", "application/xml"],
                "allow_paths": ["/docs", "/docs"],
                "deny_paths": ["/docs/private"],
            },
            "approved_domains": ["XN--BCHER-KVA.EXAMPLE."],
        }
    )
    assert profile.change_detection.materiality_threshold == Decimal("0.2000")
    assert profile.site_policy.allowed_content_types == ["text/html", "application/xml"]
    assert profile.site_policy.allow_paths == ["/docs"]
    assert profile.approved_domains == ["xn--bcher-kva.example"]


def test_legacy_config_rejects_secrets_and_response_redacts_existing_secrets() -> None:
    for config in (
        {"nested": {"api_token": "do-not-store"}},
        {"browser_args": ["--unsafe"]},
        {"safe\nkey": "value"},
    ):
        with pytest.raises(ValidationError):
            SourceCreate.model_validate(
                {
                    "name": "Secret",
                    "source_type": SourceType.RSS,
                    "url": "https://example.com/feed",
                    "config": config,
                }
            )
    response = SourceResponse.model_validate(
        {
            "id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "name": "Legacy",
            "source_type": "rss",
            "url": "https://example.com/feed",
            "normalized_url": "https://example.com/feed",
            "poll_interval_minutes": 60,
            "status": "active",
            "last_fetched_at": None,
            "next_fetch_at": None,
            "config": {"label": "public", "password": "hidden", "nested": {"token": "hidden"}},
            "source_family": "generic_web",
            "acquisition_mode": "auto",
            "discovery_mode": "single_page",
            "profile_version": "acq-source-v1",
            "acquisition_profile": {},
            "created_at": "2026-08-30T00:00:00Z",
            "updated_at": "2026-08-30T00:00:00Z",
        }
    )
    assert response.config == {"label": "public", "nested": {}}
    assert response.acquisition_profile.content_profile == "generic"


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/file",
        "http://user@example.com/",
        "http://127.0.0.1/",
        "http://169.254.169.254/latest/meta-data",
        "https://metadata.google.internal/",
        "https://example.com:8443/",
    ],
)
def test_network_policy_denies_non_overridable_targets(url: str) -> None:
    with pytest.raises(CollectionError) as caught:
        NetworkPolicy().validate(url)
    assert caught.value.code == "network_policy_denied"


def test_site_and_resource_policy_can_only_tighten_operator_limits() -> None:
    profile = AcquisitionProfileV1.model_validate(
        {
            "resource_budget": {
                "max_requests": 10,
                "max_pages": 4,
                "max_duration_seconds": 120,
            },
            "site_policy": {
                "robots_mode": "respect",
                "crawl_delay_ms": 1000,
                "requests_per_minute": 30,
                "max_parallel_requests": 2,
                "allowed_content_types": ["text/html", "application/xml"],
                "allow_paths": ["/docs"],
                "deny_paths": ["/docs/private"],
            },
            "approved_domains": ["assets.example.com"],
        }
    )
    site = effective_site_policy(
        profile,
        "https://example.com/docs/start",
        OperatorSitePolicy(
            robots_mode="deny_if_unavailable",
            crawl_delay_ms=2000,
            requests_per_minute=20,
            max_parallel_requests=1,
            allowed_content_types=frozenset({"text/html"}),
            allow_paths=("/docs/public",),
            deny_paths=("/blocked",),
            approved_domains=frozenset({"assets.example.com", "other.example.com"}),
        ),
    )
    assert site.robots_mode == "deny_if_unavailable"
    assert site.crawl_delay_ms == 2000
    assert site.requests_per_minute == 20
    assert site.max_parallel_requests == 1
    assert site.allowed_content_types == {"text/html"}
    assert site.allow_paths == ("/docs/public",)
    assert site.deny_paths == ("/blocked", "/docs/private")
    site.validate_target("https://assets.example.com/docs/public/item")
    with pytest.raises(CollectionError):
        site.validate_target("https://other.example.com/docs/public/item")
    with pytest.raises(CollectionError):
        site.validate_target("https://example.com/docs/private/item")

    budget = effective_resource_budget(
        profile,
        OperatorResourceBudget(max_requests=5, max_pages=2, max_duration_seconds=60),
    )
    assert budget.max_requests == 5
    assert budget.max_pages == 2
    assert budget.max_duration_seconds == 60
    with pytest.raises(CollectionError) as caught:
        budget.validate_usage(requests=6, pages=1, bytes_received=10, duration_seconds=1)
    assert caught.value.code == "acquisition_budget_exhausted"

    default_site = effective_site_policy(profile, "https://example.com/docs/start")
    with pytest.raises(CollectionError) as domain_error:
        default_site.validate_target("https://assets.example.com/docs/item")
    assert domain_error.value.code == "site_policy_denied"


class RetryableOfflineFetcher:
    def __init__(self) -> None:
        self.calls = 0

    async def fetch(self, url: str, source_type: SourceType) -> FetchResponse:
        self.calls += 1
        raise CollectionError("timeout", "Target timed out", retryable=True)


@pytest.mark.asyncio
async def test_native_retries_are_clamped_by_total_request_budget() -> None:
    profile = AcquisitionProfileV1.model_validate(
        {"resource_budget": {"max_requests": 1, "max_retries_per_target": 2}}
    )
    fetcher = RetryableOfflineFetcher()
    request = AcquisitionRequest(
        source_id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        run_id=UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
        target_url="https://example.com/article",
        source_type=SourceType.URL,
        source_family=SourceFamily.GENERIC_WEB,
        mode=AcquisitionMode.NATIVE,
        discovery_mode=DiscoveryMode.SINGLE_PAGE,
        profile=profile,
        correlation_id=None,
    )
    with pytest.raises(CollectionError) as caught:
        await NativeAcquisitionBackend(fetcher).acquire(request)
    assert caught.value.code == "timeout"
    assert fetcher.calls == 1


@pytest.mark.asyncio
async def test_native_applies_site_policy_to_every_redirect_hop() -> None:
    calls: list[str] = []

    async def resolver(_hostname: str) -> list[str]:
        return ["93.184.216.34"]

    async def transport(**kwargs: object) -> WireResponse:
        calls.append(str(kwargs["url"]))
        return WireResponse(302, {"location": "https://assets.example.com/private"}, b"")

    request = AcquisitionRequest(
        source_id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        run_id=UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
        target_url="https://example.com/article",
        source_type=SourceType.URL,
        source_family=SourceFamily.GENERIC_WEB,
        mode=AcquisitionMode.NATIVE,
        discovery_mode=DiscoveryMode.SINGLE_PAGE,
        profile=AcquisitionProfileV1.model_validate({"approved_domains": ["assets.example.com"]}),
        correlation_id=None,
    )
    fetcher = SafeFetcher(resolver=resolver, transport=transport)
    with pytest.raises(CollectionError) as caught:
        await NativeAcquisitionBackend(fetcher).acquire(request)
    assert caught.value.code == "site_policy_denied"
    assert calls == ["https://example.com/article"]
