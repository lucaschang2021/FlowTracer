"""ACQ-1E Controlled Discovery v1 policy: scope boundaries, link scoring, hard caps.

Pure functions only: no network, filesystem, database, or clock access. Frozen by
ADR-035 / docs/61-ACQ1-WP5-DISCOVERY-CONTRACT.md. Every refusal is fail-closed: an
unparseable or out-of-scope target is denied, never widened.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from app.models.entities import DiscoveryMode

DISCOVERY_POLICY_VERSION = "discovery-v1"

MIN_SCORE_DEFAULT = 20
MAX_FRONTIER_SIZE_DEFAULT = 500
MAX_DISCOVERY_LINKS_PER_PAGE = 200

_DEPTH_PENALTY = 20
_SAME_PATH_BONUS = 30
_SAME_HOST_BONUS = 15
_APPROVED_HOST_BONUS = 10
_ALLOW_PATH_BONUS = 10
_ANCHOR_BONUS = 10
_TRACKING_PENALTY = 10

_ALLOWED_SCHEMES = frozenset({"http", "https"})
_ALLOWED_PORTS = frozenset({80, 443})
_TRACKING_PREFIXES = ("utm_",)


def host_of(url: str) -> str | None:
    """Lowercase host without trailing dot; None when the URL cannot be parsed."""
    try:
        parsed = urlsplit(url)
    except ValueError:
        return None
    hostname = parsed.hostname
    if hostname is None:
        return None
    return hostname.rstrip(".").lower()


def directory_prefix(path: str) -> str:
    """Directory portion of a path, always ending in '/' (root '/' for top-level)."""
    if not path or path == "/":
        return "/"
    trimmed = path.rstrip("/")
    head, _, _ = trimmed.rpartition("/")
    return f"{head}/" if head else "/"


def path_allowed(path: str, *, allow_paths: tuple[str, ...], deny_paths: tuple[str, ...]) -> bool:
    """Site policy path gate: deny first, then optional allow list."""
    if any(path.startswith(prefix) for prefix in deny_paths):
        return False
    if allow_paths and not any(path.startswith(prefix) for prefix in allow_paths):
        return False
    return True


def has_tracking_params(query: str) -> bool:
    if not query:
        return False
    for pair in query.split("&"):
        name = pair.split("=", 1)[0].strip().lower()
        if name.startswith(_TRACKING_PREFIXES) or name in {"fbclid", "gclid", "ref_src"}:
            return True
    return False


def _safe_parts(url: str) -> tuple[str, str, int, str, str] | None:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme not in _ALLOWED_SCHEMES
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or "@" in parsed.netloc
    ):
        return None
    hostname = parsed.hostname.rstrip(".").lower()
    effective_port = port if port is not None else (443 if parsed.scheme == "https" else 80)
    if effective_port not in _ALLOWED_PORTS:
        return None
    return parsed.scheme, hostname, effective_port, parsed.path or "/", parsed.query


def scope_allows(
    *,
    seed_url: str,
    target_url: str,
    scope: DiscoveryMode,
    approved_domains: frozenset[str],
) -> bool:
    """Four-scope boundary gate (docs/61 §2). Unknown shapes are denied."""
    seed = _safe_parts(seed_url)
    target = _safe_parts(target_url)
    if seed is None or target is None:
        return False
    seed_scheme, seed_host, seed_port, seed_path, _ = seed
    target_scheme, target_host, target_port, target_path, _ = target
    if scope == DiscoveryMode.SINGLE_PAGE:
        return (
            target_scheme == seed_scheme
            and target_host == seed_host
            and target_port == seed_port
            and target_path == seed_path
        )
    if scope == DiscoveryMode.SAME_PATH:
        return (
            target_scheme == seed_scheme
            and target_host == seed_host
            and target_port == seed_port
            and target_path.startswith(directory_prefix(seed_path))
        )
    if scope == DiscoveryMode.SAME_DOMAIN:
        return target_host == seed_host
    if scope == DiscoveryMode.APPROVED_DOMAINS:
        return target_host == seed_host or target_host in approved_domains
    return False


def score_link(
    *,
    seed_url: str,
    target_url: str,
    anchor_text: str,
    depth: int,
    allow_paths: tuple[str, ...],
    query: str,
    approved_host: bool = False,
) -> int:
    """Deterministic 0..100 score (docs/61 §4). Depth penalizes beyond the first hop:
    the seed page's direct links are layer 1; deeper layers are the ones that decay."""
    seed = _safe_parts(seed_url)
    target = _safe_parts(target_url)
    if seed is None or target is None:
        return 0
    seed_scheme, seed_host, seed_port, seed_path, _ = seed
    target_scheme, target_host, target_port, target_path, _ = target
    same_path = (
        target_scheme == seed_scheme
        and target_host == seed_host
        and target_port == seed_port
        and target_path.startswith(directory_prefix(seed_path))
    )
    if same_path:
        bonus = _SAME_PATH_BONUS
    elif target_host == seed_host:
        bonus = _SAME_HOST_BONUS
    elif approved_host:
        bonus = _APPROVED_HOST_BONUS
    else:
        bonus = 0
    score = -_DEPTH_PENALTY * max(0, max(0, depth) - 1) + bonus
    if allow_paths and any(target_path.startswith(prefix) for prefix in allow_paths):
        score += _ALLOW_PATH_BONUS
    if len(anchor_text.strip()) >= 4:
        score += _ANCHOR_BONUS
    if has_tracking_params(query):
        score -= _TRACKING_PENALTY
    return max(0, min(100, score))
