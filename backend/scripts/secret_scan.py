"""WP-8 secret scan over git-tracked files (docs/25 §1, docs/67 §1).

Scans every tracked text file for high-signal secret shapes: private key blocks,
cloud/registry tokens, code-hosting and chat tokens, provider API keys, and
connection strings whose password is not a known local/CI placeholder. Prints one
JSON line per finding and exits non-zero when any finding exists.

Usage: python scripts/secret_scan.py
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND.parent
MAX_FILE_BYTES = 1_048_576

PLACEHOLDER_MARKERS = ("test", "placeholder", "example", "synthetic", "fake", "local-only")
PASSWORD_MARKERS = (
    "secret",
    "pass",
    "example",
    "placeholder",
    "synthetic",
    "local",
    "changeme",
    "test",
)
FAKE_HOSTS = re.compile(
    r"^(localhost|127\.0\.0\.1|db|postgres|.*\.(test|invalid|example)|example\.com)$"
)

PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private_key_block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github_token", re.compile(r"\b(ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{22,})\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("stripe_secret_key", re.compile(r"\bsk_live_[0-9a-zA-Z]{24,}\b")),
    ("openai_style_key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}\b")),
    (
        "jwt_literal",
        re.compile(r"""(?i)\bjwt_secret\s*[:=]\s*["']([^"']{32,})["']"""),
    ),
)
CREDENTIALED_URL = re.compile(r"://([^/\s:@'\"]{1,64}):([^/\s:@'\"]{3,64})@([^/\s:@'\"]+)")


def _tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],  # noqa: S607 - git comes from PATH by design
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return sorted(line for line in result.stdout.splitlines() if line)


def _scan_file(path: Path, relpath: str) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    try:
        raw = path.read_bytes()
    except OSError:
        return findings
    if len(raw) > MAX_FILE_BYTES or b"\x00" in raw[:4096]:
        return findings
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return findings
    for number, line in enumerate(text.splitlines(), start=1):
        for rule, pattern in PATTERNS:
            match = pattern.search(line)
            if match is None:
                continue
            if rule == "jwt_literal" and any(
                marker in match.group(1).lower() for marker in PLACEHOLDER_MARKERS
            ):
                continue
            findings.append({"rule": rule, "file": relpath, "line": number})
        credential = CREDENTIALED_URL.search(line)
        if credential is not None:
            password = credential.group(2).lower()
            host = credential.group(3).lower()
            looks_placeholder = any(marker in password for marker in PASSWORD_MARKERS)
            if not looks_placeholder and FAKE_HOSTS.match(host) is None:
                findings.append({"rule": "credentialed_url", "file": relpath, "line": number})
    return findings


def main() -> None:
    findings: list[dict[str, object]] = []
    for relpath in _tracked_files():
        findings.extend(_scan_file(REPO_ROOT / relpath, relpath))
    for finding in findings:
        print(json.dumps(finding, ensure_ascii=False))
    if findings:
        print(f"SECRET SCAN FAILED: {len(findings)} finding(s)")
        raise SystemExit(1)
    print("SECRET SCAN CLEAN")


if __name__ == "__main__":
    main()
