"""Bounded HTML link extraction for Controlled Discovery (stdlib only, no I/O).

Extracts <a href> anchors with their visible text and rel tokens. Malformed input
yields an empty result rather than raising: discovery treats absence of usable links
as "nothing to discover", never as a reason to widen scope.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin

_CHARSET = re.compile(r"charset\s*=\s*[\"']?([\w.-]+)", re.IGNORECASE)
_IGNORED_TAGS = frozenset({"script", "style", "noscript", "template"})


@dataclass(frozen=True, slots=True)
class LinkRef:
    url: str
    anchor_text: str
    nofollow: bool


class _LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored_depth = 0
        self._pending_href: str | None = None
        self._pending_rel: str = ""
        self._anchor_parts: list[str] = []
        self.links: list[tuple[str, str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.lower()
        if normalized in _IGNORED_TAGS:
            self._ignored_depth += 1
            return
        if normalized != "a" or self._ignored_depth or self._pending_href is not None:
            return
        values = {name.lower(): value for name, value in attrs if value is not None}
        href = values.get("href")
        if not href or not href.strip():
            return
        self._pending_href = href.strip()
        self._pending_rel = values.get("rel", "").lower()
        self._anchor_parts = []

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        if normalized in _IGNORED_TAGS and self._ignored_depth:
            self._ignored_depth -= 1
            return
        if normalized != "a" or self._pending_href is None or self._ignored_depth:
            return
        anchor = " ".join(part.strip() for part in self._anchor_parts if part.strip())
        self.links.append((self._pending_href, anchor[:300], self._pending_rel))
        self._pending_href = None
        self._pending_rel = ""
        self._anchor_parts = []

    def handle_data(self, data: str) -> None:
        if self._pending_href is not None and not self._ignored_depth:
            self._anchor_parts.append(data)


def _decode(body: bytes, content_type: str) -> str:
    match = _CHARSET.search(content_type)
    encoding = match.group(1) if match else "utf-8"
    try:
        return body.decode(encoding, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


def extract_links(body: bytes, content_type: str, base_url: str, *, limit: int) -> list[LinkRef]:
    """Absolute link references in document order, bounded by ``limit``."""
    parser = _LinkCollector()
    try:
        parser.feed(_decode(body, content_type))
        parser.close()
    except Exception:
        return []
    results: list[LinkRef] = []
    for href, anchor, rel in parser.links:
        if len(results) >= limit:
            break
        try:
            absolute = urljoin(base_url, href)
        except ValueError:
            continue
        tokens = rel.split() if rel else []
        results.append(LinkRef(url=absolute, anchor_text=anchor, nofollow="nofollow" in tokens))
    return results
