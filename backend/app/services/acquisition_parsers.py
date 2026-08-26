from __future__ import annotations

import hashlib
import re
import unicodedata
import xml.etree.ElementTree as StdElementTree
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import ClassVar
from urllib.parse import urljoin

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

from app.core.errors import AppError
from app.services.acquisition_types import (
    CollectionError,
    FetchResponse,
    ParseResult,
    RawCandidate,
)
from app.services.url_normalization import normalize_source_url


def normalize_text(value: str) -> str:
    return unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n")).strip()


def _canonical_url(value: str, base_url: str) -> str:
    try:
        return normalize_source_url(urljoin(base_url, value))[1]
    except AppError:
        raise CollectionError("extraction_failed", "Candidate URL is invalid") from None


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _first_text(element: StdElementTree.Element, names: set[str]) -> str | None:
    for descendant in element.iter():
        if _local_name(descendant.tag) in names and descendant.text:
            value = normalize_text("".join(descendant.itertext()))
            if value:
                return value
    return None


def _entry_link(element: StdElementTree.Element) -> str | None:
    for descendant in element.iter():
        if _local_name(descendant.tag) != "link":
            continue
        href = descendant.attrib.get("href")
        relation = descendant.attrib.get("rel", "alternate")
        if href and relation in {"", "alternate"}:
            return href.strip()
        if descendant.text and descendant.text.strip():
            return descendant.text.strip()
    return None


def _published(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def parse_feed(response: FetchResponse) -> ParseResult:
    try:
        root = ElementTree.fromstring(response.body)
    except (ElementTree.ParseError, DefusedXmlException):
        raise CollectionError("invalid_feed", "Feed XML is invalid") from None
    entries = [element for element in root.iter() if _local_name(element.tag) in {"item", "entry"}]
    if not entries:
        raise CollectionError("invalid_feed", "Feed contains no entries")
    candidates: list[RawCandidate] = []
    failed_count = 0
    for entry in entries:
        try:
            title = _first_text(entry, {"title"})
            raw_text = normalize_text(
                _first_text(entry, {"content", "encoded", "description", "summary"}) or ""
            )
            if not raw_text:
                failed_count += 1
                continue
            link = _entry_link(entry)
            canonical = _canonical_url(link or response.final_url, response.final_url)
            stable_content_id = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
            external_id = _first_text(entry, {"guid", "id"}) or (
                canonical if link else stable_content_id
            )
            published_value = _first_text(entry, {"published", "updated", "pubdate"})
            author = _first_text(entry, {"author", "creator"})
            metadata = {"author": author[:500]} if author else {}
            candidates.append(
                RawCandidate(
                    external_id=external_id[:512],
                    canonical_url=canonical,
                    raw_text=raw_text,
                    content_type=response.content_type,
                    title=title,
                    published_at=_published(published_value),
                    metadata=metadata,
                    dedupe_by_canonical=link is not None,
                )
            )
        except CollectionError:
            failed_count += 1
    if not candidates:
        raise CollectionError("empty_content", "Feed contains no non-empty content")
    return ParseResult(candidates=candidates, failed_count=failed_count)


class _ReadableHTMLParser(HTMLParser):
    _BLOCKED: ClassVar[set[str]] = {"script", "style", "noscript", "template"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocked_depth = 0
        self.title_depth = 0
        self.text_parts: list[str] = []
        self.title_parts: list[str] = []
        self.canonical: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.lower()
        if normalized in self._BLOCKED:
            self.blocked_depth += 1
        if normalized == "title":
            self.title_depth += 1
        if normalized == "link":
            values = {name.lower(): value for name, value in attrs if value is not None}
            if "canonical" in values.get("rel", "").lower().split():
                self.canonical = values.get("href")

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        if normalized in self._BLOCKED and self.blocked_depth:
            self.blocked_depth -= 1
        if normalized == "title" and self.title_depth:
            self.title_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.blocked_depth:
            return
        value = data.strip()
        if value:
            self.text_parts.append(value)
            if self.title_depth:
                self.title_parts.append(value)


def _decode_html(body: bytes, content_type: str) -> str:
    match = re.search(r"charset\s*=\s*[\"']?([\w.-]+)", content_type, re.IGNORECASE)
    encoding = match.group(1) if match else "utf-8"
    try:
        return body.decode(encoding, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


def parse_html(response: FetchResponse, source_normalized_url: str) -> ParseResult:
    parser = _ReadableHTMLParser()
    try:
        parser.feed(_decode_html(response.body, response.content_type))
        parser.close()
    except Exception:
        raise CollectionError("extraction_failed", "HTML extraction failed") from None
    raw_text = normalize_text("\n".join(parser.text_parts))
    if not raw_text:
        raise CollectionError("empty_content", "Page contains no readable text")
    canonical = _canonical_url(parser.canonical or response.final_url, response.final_url)
    title = normalize_text(" ".join(parser.title_parts)) or None
    return ParseResult(
        candidates=[
            RawCandidate(
                external_id=source_normalized_url,
                canonical_url=canonical,
                raw_text=raw_text,
                content_type=response.content_type,
                title=title,
                metadata={},
            )
        ]
    )
