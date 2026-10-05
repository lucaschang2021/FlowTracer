"""ACQ-1E frontier planning and checkpoint merge (pure; docs/61 §3/§6/§7).

Given one fetched page, plan the discovered links that survive scope, site policy,
scoring, and hard caps, then merge them into the source's persistent checkpoint.
This increment records frontier state only: no request is issued to discovered URLs
(crawl execution is a later WP-5 increment gated by its own admission).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
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
    host_of,
    path_allowed,
    scope_allows,
    score_link,
)
from app.services.url_normalization import normalize_source_url

CHECKPOINT_VERSION = 1
MAX_SEEN_HASHES = 2000
FRONTIER_HARD_CAP = 500


@dataclass(frozen=True, slots=True)
class DiscoveryPlan:
    entries: list[dict[str, Any]]
    summary: dict[str, Any]
    checkpoint: dict[str, Any]


def _url_hash(url: str) -> str:
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
        depth=1,
        allow_paths=allow_paths,
        query=parsed.query,
        approved_host=bool(target_host) and target_host in approved_domains,
    )
    return normalized, score


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
) -> DiscoveryPlan:
    """Plan discovered links for one accepted page and merge the checkpoint."""
    links = extract_links(body, content_type, final_url, limit=MAX_DISCOVERY_LINKS_PER_PAGE)
    seen, existing_frontier, counters = checkpoint_view(checkpoint)
    accepted_total = int(counters.get("accepted_total", 0))
    depth_cap = max(0, min(max_depth, 3))
    frontier_cap = max(0, min(max_frontier_size, FRONTIER_HARD_CAP))
    url_cap = max(0, max_discovered_urls)
    counters = {**counters, "runs": int(counters.get("runs", 0)) + 1}

    candidate_rows: list[dict[str, Any]] = []
    rejected_scope = rejected_score = duplicates = 0
    for link in links:
        classified = _classify(
            seed_url=seed_url,
            scope=scope,
            approved_domains=approved_domains,
            allow_paths=allow_paths,
            deny_paths=deny_paths,
            link=link,
        )
        if classified is None:
            rejected_scope += 1
            continue
        normalized, score = classified
        if score < min_score:
            rejected_score += 1
            continue
        digest = _url_hash(normalized)
        if digest in seen or any(row["url"] == normalized for row in candidate_rows):
            duplicates += 1
            continue
        candidate_rows.append(
            {"url": normalized, "parent_url": seed_url, "depth": 1, "score": score, "hash": digest}
        )

    if depth_cap < 1:
        candidate_rows = []
    candidate_rows.sort(key=lambda row: (-int(row["score"]), int(row["depth"]), str(row["url"])))
    accepted: list[dict[str, Any]] = []
    for row in candidate_rows:
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

    for row in accepted:
        seen.add(_url_hash(str(row["url"])))
    if len(seen) > MAX_SEEN_HASHES:
        seen = set(sorted(seen)[:MAX_SEEN_HASHES])
    merged_frontier = (existing_frontier + accepted)[:frontier_cap]
    counters["accepted_total"] = accepted_total + len(accepted)
    summary = {
        "policy_version": DISCOVERY_POLICY_VERSION,
        "scope": scope.value,
        "links_found": len(links),
        "rejected_scope": rejected_scope,
        "rejected_score": rejected_score,
        "duplicates": duplicates,
        "accepted": len(accepted),
        "frontier_size": len(merged_frontier),
        "depth_cap": depth_cap,
        "truncated": len(existing_frontier) + len(candidate_rows) > len(merged_frontier),
    }
    checkpoint_next = {
        "version": CHECKPOINT_VERSION,
        "seen": sorted(seen),
        "frontier": merged_frontier,
        "counters": counters,
    }
    return DiscoveryPlan(entries=accepted, summary=summary, checkpoint=checkpoint_next)


def seed_host_of(seed_url: str) -> str | None:
    return host_of(seed_url)
