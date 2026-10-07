"""Offline closure acceptance runner (docs/71 §Phase 5.3, docs/77 §5).

Reproduces the *complete* provider-side gate evidence on the exact candidate
commit so an independent reviewer can execute it themselves:

- records the candidate commit hash and working-tree cleanliness;
- runs the full pytest suite with the coverage floor, then the static gates
  (ruff check, ruff format, mypy strict, architecture gate, Alembic drift,
  frozen OpenAPI snapshot, secret scan);
- writes a JSON report (default ``closure-acceptance-<commit8>.json`` next to the
  console log). The report distinguishes a full run from ``--no-tests`` static-only
  evidence; ``all_passed`` / ``full_acceptance_passed`` can only be true when the
  full pytest suite was actually executed and every check passed. The process exits
  non-zero when any executed check failed.

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


def _build_report(
    *,
    commit: str,
    branch: str,
    dirty: str,
    checks: list[Check],
    full_run: bool,
) -> dict[str, object]:
    pytest_check = next((check for check in checks if check.name == "pytest-full"), None)
    tests_executed = pytest_check is not None
    tests_passed = pytest_check.passed if pytest_check is not None else None
    executed_checks_passed = all(check.passed for check in checks)
    commit_valid = len(commit) == 40 and all(
        character in "0123456789abcdef" for character in commit
    )
    working_tree_clean = dirty == ""
    full_acceptance_passed = (
        full_run
        and tests_executed
        and executed_checks_passed
        and commit_valid
        and working_tree_clean
    )

    return {
        "schema_version": 2,
        "acceptance_mode": "full" if full_run else "static-only",
        "candidate_commit": commit,
        "branch": branch,
        "working_tree_clean": working_tree_clean,
        "uncommitted_entries": dirty.splitlines(),
        "tests": {
            "required_for_full_acceptance": True,
            "executed": tests_executed,
            "passed": tests_passed,
        },
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
        "executed_checks_passed": executed_checks_passed,
        "full_acceptance_passed": full_acceptance_passed,
        # Compatibility field: this now means complete acceptance, never static-only success.
        "all_passed": full_acceptance_passed,
    }


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

    report = _build_report(
        commit=commit,
        branch=branch,
        dirty=dirty,
        checks=checks,
        full_run=not options.no_tests,
    )
    report_path = options.report or BACKEND / f"closure-acceptance-{short}.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"\ncandidate commit: {short} ({branch}), clean={report['working_tree_clean']}")
    print(f"report written to: {report_path}")
    if report["full_acceptance_passed"]:
        print("FULL ACCEPTANCE CHECKS PASSED")
    elif report["acceptance_mode"] == "static-only" and report["executed_checks_passed"]:
        print("STATIC CHECKS PASSED; FULL ACCEPTANCE NOT RUN")
    else:
        print("CHECKS FAILED")
    return 0 if report["executed_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
