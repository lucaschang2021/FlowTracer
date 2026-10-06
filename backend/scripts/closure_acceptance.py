"""Offline closure acceptance runner (docs/71 §Phase 5.3, docs/77 §5).

Reproduces the *complete* provider-side gate evidence on the exact candidate
commit so an independent reviewer can execute it themselves:

- records the candidate commit hash, the working-tree cleanliness, and the
  migration head;
- runs the full pytest suite with the coverage floor, then the static gates
  (ruff check, ruff format, mypy strict, architecture gate, Alembic drift,
  frozen OpenAPI snapshot, secret scan);
- writes a JSON report (default ``closure-acceptance-<commit8>.json`` next to the
  console log) and exits non-zero unless every executed check passed.

Prerequisites (same as the documented test environment): PostgreSQL and Redis
test containers reachable via ``TEST_DATABASE_URL`` / ``REDIS_URL`` and the
other variables from the handoff environment file. No public network access is
performed by the suite.

Usage (from ``backend/``):

    python scripts/closure_acceptance.py                 # full evidence
    python scripts/closure_acceptance.py --no-tests      # static gates only
    python scripts/closure_acceptance.py --report out.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
COVERAGE_FLOOR = "87.61"


@dataclass(slots=True)
class Check:
    name: str
    command: list[str]
    passed: bool
    seconds: float
    tail: str


def _run(name: str, command: list[str], *, timeout: int = 3600) -> Check:
    print(f"== {name}: {' '.join(command)}")
    started = time.monotonic()
    completed = subprocess.run(  # noqa: S603 - fixed local commands
        command,
        cwd=BACKEND,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    seconds = time.monotonic() - started
    output = (completed.stdout or "") + (completed.stderr or "")
    tail = "\n".join(output.strip().splitlines()[-12:])
    passed = completed.returncode == 0
    print(f"   {'PASS' if passed else 'FAIL'} in {seconds:.1f}s")
    if not passed:
        print(tail)
    return Check(name, command, passed, seconds, tail)


def _git(*args: str) -> str:
    completed = subprocess.run(  # noqa: S603 - fixed local command
        ["git", *args],  # noqa: S607 - resolved via PATH on the delivery machine
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="ACQ-1 closure acceptance runner")
    parser.add_argument("--no-tests", action="store_true", help="skip the full pytest suite")
    parser.add_argument("--report", type=Path, default=None)
    options = parser.parse_args()

    commit = _git("rev-parse", "HEAD")
    short = commit[:8] if commit else "unknown"
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    dirty = _git("status", "--porcelain")

    checks: list[Check] = []
    if not options.no_tests:
        checks.append(
            _run(
                "pytest-full",
                [sys.executable, "-m", "pytest", f"--cov-fail-under={COVERAGE_FLOOR}", "-q"],
            )
        )
    checks.append(_run("ruff-check", [sys.executable, "-m", "ruff", "check", "."]))
    checks.append(_run("ruff-format", [sys.executable, "-m", "ruff", "format", "--check", "."]))
    checks.append(_run("mypy", [sys.executable, "-m", "mypy", "app"]))
    checks.append(_run("architecture-gate", [sys.executable, "-m", "architecture_gate", "check"]))
    checks.append(_run("alembic-check", [sys.executable, "-m", "alembic", "check"]))
    checks.append(_run("openapi-freeze", [sys.executable, "scripts/export_openapi.py", "--check"]))
    checks.append(_run("secret-scan", [sys.executable, "scripts/secret_scan.py"]))

    report = {
        "candidate_commit": commit,
        "branch": branch,
        "working_tree_clean": dirty == "",
        "uncommitted_entries": dirty.splitlines(),
        "checks": [
            {
                "name": check.name,
                "command": check.command,
                "passed": check.passed,
                "seconds": round(check.seconds, 2),
                "tail": check.tail,
            }
            for check in checks
        ],
        "all_passed": all(check.passed for check in checks),
    }
    report_path = options.report or BACKEND / f"closure-acceptance-{short}.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"\ncandidate commit: {short} ({branch}), clean={report['working_tree_clean']}")
    print(f"report written to: {report_path}")
    print("ALL CHECKS PASSED" if report["all_passed"] else "CHECKS FAILED")
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
