from __future__ import annotations

import json
import unicodedata
from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import Decimal
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

from scrapling.parser import Selector

from app.core.errors import AppError
from app.models.entities import SourceFamily
from app.services.acquisition_parsers import _decode_html
from app.services.acquisition_policy import NetworkPolicy
from app.services.acquisition_types import CollectionError, FetchResponse
from app.services.extraction_quality import quality_bucket, quality_score
from app.services.extraction_types import (
    EXTRACTOR_VERSION,
    QUALITY_VERSION,
    ExtractionEvidence,
    ExtractionMetrics,
    ExtractionObservation,
    FieldEvidence,
)
from app.services.url_normalization import normalize_source_url

MAX_ELEMENTS = 50_000
MAX_DEPTH = 128
MAX_ATTRIBUTE_BYTES = 2 * 1024 * 1024
MAX_EVIDENCE_BYTES = 16 * 1024
MAX_METADATA_BYTES = 8 * 1024
MAX_LINKS = 128
MAX_LINK_NODES = 4096
MAX_LINK_BYTES = 64 * 1024
_HIDDEN = frozenset({"head", "script", "style", "noscript", "template"})
_NOISE_TAGS = frozenset({"nav", "header", "footer", "aside"})
_NOISE_ROLES = frozenset({"navigation", "banner", "contentinfo"})
_SCRIPT_TYPES = frozenset(
    {
        "",
        "module",
        "text/javascript",
        "application/javascript",
        "text/ecmascript",
        "application/ecmascript",
    }
)
_VOID = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)


class ObservationResourceLimit(ValueError):
    pass


class _BoundedPreflight(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.elements = 0
        self.stack: list[str] = []
        self.attribute_bytes = 0
        self.found_body = False
        self.in_first_body = False
        self.first_body_html: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.lower()
        self.elements += 1
        if normalized not in _VOID:
            self.stack.append(normalized)
        self.attribute_bytes += sum(len((value or "").encode()) for _, value in attrs)
        self._check()
        if normalized == "body" and not self.found_body:
            self.found_body = True
            self.in_first_body = True
        elif self.in_first_body:
            raw_tag = self.get_starttag_text()
            if raw_tag is not None:
                self.first_body_html.append(raw_tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.lower()
        self.elements += 1
        self.attribute_bytes += sum(len((value or "").encode()) for _, value in attrs)
        self._check()
        if normalized == "body" and not self.found_body:
            self.found_body = True
        elif self.in_first_body:
            raw_tag = self.get_starttag_text()
            if raw_tag is not None:
                self.first_body_html.append(raw_tag)

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        if self.in_first_body:
            if normalized == "body":
                self.in_first_body = False
            else:
                self.first_body_html.append(f"</{tag}>")
        if normalized in self.stack:
            index = len(self.stack) - 1 - self.stack[::-1].index(normalized)
            del self.stack[index:]

    def handle_data(self, data: str) -> None:
        if self.in_first_body:
            self.first_body_html.append(data)

    def handle_entityref(self, name: str) -> None:
        if self.in_first_body:
            self.first_body_html.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        if self.in_first_body:
            self.first_body_html.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        if self.in_first_body:
            self.first_body_html.append(f"<!--{data}-->")

    def _check(self) -> None:
        if (
            self.elements > MAX_ELEMENTS
            or len(self.stack) > MAX_DEPTH
            or self.attribute_bytes > MAX_ATTRIBUTE_BYTES
        ):
            raise ObservationResourceLimit


def normalize_observed_text(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))
    return " ".join(normalized.split())


def meaningful_length(value: str) -> int:
    return sum(unicodedata.category(character)[0] in {"L", "N"} for character in value)


def _attr(node: Any, name: str) -> str:
    return str(node.attrib.get(name, ""))


def _is_hidden(node: Any) -> bool:
    return (
        str(node.tag).lower() in _HIDDEN
        or "hidden" in node.attrib
        or _attr(node, "aria-hidden").strip().casefold() == "true"
    )


def _is_noise(node: Any) -> bool:
    return (
        str(node.tag).lower() in _NOISE_TAGS
        or _attr(node, "role").strip().casefold() in _NOISE_ROLES
    )


def _has_hidden_ancestor(node: Any) -> bool:
    return _is_hidden(node) or any(_is_hidden(parent) for parent in node.iterancestors())


def _has_noise_ancestor(node: Any) -> bool:
    return _is_noise(node) or any(_is_noise(parent) for parent in node.iterancestors())


def _attribute_equals(nodes: Iterable[Any], name: str, expected: str) -> list[Any]:
    return [node for node in nodes if _attr(node, name).strip().casefold() == expected]


def _attribute_token(nodes: Iterable[Any], name: str, token: str) -> list[Any]:
    return [
        node
        for node in nodes
        if token in {candidate.casefold() for candidate in _attr(node, name).split()}
    ]


def _text_nodes(
    node: Any,
    *,
    remove_noise: bool,
    inherited_hidden: bool = False,
    inherited_noise: bool = False,
) -> list[str]:
    hidden = inherited_hidden or _is_hidden(node)
    noise = inherited_noise or _is_noise(node)
    output: list[str] = []
    if not hidden and not (remove_noise and noise) and node.text:
        output.append(str(node.text))
    for child in node:
        output.extend(
            _text_nodes(
                child,
                remove_noise=remove_noise,
                inherited_hidden=hidden,
                inherited_noise=noise,
            )
        )
        if not hidden and not (remove_noise and noise) and child.tail:
            output.append(str(child.tail))
    return output


def _valid_field(value: str | None, maximum: int) -> str | None:
    if value is None:
        return None
    if any(
        unicodedata.category(char) == "Cs"
        or (unicodedata.category(char) == "Cc" and char not in "\r\n\t")
        for char in value
    ):
        return None
    normalized = normalize_observed_text(value)
    if not normalized or len(normalized) > maximum:
        return None
    if any(unicodedata.category(char) in {"Cc", "Cs"} for char in normalized):
        return None
    return normalized


def _first_value(nodes: Iterable[Any], *, attribute: str | None = None, maximum: int) -> str | None:
    for node in nodes:
        raw = (
            _attr(node, attribute) if attribute else " ".join(_text_nodes(node, remove_noise=False))
        )
        value = _valid_field(raw, maximum)
        if value is not None:
            return value
    return None


def _date(value: str | None) -> str | None:
    candidate = _valid_field(value, 100)
    if candidate is None:
        return None
    try:
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _safe_url(value: str, base_url: str, *, strip_query: bool = False) -> str | None:
    try:
        if any(unicodedata.category(char) in {"Cc", "Cs"} for char in value):
            return None
        joined = urljoin(base_url, value)
        if strip_query:
            parsed = urlsplit(joined)
            joined = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
        _, normalized = normalize_source_url(joined)
        if len(normalized.encode()) > 2048:
            return None
        NetworkPolicy().validate(normalized)
    except (AppError, CollectionError, ValueError):
        return None
    return normalized


def _field(present: bool, path: str, confidence: str) -> FieldEvidence:
    return FieldEvidence(
        present=present,
        evidence_path=path if present else "missing",
        confidence=Decimal(confidence) if present else Decimal("0.0000"),
    )


def _metadata(family: SourceFamily, content_profile: str) -> dict[str, str]:
    return {
        "source_family": family.value,
        "content_profile": content_profile,
        "extractor_version": EXTRACTOR_VERSION,
        "quality_version": QUALITY_VERSION,
    }


def unscored_observation(
    family: SourceFamily, *, content_profile: str, resource_limit: bool
) -> ExtractionObservation:
    code = "extraction_resource_limit" if resource_limit else "extraction_observation_failed"
    fields = {
        name: _field(False, "missing", "0")
        for name in ("title", "text", "author", "published_at", "canonical_url")
    }
    evidence = ExtractionEvidence(
        source_family=family,
        fields=fields,
        metrics=ExtractionMetrics(0, 0, 0, 0),
        quality_score=None,
        quality_bucket="unscored",
        diagnostic_codes=(code,),
    )
    return ExtractionObservation(
        evidence=evidence, safe_metadata=_metadata(family, content_profile), links=()
    )


def observe_html(
    response: FetchResponse, family: SourceFamily, content_profile: str
) -> ExtractionObservation:
    try:
        html = _decode_html(response.body, response.content_type)
        preflight = _BoundedPreflight()
        preflight.feed(html)
        preflight.close()
    except ObservationResourceLimit:
        return unscored_observation(family, content_profile=content_profile, resource_limit=True)
    except Exception:
        return unscored_observation(family, content_profile=content_profile, resource_limit=False)
    try:
        page = Selector(html, url=response.final_url)
        root = page._root
        if preflight.found_body:
            scope_page = Selector(
                f"<body>{''.join(preflight.first_body_html)}</body>", url=response.final_url
            )
            scope = scope_page.css("body")[0]._root
        else:
            scope = root
        roots: list[tuple[Any, str]] = []
        roots.extend((node, "html.article") for node in scope.iter("article"))
        roots.extend((node, "html.main") for node in scope.iter("main"))
        roots.extend(
            (node, "html.role_main") for node in _attribute_equals(scope.iter(), "role", "main")
        )
        body_root: Any = scope
        text_rule = "html.body" if preflight.found_body else "html.root"
        for candidate, rule in roots:
            if _has_hidden_ancestor(candidate) or _has_noise_ancestor(candidate):
                continue
            candidate_text = normalize_observed_text(
                " ".join(_text_nodes(candidate, remove_noise=True))
            )
            if meaningful_length(candidate_text) > 0:
                body_root, text_rule = candidate, rule
                break
        body_text = normalize_observed_text(" ".join(_text_nodes(body_root, remove_noise=True)))
        visible_text = normalize_observed_text(" ".join(_text_nodes(scope, remove_noise=False)))
        noise_parts: list[str] = []
        for node in scope.iter():
            if (
                _is_noise(node)
                and not _has_hidden_ancestor(node)
                and not any(_is_noise(parent) for parent in node.iterancestors())
            ):
                noise_parts.extend(_text_nodes(node, remove_noise=False))
        noise_text = normalize_observed_text(" ".join(noise_parts))
        m = meaningful_length(body_text)
        v = meaningful_length(visible_text)
        n = meaningful_length(noise_text)
        scripts = 0
        for script in root.iter("script"):
            if any(str(parent.tag).lower() == "template" for parent in script.iterancestors()):
                continue
            script_type = _attr(script, "type").strip().lower()
            if script_type in _SCRIPT_TYPES and (
                _attr(script, "src").strip() or (script.text or "").strip()
            ):
                scripts += 1

        title = _first_value(
            _attribute_equals(root.iter("meta"), "property", "og:title"),
            attribute="content",
            maximum=500,
        )
        title_rule, title_conf = "html.og_title", "1.0000"
        if title is None:
            title = _first_value(body_root.cssselect("h1"), maximum=500)
            title_rule, title_conf = "html.h1", "0.7500"
        if title is None:
            title = _first_value(page.css("head title"), maximum=500)
            title_rule, title_conf = "html.title", "0.7500"

        author = _first_value(
            _attribute_equals(root.iter("meta"), "name", "author"),
            attribute="content",
            maximum=300,
        )
        author_rule, author_conf = "html.author_meta", "1.0000"
        if author is None:
            author = _first_value(_attribute_token(body_root.iter(), "rel", "author"), maximum=300)
            author_rule, author_conf = "html.author_rel", "0.7500"

        published_raw = _first_value(
            _attribute_equals(root.iter("meta"), "property", "article:published_time"),
            attribute="content",
            maximum=100,
        )
        published = _date(published_raw)
        published_rule, published_conf = "html.published_meta", "1.0000"
        if published is None:
            published_raw = _first_value(
                body_root.cssselect("time[datetime]"), attribute="datetime", maximum=100
            )
            published = _date(published_raw)
            published_rule, published_conf = "html.time", "0.7500"

        heads = list(root.iter("head"))
        canonical_nodes = (
            _attribute_token(heads[0].iter("link"), "rel", "canonical") if heads else []
        )
        canonical_raw = _first_value(canonical_nodes, attribute="href", maximum=2048)
        canonical = _safe_url(canonical_raw, response.final_url) if canonical_raw else None
        canonical_real = canonical is not None
        if canonical is None:
            canonical = _safe_url(response.final_url, response.final_url)
        canonical_rule = "html.canonical" if canonical_real else "fallback.final_url"
        canonical_conf = "1.0000" if canonical_real else "0.0000"

        score = quality_score(
            meaningful_chars=m,
            visible_chars=v,
            navigation_chars=n,
            executable_script_count=scripts,
            has_title=title is not None,
            has_publish_date=published is not None,
            has_author=author is not None,
            has_canonical=canonical_real,
        )
        bucket = quality_bucket(score)
        diagnostic = f"extraction_quality_{bucket}"
        diagnostics = (diagnostic,) if bucket in {"low", "marginal"} else ()
        fields = {
            "title": _field(title is not None, title_rule, title_conf),
            "text": _field(m > 0, text_rule, "0.7500"),
            "author": _field(author is not None, author_rule, author_conf),
            "published_at": _field(published is not None, published_rule, published_conf),
            "canonical_url": _field(canonical is not None, canonical_rule, canonical_conf),
        }
        links: list[str] = []
        seen: set[str] = set()
        for anchor in scope.cssselect("a[href]")[:MAX_LINK_NODES]:
            if _has_hidden_ancestor(anchor):
                continue
            link = _safe_url(_attr(anchor, "href"), response.final_url, strip_query=True)
            if link is None or link in seen:
                continue
            candidate = [*links, link]
            encoded = json.dumps(candidate, ensure_ascii=False, separators=(",", ":")).encode()
            if len(candidate) > MAX_LINKS or len(encoded) > MAX_LINK_BYTES:
                break
            links.append(link)
            seen.add(link)
        evidence = ExtractionEvidence(
            source_family=family,
            fields=fields,
            metrics=ExtractionMetrics(m, v, n, scripts),
            quality_score=score,
            quality_bucket=bucket,  # type: ignore[arg-type]
            diagnostic_codes=diagnostics,
        )
        metadata = _metadata(family, content_profile)
        if (
            len(evidence.compact_json()) > MAX_EVIDENCE_BYTES
            or len(json.dumps(metadata, separators=(",", ":")).encode()) > MAX_METADATA_BYTES
        ):
            return unscored_observation(
                family, content_profile=content_profile, resource_limit=True
            )
        return ExtractionObservation(
            evidence=evidence,
            safe_metadata=metadata,
            links=tuple(links),
            title=title,
            text=body_text,
            author=author,
            published_at=published,
            canonical_url=canonical,
        )
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        return unscored_observation(family, content_profile=content_profile, resource_limit=False)
