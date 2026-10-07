"""ACQ-1G deterministic opportunity fact extraction (docs/24 §7, ADR-037).

Facts come only from explicit page structure: a JSON-LD ``JobPosting`` block and the
already-parsed candidate. Nothing is guessed: absent fields stay None and the hard
filter decides. ``client_metadata`` is a closed allowlist of publicly posted,
non-sensitive values.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlsplit

from app.domains.opportunity_policy import OpportunityFacts
from app.services.acquisition_parsers import _decode_html, _published
from app.services.acquisition_types import RawCandidate

MAX_TITLE = 300
MAX_DESCRIPTION = 20_000
MAX_SKILLS = 50
MAX_SKILL_CHARS = 80
MAX_PLATFORM = 120
MAX_DELIVERY_TYPE = 24
MAX_CLIENT_NAME = 120
MAX_JSONLD_NODES = 500

_JSONLD_PATTERN = re.compile(
    r"<script[^>]*type\s*=\s*[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True, slots=True)
class ExtractedOpportunity:
    """Bounded facts plus the allowlisted client metadata for one candidate."""

    facts: OpportunityFacts
    client_metadata: dict[str, Any]


class _TextCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        value = data.strip()
        if value:
            self.parts.append(value)


def _html_text(value: str) -> str:
    collector = _TextCollector()
    try:
        collector.feed(value)
        collector.close()
    except Exception:
        return ""
    return " ".join(collector.parts).strip()


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split())
    return normalized or None


def _job_posting(body: bytes | None, content_type: str | None) -> dict[str, Any] | None:
    if body is None or "html" not in (content_type or "").lower():
        return None
    try:
        html = _decode_html(body, content_type or "text/html")
    except Exception:
        return None
    for match in _JSONLD_PATTERN.finditer(html):
        raw = match.group(1).strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        for node in _iter_nodes(data):
            if _is_job_posting(node):
                return node
    return None


def _iter_nodes(data: Any) -> list[dict[str, Any]]:
    queue: list[Any] = [data]
    nodes: list[dict[str, Any]] = []
    seen = 0
    while queue and seen < MAX_JSONLD_NODES:
        current = queue.pop(0)
        seen += 1
        if isinstance(current, dict):
            nodes.append(current)
            for value in current.values():
                if isinstance(value, (dict, list)):
                    queue.append(value)
        elif isinstance(current, list):
            queue.extend(item for item in current if isinstance(item, (dict, list)))
    return nodes


def _is_job_posting(node: dict[str, Any]) -> bool:
    node_type = node.get("@type")
    if isinstance(node_type, str):
        return node_type.casefold() == "jobposting"
    if isinstance(node_type, list):
        return any(isinstance(item, str) and item.casefold() == "jobposting" for item in node_type)
    return False


def _decimal_of(value: Any) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float, str)):
        try:
            parsed = Decimal(str(value))
        except InvalidOperation:
            return None
        if not parsed.is_finite() or parsed < 0 or parsed > Decimal("10000000"):
            return None
        return parsed.quantize(Decimal("0.01"))
    return None


def _int_of(value: Any, minimum: int, maximum: int) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    parsed = int(value)
    if not minimum <= parsed <= maximum:
        return None
    return parsed


def _bool_of(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _currency(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().upper()
    return normalized if len(normalized) == 3 and normalized.isalpha() else None


def _salary(posting: dict[str, Any] | None) -> tuple[Decimal | None, Decimal | None, str | None]:
    if not posting:
        return None, None, None
    base = posting.get("baseSalary")
    if isinstance(base, (int, float, str)):
        return None, _decimal_of(base), None
    if not isinstance(base, dict):
        return None, None, None
    currency = _currency(base.get("currency"))
    value = base.get("value")
    if isinstance(value, dict):
        return _decimal_of(value.get("minValue")), _decimal_of(value.get("maxValue")), currency
    return _decimal_of(base.get("minValue")), _decimal_of(base.get("maxValue")), currency


def _skills(posting: dict[str, Any] | None) -> tuple[str, ...]:
    if not posting:
        return ()
    raw = posting.get("skills")
    items: list[str] = []
    if isinstance(raw, str):
        items = [part for part in raw.split(",")]
    elif isinstance(raw, list):
        items = [part for part in raw if isinstance(part, str)]
    normalized: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = " ".join(item.split())[:MAX_SKILL_CHARS]
        if value and value.casefold() not in seen:
            seen.add(value.casefold())
            normalized.append(value)
        if len(normalized) >= MAX_SKILLS:
            break
    return tuple(normalized)


def _host(url: str) -> str | None:
    try:
        host = urlsplit(url).hostname
    except ValueError:
        return None
    return host.lower()[:MAX_PLATFORM] if host else None


def _iso_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    return _published(value)


def _client_metadata(posting: dict[str, Any] | None) -> dict[str, Any]:
    if not posting:
        return {}
    metadata: dict[str, Any] = {}
    organization = posting.get("hiringOrganization")
    if isinstance(organization, dict):
        name = _text(organization.get("name"))
        if name:
            metadata["client_name"] = name[:MAX_CLIENT_NAME]
    rating = posting.get("clientRating")
    if (
        not isinstance(rating, bool)
        and isinstance(rating, (int, float))
        and 0 <= float(rating) <= 5
    ):
        metadata["client_rating"] = round(float(rating), 2)
    count = _int_of(posting.get("clientReviewCount"), 0, 1_000_000_000)
    if count is not None:
        metadata["client_review_count"] = count
    meetings = _int_of(posting.get("requiredMeetings"), 0, 1000)
    if meetings is not None:
        metadata["required_meetings"] = meetings
    maintenance = _bool_of(posting.get("maintenanceRequired"))
    if maintenance is not None:
        metadata["maintenance_required"] = maintenance
    return metadata


def extract_opportunity_facts(
    candidate: RawCandidate, body: bytes | None
) -> ExtractedOpportunity | None:
    """Build bounded facts for one candidate; requires an explicit title."""
    raw_text = candidate.raw_text or ""
    canonical = candidate.canonical_url or ""
    content_type = candidate.content_type or ""
    if not canonical:
        return None
    posting = _job_posting(body, content_type)
    title = _text(posting.get("title")) if posting else None
    title = title or _text(candidate.title)
    if not title:
        return None
    description = None
    if posting:
        posted_description = posting.get("description")
        if isinstance(posted_description, str):
            description = _html_text(posted_description) or posted_description.strip()
    description = (description or raw_text).strip()[:MAX_DESCRIPTION]
    if not description:
        return None
    budget_min, budget_max, currency = _salary(posting)
    metadata = _client_metadata(posting)
    delivery = None
    if posting:
        raw_delivery = _text(posting.get("deliveryType"))
        delivery = raw_delivery[:MAX_DELIVERY_TYPE] if raw_delivery else None
    published_at = candidate.published_at
    if published_at is None:
        published_at = _iso_datetime(posting.get("datePosted")) if posting else None
    deadline = _iso_datetime(posting.get("validThrough")) if posting else None
    effort = _decimal_of(posting.get("estimatedEffortHours")) if posting else None
    facts = OpportunityFacts(
        title=title[:MAX_TITLE],
        description=description,
        source_url=canonical,
        platform=_host(canonical),
        budget_min=budget_min,
        budget_max=budget_max,
        currency=currency,
        skills=_skills(posting),
        deadline=deadline,
        published_at=published_at,
        estimated_effort_hours=effort,
        delivery_type=delivery,
        required_meetings=metadata.get("required_meetings"),
        maintenance_required=metadata.get("maintenance_required"),
    )
    return ExtractedOpportunity(facts=facts, client_metadata=metadata)
