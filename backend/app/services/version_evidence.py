"""ACQ-1F version evidence extraction: noise normalization, three fingerprints,
structure summary, deterministic classification (docs/23 §10).

Pure functions only: no network, filesystem, database, or clock access. Fingerprints are
SHA-256 over canonical forms; the same input always yields the same value.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from contextlib import suppress
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from html.parser import HTMLParser
from typing import ClassVar
from urllib.parse import urlsplit

EXTRACTOR_VERSION = "extractor-v1"
DETECTOR_VERSION = "change-detector-v1"
FOUR_PLACES = Decimal("0.0001")

MAX_BLOCKS = 64
MAX_ATTACHMENTS = 32
MAX_FIELD_DIFF_FIELDS = 16
MAX_FIELD_DIFF_CHARS = 200

_ZERO_WIDTH = re.compile("[\u200b-\u200f\u202a-\u202e\ufeff]")
_TRACKING_QUERY = re.compile(r"[?&](utm_[^=&\s#]+|fbclid|gclid|ref_src)=[^&\s#]*")
_DYNAMIC_TIME_LINE = re.compile(
    r"(?i)^(?:last\s+updated|updated|revision|\u66f4\u65b0\u65f6\u95f4|"
    r"\u5237\u65b0\u65f6\u95f4)\s*[:\uff1a]?\s*\d"
)
_SOLE_DATETIME_LINE = re.compile(
    r"^\d{4}[-/.]\d{1,2}[-/.]\d{1,2}(?:[ T]\d{1,2}:\d{2}(?::\d{2})?)?$"
)

ATTACHMENT_SUFFIXES = frozenset(
    {
        ".pdf",
        ".zip",
        ".gz",
        ".tar",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".csv",
        ".txt",
        ".rtf",
        ".epub",
        ".mp3",
        ".m4a",
        ".wav",
        ".mp4",
        ".mov",
        ".webm",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".svg",
    }
)

MATERIALITY_CONTENT = Decimal("0.6000")
MATERIALITY_STRUCTURE = Decimal("0.3000")
MATERIALITY_METADATA = Decimal("0.1000")


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def normalize_content(text: str) -> str:
    """Deterministic content normalization: NFC, LF lines, zero-width and tracking
    query noise removed, dynamic time-only lines dropped, blank/duplicate spacing folded."""
    value = unicodedata.normalize("NFC", text)
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = _ZERO_WIDTH.sub("", value)
    value = _TRACKING_QUERY.sub("", value)
    blocks: list[str] = []
    for raw_line in value.split("\n"):
        line = " ".join(raw_line.split())
        if not line:
            continue
        if _DYNAMIC_TIME_LINE.match(line) or _SOLE_DATETIME_LINE.match(line):
            continue
        blocks.append(line)
    return "\n".join(blocks)


def content_fingerprint(normalized_content: str) -> str:
    return _sha256_text(normalized_content)


def metadata_values(
    *,
    title: str | None,
    author: str | None,
    published_at: datetime | None,
    content_type: str | None,
) -> dict[str, str | None]:
    """Field allowlist for the metadata fingerprint; UTC ISO time, stable keys."""
    published = published_at.astimezone(UTC).isoformat() if published_at is not None else None
    return {
        "author": author,
        "content_type": content_type,
        "published_at": published,
        "title": title,
    }


def metadata_fingerprint(values: dict[str, str | None]) -> str:
    return _sha256_text(canonical_json(values))


BLOCK_TAGS = frozenset(
    {
        "article",
        "aside",
        "blockquote",
        "figcaption",
        "figure",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "li",
        "main",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "tbody",
        "td",
        "th",
        "thead",
        "tr",
        "ul",
    }
)


def _attachment_identity(url: str) -> str | None:
    try:
        parsed = urlsplit(url.strip())
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    path = parsed.path or ""
    lowered = path.lower()
    if not any(lowered.endswith(suffix) for suffix in ATTACHMENT_SUFFIXES):
        return None
    host = parsed.hostname.rstrip(".").lower()
    return f"{host}{lowered}"


class _StructureParser(HTMLParser):
    _TAGS: ClassVar[dict[str, str]] = {
        "a": "href",
        "img": "src",
        "source": "src",
        "video": "src",
        "audio": "src",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.block_tags: list[str] = []
        self.found: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.lower()
        if normalized in BLOCK_TAGS and len(self.block_tags) < MAX_BLOCKS:
            self.block_tags.append(normalized)
        attribute = self._TAGS.get(normalized)
        if attribute is None:
            return
        values = {name.lower(): value for name, value in attrs if value is not None}
        candidate = values.get(attribute)
        if not candidate:
            return
        identity = _attachment_identity(candidate)
        if identity is not None and len(self.found) < MAX_ATTACHMENTS:
            self.found.add(identity)


def _decode(body: bytes, content_type: str) -> str:
    match = re.search(r"charset\s*=\s*[\"']?([\w.-]+)", content_type, re.IGNORECASE)
    encoding = match.group(1) if match else "utf-8"
    try:
        return body.decode(encoding, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


def structure_summary(
    *, body: bytes | None, content_type: str, normalized_content: str
) -> dict[str, object]:
    """Semantic block-tag sequence plus attachment identities; never the full DOM and
    never text content, so content edits alone cannot move the structure dimension."""
    del normalized_content
    block_tags: list[str] = []
    attachments: list[str] = []
    if body is not None and "html" in content_type.lower():
        parser = _StructureParser()
        with suppress(Exception):
            parser.feed(_decode(body, content_type))
            parser.close()
        block_tags = parser.block_tags[:MAX_BLOCKS]
        attachments = sorted(parser.found)[:MAX_ATTACHMENTS]
    return {
        "block_count": len(block_tags),
        "block_tags": block_tags,
        "attachments": attachments,
    }


def structure_fingerprint(summary: dict[str, object]) -> str:
    return _sha256_text(canonical_json(summary))


def classify_trio(
    *,
    previous: tuple[str, str, str] | None,
    current: tuple[str, str, str],
) -> str:
    """Deterministic change type from the fingerprint trio; content dominates."""
    if previous is None:
        return "created"
    if previous == current:
        return "unchanged"
    if previous[0] != current[0]:
        return "content_changed"
    if previous[2] != current[2]:
        return "structure_changed"
    return "metadata_changed"


def materiality_of(
    *, content_changed: bool, structure_changed: bool, metadata_changed: bool
) -> Decimal:
    value = Decimal(0)
    if content_changed:
        value += MATERIALITY_CONTENT
    if structure_changed:
        value += MATERIALITY_STRUCTURE
    if metadata_changed:
        value += MATERIALITY_METADATA
    return min(value, Decimal(1)).quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)


def _truncate(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if len(text) <= MAX_FIELD_DIFF_CHARS else text[:MAX_FIELD_DIFF_CHARS]


def bounded_field_diff(
    *,
    change_type: str,
    previous: dict[str, str | None] | None,
    current: dict[str, str | None],
) -> dict[str, object]:
    """Bounded, leak-free diff over the metadata allowlist plus content/structure flags."""
    if change_type in {"created", "removed", "unchanged"}:
        return {"changed": [], "fields": {}}
    changed: list[str] = []
    fields: dict[str, dict[str, str | None]] = {}
    if change_type == "content_changed":
        changed.append("content")
    if change_type == "structure_changed":
        changed.append("structure")
    for name, new_value in sorted(current.items()):
        old_value = None if previous is None else previous.get(name)
        if old_value != new_value and len(changed) < MAX_FIELD_DIFF_FIELDS:
            changed.append(name)
            fields[name] = {"old": _truncate(old_value), "new": _truncate(new_value)}
    return {"changed": changed[:MAX_FIELD_DIFF_FIELDS], "fields": fields}
