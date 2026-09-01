from __future__ import annotations

import socket
from decimal import Decimal

import pytest

from app.adapters.acquisition.static_scrapling import (
    meaningful_length,
    normalize_observed_text,
    observe_html,
)
from app.models.entities import SourceFamily, SourceType
from app.services.acquisition_parsers import parse_feed
from app.services.acquisition_types import AcquisitionResult, FetchResponse
from app.services.extraction import attach_extraction_observations
from app.services.extraction_quality import (
    aggregate_quality,
    quality_bucket,
    quality_score,
    update_quality_ewma,
)


def score_for(m: int, *, scripts: int = 0) -> Decimal:
    return quality_score(
        meaningful_chars=m,
        visible_chars=m,
        navigation_chars=0,
        executable_script_count=scripts,
        has_title=False,
        has_publish_date=False,
        has_author=False,
        has_canonical=False,
    )


@pytest.mark.parametrize(
    ("meaningful", "expected"),
    [
        (0, "0.0000"),
        (79, "0.4093"),
        (80, "0.4100"),
        (399, "0.6493"),
        (400, "0.6500"),
        (401, "0.6500"),
    ],
)
def test_quality_golden_boundaries(meaningful: int, expected: str) -> None:
    assert score_for(meaningful) == Decimal(expected)


def test_quality_exact_math_validation_buckets_and_ewma() -> None:
    assert quality_bucket(Decimal("0.4499")) == "low"
    assert quality_bucket(Decimal("0.4500")) == "marginal"
    assert quality_bucket(Decimal("0.5999")) == "marginal"
    assert quality_bucket(Decimal("0.6000")) == "acceptable"
    assert aggregate_quality([Decimal("0.3333"), Decimal("0.6666")]) == Decimal("0.5000")
    assert aggregate_quality([Decimal("0.5000"), None]) is None
    assert update_quality_ewma(Decimal("0.4000"), Decimal("0.6000")) == Decimal("0.4400")
    assert update_quality_ewma(Decimal("0.4000"), None) == Decimal("0.4000")
    with pytest.raises(ValueError):
        quality_score(
            meaningful_chars=True,
            visible_chars=1,
            navigation_chars=0,
            executable_script_count=0,
            has_title=False,
            has_publish_date=False,
            has_author=False,
            has_canonical=False,
        )
    with pytest.raises(ValueError):
        quality_bucket(Decimal("NaN"))


def test_text_normalization_and_unicode_count() -> None:
    assert normalize_observed_text(" A\r\n\tB  e\u0301 ") == "A B é"
    assert meaningful_length("中文A9🙂, ") == 4


@pytest.mark.parametrize("family", list(SourceFamily))
def test_all_families_use_common_static_extractor_without_network(
    family: SourceFamily, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        socket,
        "create_connection",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("network forbidden")),
    )
    response = FetchResponse(
        final_url="https://example.com/original",
        content_type="text/html; charset=utf-8",
        body=(
            b"<html><head><meta property='og:title' content='Meta title'>"
            b"<meta property='article:published_time' content='2026-08-30T10:00:00+02:00'>"
            b"<meta name='author' content='Ada'><link rel='canonical' href='/canonical'>"
            b"<script type='application/ld+json'>{}</script></head><body>"
            b"<nav>Navigation noise</nav><article><h1>Fallback</h1>"
            b"<p>Hello static extraction</p><a href='/next?q=secret#part'>Next</a>"
            b"<aside><aside>Nested noise</aside></aside></article></body></html>"
        ),
    )
    observed = observe_html(response, family, "article")
    assert observed.title == "Meta title"
    assert observed.author == "Ada"
    assert observed.published_at == "2026-08-30T08:00:00Z"
    assert observed.canonical_url == "https://example.com/canonical"
    assert observed.links == ("https://example.com/next",)
    assert observed.evidence.fields["title"].evidence_path == "html.og_title"
    assert observed.evidence.metrics.executable_script_count == 0
    assert observed.safe_metadata == {
        "source_family": family.value,
        "content_profile": "article",
        "extractor_version": "static-extractor-v1",
        "quality_version": "extraction-quality-v1",
    }
    assert len(observed.evidence.compact_json()) <= 16 * 1024
    assert not {"doi", "amount", "deadline", "location"} & observed.safe_metadata.keys()


def test_html_fallback_hidden_script_shell_and_resource_limit() -> None:
    html = (
        "<html><head><title>Head title</title></head><body>"
        "<header>noise</header><main><h1>H1 title</h1>"
        "<p aria-hidden='true'>hidden words</p><p>" + ("x" * 79) + "</p>"
        "<script>run()</script><script type='application/ld+json'>{}</script>"
        "</main></body></html>"
    )
    observed = observe_html(
        FetchResponse("https://example.com/", "text/html", html.encode()),
        SourceFamily.GENERIC_WEB,
        "generic",
    )
    assert observed.title == "H1 title"
    assert observed.evidence.fields["title"].evidence_path == "html.h1"
    assert observed.evidence.metrics.executable_script_count == 1
    assert "hidden" not in observed.text

    too_deep = "<div>" * 129 + "x" + "</div>" * 129
    limited = observe_html(
        FetchResponse("https://example.com/", "text/html", too_deep.encode()),
        SourceFamily.GENERIC_WEB,
        "generic",
    )
    assert limited.evidence.quality_score is None
    assert limited.evidence.diagnostic_codes == ("extraction_resource_limit",)

    evasive = ("<div></bogus>" * 129) + "x" + ("</div>" * 129)
    evasion_limited = observe_html(
        FetchResponse("https://example.com/", "text/html", evasive.encode()),
        SourceFamily.GENERIC_WEB,
        "generic",
    )
    assert evasion_limited.evidence.diagnostic_codes == ("extraction_resource_limit",)


def test_attribute_tokens_are_ascii_casefolded_and_hidden_ancestor_is_ineligible() -> None:
    response = FetchResponse(
        "https://example.com/",
        "text/html",
        (
            b"<html><head><meta PROPERTY='OG:TITLE' content='Case title'>"
            b"<link REL='CANONICAL alternate' href='/case'></head><body>"
            b"<div hidden><article><h1>Wrong root</h1><p>hidden</p></article></div>"
            b"<div ROLE='MAIN'><p>Visible body</p><a REL='AUTHOR'>Case Author</a>"
            b"<a hidden href='/hidden'>hidden link</a></div></body></html>"
        ),
    )
    observed = observe_html(response, SourceFamily.POLICY, "document")
    assert observed.title == "Case title"
    assert observed.author == "Case Author"
    assert observed.text == "Visible body Case Author"
    assert observed.links == ()
    assert observed.evidence.fields["text"].evidence_path == "html.role_main"


def test_feed_candidates_are_individually_observed_and_fallback_is_not_link() -> None:
    response = FetchResponse(
        final_url="https://example.com/feed",
        content_type="application/rss+xml",
        body=(
            b"<rss><channel>"
            b"<item><guid>a</guid><title>A</title><description>Alpha body</description>"
            b"<pubDate>Sun, 30 Aug 2026 10:00:00 GMT</pubDate></item>"
            b"<item><guid>b</guid><title>B</title><description>Beta distinct body</description>"
            b"<link>https://example.com/b?q=1</link></item>"
            b"</channel></rss>"
        ),
    )
    parsed = parse_feed(response)
    enriched = attach_extraction_observations(
        AcquisitionResult(response=response, retry_count=0, budget_used={}),
        family=SourceFamily.TECHNOLOGY,
        content_profile="feed",
        source_type=SourceType.RSS,
        parsed=parsed,
    )
    assert len(enriched.observations) == 2
    first, second = enriched.observations
    assert first.evidence.fields["canonical_url"].evidence_path == "fallback.feed_url"
    assert first.links == ()
    assert second.evidence.fields["canonical_url"].evidence_path == "feed.link"
    assert second.links == ("https://example.com/b",)
    assert first.evidence.quality_score is not None
    assert second.evidence.quality_score is not None
