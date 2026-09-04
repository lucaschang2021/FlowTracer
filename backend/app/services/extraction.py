from __future__ import annotations

import re
import unicodedata
import xml.etree.ElementTree as StdElementTree
from dataclasses import replace
from datetime import UTC
from decimal import Decimal
from urllib.parse import urlsplit, urlunsplit

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

from app.adapters.acquisition.static_scrapling import observe_html, unscored_observation
from app.models.entities import SourceFamily, SourceType
from app.services.acquisition_parsers import (
    _canonical_url,
    _entry_link,
    _first_text,
    _local_name,
    _published,
    normalize_text,
)
from app.services.acquisition_policy import NetworkPolicy
from app.services.acquisition_types import (
    AcquisitionResult,
    CollectionError,
    FetchResponse,
    ParseResult,
)
from app.services.extraction_quality import quality_bucket, quality_score
from app.services.extraction_types import ExtractionObservation, FieldEvidence


def _feed_entries(body: bytes) -> list[StdElementTree.Element]:
    try:
        root = ElementTree.fromstring(body)
    except (ElementTree.ParseError, DefusedXmlException):
        return []
    return [element for element in root.iter() if _local_name(element.tag) in {"item", "entry"}]


def _aware_source_date(value: str | None) -> bool:
    if not value or not re.search(r"(?:Z|[+-]\d\d:?\d\d|\b(?:UT|GMT)\b)\s*$", value, re.I):
        return False
    parsed = _published(value)
    return parsed is not None and parsed.tzinfo is not None


def _feed_field(value: str | None, maximum: int) -> str | None:
    if value is None:
        return None
    if any(
        unicodedata.category(char) == "Cs"
        or (unicodedata.category(char) == "Cc" and char not in "\r\n\t")
        for char in value
    ):
        return None
    normalized = normalize_text(value)
    if (
        not normalized
        or len(normalized) > maximum
        or any(unicodedata.category(char) in {"Cc", "Cs"} for char in normalized)
    ):
        return None
    return normalized


def _valid_feed_link(value: str | None) -> bool:
    if value is None:
        return False
    try:
        NetworkPolicy().validate(value)
    except CollectionError:
        return False
    return len(value.encode()) <= 2048


def _feed_observations(
    response: FetchResponse, family: SourceFamily, content_profile: str, parsed: ParseResult
) -> tuple[ExtractionObservation, ...]:
    observations: list[ExtractionObservation] = []
    candidate_index = 0
    for entry in _feed_entries(response.body):
        fragment = _first_text(entry, {"content", "encoded", "description", "summary"}) or ""
        if not fragment.strip():
            continue
        link = _entry_link(entry)
        try:
            _canonical_url(link or response.final_url, response.final_url)
        except CollectionError:
            continue
        if candidate_index >= len(parsed.candidates):
            break
        candidate = parsed.candidates[candidate_index]
        candidate_index += 1
        base = observe_html(
            FetchResponse(
                final_url=response.final_url,
                content_type="text/html; charset=utf-8",
                body=fragment.encode("utf-8"),
            ),
            family,
            content_profile,
        )
        if base.evidence.quality_score is None:
            observations.append(base)
            continue
        valid_link = _valid_feed_link(candidate.canonical_url if link else None)
        published_raw = _first_text(entry, {"published", "updated", "pubdate"})
        valid_date = _aware_source_date(published_raw)
        title = _feed_field(candidate.title, 500)
        author = _feed_field(str(candidate.metadata.get("author", "")) or None, 300)
        score = quality_score(
            meaningful_chars=base.evidence.metrics.meaningful_chars,
            visible_chars=base.evidence.metrics.visible_chars,
            navigation_chars=base.evidence.metrics.navigation_chars,
            executable_script_count=base.evidence.metrics.executable_script_count,
            has_title=title is not None,
            has_publish_date=valid_date,
            has_author=author is not None,
            has_canonical=valid_link,
        )
        bucket = quality_bucket(score)
        diagnostics = (f"extraction_quality_{bucket}",) if bucket in {"low", "marginal"} else ()
        fields = {
            "title": FieldEvidence(
                title is not None,
                "feed.title" if title else "missing",
                Decimal("1.0000") if title else Decimal(0),
            ),
            "text": FieldEvidence(True, "feed.content", Decimal("1.0000")),
            "author": FieldEvidence(
                author is not None,
                "feed.author" if author else "missing",
                Decimal("1.0000") if author else Decimal(0),
            ),
            "published_at": FieldEvidence(
                valid_date,
                "feed.published" if valid_date else "missing",
                Decimal("1.0000") if valid_date else Decimal(0),
            ),
            "canonical_url": FieldEvidence(
                valid_link or link is None,
                "feed.link" if valid_link else "fallback.feed_url",
                Decimal("1.0000") if valid_link else Decimal(0),
            ),
        }
        evidence = replace(
            base.evidence,
            fields=fields,
            quality_score=score,
            quality_bucket=bucket,  # type: ignore[arg-type]
            diagnostic_codes=diagnostics,
        )
        observations.append(
            replace(
                base,
                evidence=evidence,
                title=title,
                author=author,
                published_at=(
                    candidate.published_at.astimezone(UTC).isoformat().replace("+00:00", "Z")
                    if candidate.published_at and valid_date
                    else None
                ),
                canonical_url=candidate.canonical_url,
                links=(urlunsplit((*urlsplit(candidate.canonical_url)[:3], "", "")),)
                if valid_link
                else (),
            )
        )
    while len(observations) < len(parsed.candidates):
        observations.append(
            unscored_observation(family, content_profile=content_profile, resource_limit=False)
        )
    return tuple(observations)


def attach_extraction_observations(
    result: AcquisitionResult,
    *,
    family: SourceFamily,
    content_profile: str,
    source_type: SourceType,
    parsed: ParseResult,
) -> AcquisitionResult:
    if source_type == SourceType.RSS:
        observations = _feed_observations(result.response, family, content_profile, parsed)
    else:
        observations = (observe_html(result.response, family, content_profile),)
    return replace(result, observations=observations)
