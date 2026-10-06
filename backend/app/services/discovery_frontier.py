"""ACQ-1E frontier planning and checkpoint merge (pure; docs/61 §3/§6/§7).

Given one fetched page, plan the discovered links that survive scope, site policy,
scoring, and hard caps, then merge them into the source's persistent checkpoint.
Planning itself issues no requests; the I2 crawl executor (``discovery_crawl``)
consumes the frontier through the pure checkpoint transitions defined here.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

from app.core.errors import AppError
from app.models.entities import DiscoveryMode
from app.services.discovery_links import LinkRef, extract_links
from app.services.discovery_policy import (
    DISCOVERY_POLICY_VERSION,
    MAX_DISCOVERY_LINKS_PER_PAGE,
    MAX_FRONTIER_SIZE_DEFAULT,
    MIN_SCORE_DEFAULT,
    path_allowed,
    scope_allows,
    score_link,
)
from app.services.url_normalization import normalize_source_url

CHECKPOINT_VERSION = 2
MAX_SEEN_HASHES = 2000
FRONTIER_HARD_CAP = 500
DEFAULT_TARGET_ATTEMPTS = 0


@dataclass(frozen=True, slots=True)
class DiscoveryPlan:
    entries: list[dict[str, Any]]
    summary: dict[str, Any]
    checkpoint: dict[str, Any]


def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def checkpoint_view(
    checkpoint: dict[str, Any] | None,
) -> tuple[set[str], list[dict[str, Any]], dict[str, int]]:
    """Tolerant view of a persisted checkpoint; malformed content yields an empty state."""
    if not isinstance(checkpoint, dict):
        return set(), [], {}
    seen_raw = checkpoint.get("seen")
    seen = (
        {value for value in seen_raw if isinstance(value, str)}
        if isinstance(seen_raw, list)
        else set()
    )
    frontier_raw = checkpoint.get("frontier")
    frontier = list(frontier_raw) if isinstance(frontier_raw, list) else []
    counters_raw = checkpoint.get("counters")
    counters = (
        {key: value for key, value in counters_raw.items() if type(value) is int}
        if isinstance(counters_raw, dict)
        else {}
    )
    return seen, frontier, counters


def _normalize(link: LinkRef) -> tuple[str, str] | None:
    try:
        _, normalized = normalize_source_url(link.url)
    except AppError:
        return None
    return normalized, link.anchor_text


def _classify(
    *,
    seed_url: str,
    scope: DiscoveryMode,
    approved_domains: frozenset[str],
    allow_paths: tuple[str, ...],
    deny_paths: tuple[str, ...],
    link: LinkRef,
    depth: int,
) -> tuple[str, int] | None:
    """Return (normalized_url, score) when the link survives, else None."""
    normalized_pair = _normalize(link)
    if normalized_pair is None:
        return None
    normalized, anchor = normalized_pair
    if not scope_allows(
        seed_url=seed_url, target_url=normalized, scope=scope, approved_domains=approved_domains
    ):
        return None
    parsed = urlsplit(normalized)
    path_value = parsed.path or "/"
    if not path_allowed(path_value, allow_paths=allow_paths, deny_paths=deny_paths):
        return None
    target_host = parsed.hostname.rstrip(".").lower() if parsed.hostname else ""
    score = score_link(
        seed_url=seed_url,
        target_url=normalized,
        anchor_text=anchor,
        depth=depth,
        allow_paths=allow_paths,
        query=parsed.query,
        approved_host=bool(target_host) and target_host in approved_domains,
    )
    return normalized, score


def _collect_candidates(
    *,
    links: list[LinkRef],
    seed_url: str,
    scope: DiscoveryMode,
    approved_domains: frozenset[str],
    allow_paths: tuple[str, ...],
    deny_paths: tuple[str, ...],
    seen: set[str],
    min_score: int,
    child_depth: int,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Classify each link; returns surviving rows plus rejection counters."""
    rows: list[dict[str, Any]] = []
    counters = {"rejected_scope": 0, "rejected_score": 0, "duplicates": 0}
    for link in links:
        classified = _classify(
            seed_url=seed_url,
            scope=scope,
            approved_domains=approved_domains,
            allow_paths=allow_paths,
            deny_paths=deny_paths,
            link=link,
            depth=child_depth,
        )
        if classified is None:
            counters["rejected_scope"] += 1
            continue
        normalized, score = classified
        if score < min_score:
            counters["rejected_score"] += 1
            continue
        digest = url_hash(normalized)
        if digest in seen or any(row["url"] == normalized for row in rows):
            counters["duplicates"] += 1
            continue
        rows.append(
            {
                "url": normalized,
                "parent_url": seed_url,
                "depth": child_depth,
                "score": score,
                "hash": digest,
            }
        )
    return rows, counters


def _select_within_caps(
    rows: list[dict[str, Any]],
    *,
    existing_frontier: list[dict[str, Any]],
    accepted_total: int,
    frontier_cap: int,
    url_cap: int,
    depth_cap: int,
) -> list[dict[str, Any]]:
    """Deterministic cap selection: score desc, then depth, then URL ordinal."""
    rows.sort(key=lambda row: (-int(row["score"]), int(row["depth"]), str(row["url"])))
    accepted: list[dict[str, Any]] = []
    for row in rows:
        if int(row["depth"]) > depth_cap:
            continue
        if len(existing_frontier) + len(accepted) >= frontier_cap:
            break
        if accepted_total + len(accepted) >= url_cap:
            break
        accepted.append(
            {
                "url": row["url"],
                "parent_url": row["parent_url"],
                "depth": row["depth"],
                "score": row["score"],
            }
        )
    return accepted


def bounded_seen(seen: set[str]) -> list[str]:
    """Deterministic truncation of the persisted seen set."""
    if len(seen) > MAX_SEEN_HASHES:
        seen = set(sorted(seen)[:MAX_SEEN_HASHES])
    return sorted(seen)


def plan_discovery(
    *,
    seed_url: str,
    body: bytes,
    content_type: str,
    final_url: str,
    scope: DiscoveryMode,
    approved_domains: frozenset[str],
    allow_paths: tuple[str, ...],
    deny_paths: tuple[str, ...],
    checkpoint: dict[str, Any] | None,
    max_depth: int,
    max_frontier_size: int = MAX_FRONTIER_SIZE_DEFAULT,
    max_discovered_urls: int,
    min_score: int = MIN_SCORE_DEFAULT,
    base_depth: int = 0,
) -> DiscoveryPlan:
    """Plan discovered links for one accepted page and merge the checkpoint.

    ``base_depth`` is the depth of the page the links were found on (seed = 0), so
    crawl layers produce depth+1 children and the depth cap spans the whole crawl."""
    links = extract_links(body, content_type, final_url, limit=MAX_DISCOVERY_LINKS_PER_PAGE)
    seen, existing_frontier, counters = checkpoint_view(checkpoint)
    accepted_total = int(counters.get("accepted_total", 0))
    depth_cap = max(0, min(max_depth, 3))
    child_depth = max(0, base_depth) + 1
    frontier_cap = max(0, min(max_frontier_size, FRONTIER_HARD_CAP))
    counters = {**counters, "runs": int(counters.get("runs", 0)) + 1}
    rows, rejects = _collect_candidates(
        links=links,
        seed_url=seed_url,
        scope=scope,
        approved_domains=approved_domains,
        allow_paths=allow_paths,
        deny_paths=deny_paths,
        seen=seen,
        min_score=min_score,
        child_depth=child_depth,
    )
    accepted = _select_within_caps(
        rows,
        existing_frontier=existing_frontier,
        accepted_total=accepted_total,
        frontier_cap=frontier_cap,
        url_cap=max(0, max_discovered_urls),
        depth_cap=depth_cap,
    )
    for row in accepted:
        seen.add(url_hash(str(row["url"])))
    merged_frontier = (existing_frontier + accepted)[:frontier_cap]
    counters["accepted_total"] = accepted_total + len(accepted)
    summary = {
        "policy_version": DISCOVERY_POLICY_VERSION,
        "scope": scope.value,
        "links_found": len(links),
        "rejected_scope": rejects["rejected_scope"],
        "rejected_score": rejects["rejected_score"],
        "duplicates": rejects["duplicates"],
        "accepted": len(accepted),
        "frontier_size": len(merged_frontier),
        "depth_cap": depth_cap,
        "base_depth": max(0, base_depth),
        "truncated": len(existing_frontier) + len(rows) > len(merged_frontier),
    }
    checkpoint_next: dict[str, Any] = {
        "version": CHECKPOINT_VERSION,
        "seen": bounded_seen(seen),
        "frontier": merged_frontier,
        "counters": counters,
    }
    lease = crawl_lease(checkpoint)
    if lease is not None:
        checkpoint_next["crawl"] = lease
    return DiscoveryPlan(entries=accepted, summary=summary, checkpoint=checkpoint_next)


def crawl_lease(checkpoint: dict[str, Any] | None) -> dict[str, Any] | None:
    """Crawl lease held on the frontier, or None when absent/malformed."""
    if not isinstance(checkpoint, dict):
        return None
    lease = checkpoint.get("crawl")
    return dict(lease) if isinstance(lease, dict) else None


def lease_is_active(lease: dict[str, Any] | None, *, now: datetime) -> bool:
    """True while the lease is held and unexpired; malformed leases are never active."""
    if not lease:
        return False
    expires_raw = lease.get("expires_at")
    if not isinstance(expires_raw, str):
        return False
    try:
        expires_at = datetime.fromisoformat(expires_raw)
    except ValueError:
        return False
    return expires_at > now


def _document(
    checkpoint: dict[str, Any] | None,
    *,
    seen: set[str],
    frontier: list[dict[str, Any]],
    counters: dict[str, int],
) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "version": CHECKPOINT_VERSION,
        "seen": bounded_seen(seen),
        "frontier": frontier,
        "counters": counters,
    }
    lease = crawl_lease(checkpoint)
    if lease is not None:
        doc["crawl"] = lease
    return doc


def set_crawl_lease(
    checkpoint: dict[str, Any] | None, lease: dict[str, Any] | None
) -> dict[str, Any]:
    """Rebuild the checkpoint document with the lease replaced (None clears it)."""
    seen, frontier, counters = checkpoint_view(checkpoint)
    doc = _document(checkpoint, seen=seen, frontier=frontier, counters=counters)
    if lease is None:
        doc.pop("crawl", None)
    else:
        doc["crawl"] = dict(lease)
    return doc


def frontier_entry_hash(entry: dict[str, Any]) -> str:
    url = entry.get("url")
    return url_hash(url) if isinstance(url, str) else ""


def next_crawl_target(
    checkpoint: dict[str, Any] | None, *, skip_hashes: frozenset[str] = frozenset()
) -> dict[str, Any] | None:
    """Deterministic next frontier entry: score desc, depth asc, URL asc."""
    _, frontier, _ = checkpoint_view(checkpoint)
    candidates = [
        entry
        for entry in frontier
        if isinstance(entry, dict)
        and isinstance(entry.get("url"), str)
        and frontier_entry_hash(entry) not in skip_hashes
    ]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda entry: (
            -int(entry.get("score", 0)),
            int(entry.get("depth", 1)),
            str(entry["url"]),
        ),
    )


def crawl_begin_page(checkpoint: dict[str, Any] | None, *, entry_hash: str) -> dict[str, Any]:
    """Consume decision for one target: drop it from the frontier, mark it seen.

    The page hash enters ``seen`` *before* its links are planned, so a self-link can
    never re-enqueue the page it was found on."""
    seen, frontier, counters = checkpoint_view(checkpoint)
    seen.add(entry_hash)
    remaining = [entry for entry in frontier if frontier_entry_hash(entry) != entry_hash]
    return _document(checkpoint, seen=seen, frontier=remaining, counters=counters)


def crawl_finish_success(checkpoint: dict[str, Any] | None) -> dict[str, Any]:
    """Count one crawled page after its children were merged."""
    seen, frontier, counters = checkpoint_view(checkpoint)
    counters = {**counters, "crawled": int(counters.get("crawled", 0)) + 1}
    return _document(checkpoint, seen=seen, frontier=frontier, counters=counters)


def crawl_fail_page(
    checkpoint: dict[str, Any] | None, *, entry_hash: str, max_attempts: int
) -> tuple[dict[str, Any], bool]:
    """Record one failed fetch: the target keeps its frontier slot (retryable) until
    ``max_attempts`` consecutive failures retire it into the seen set."""
    seen, frontier, counters = checkpoint_view(checkpoint)
    kept: list[dict[str, Any]] = []
    abandoned = False
    for entry in frontier:
        if frontier_entry_hash(entry) != entry_hash:
            kept.append(entry)
            continue
        attempts = int(entry.get("attempts", DEFAULT_TARGET_ATTEMPTS)) + 1
        if attempts >= max_attempts:
            abandoned = True
            seen.add(entry_hash)
            counters = {**counters, "abandoned": int(counters.get("abandoned", 0)) + 1}
        else:
            kept.append({**entry, "attempts": attempts})
    counters = {**counters, "failed": int(counters.get("failed", 0)) + 1}
    return _document(checkpoint, seen=seen, frontier=kept, counters=counters), abandoned


def merge_entries(
    checkpoint: dict[str, Any] | None,
    entries: list[dict[str, Any]],
    *,
    frontier_cap: int,
) -> dict[str, Any]:
    """Merge planned entries into the document, deduping against seen and frontier."""
    seen, frontier, counters = checkpoint_view(checkpoint)
    merged = list(frontier)
    added = 0
    for row in entries:
        url = row.get("url")
        if not isinstance(url, str):
            continue
        digest = url_hash(url)
        if digest in seen or any(entry.get("url") == url for entry in merged):
            continue
        if len(merged) >= frontier_cap:
            break
        merged.append(
            {
                "url": url,
                "parent_url": row.get("parent_url"),
                "depth": int(row.get("depth", 1)),
                "score": int(row.get("score", 0)),
                "attempts": int(row.get("attempts", 0)),
            }
        )
        seen.add(digest)
        added += 1
    counters = {**counters, "accepted_total": int(counters.get("accepted_total", 0)) + added}
    return _document(checkpoint, seen=seen, frontier=merged, counters=counters)
