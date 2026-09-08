from __future__ import annotations

import importlib.metadata
import os
import platform
import subprocess
import sys
from pathlib import Path

EXPECTED_PACKAGES = {
    "patchright": "1.62.3",
    "playwright": "1.62.0",
    "scrapling": "0.4.15",
}
EXPECTED_BROWSER_ROOT = Path("/opt/browser-r1")
EXPECTED_BROWSER_VERSION = "Google Chrome for Testing 151.0.7922.34"
EXPECTED_PYTHON = "3.13.15"


def validate_runtime() -> list[str]:
    mismatches: list[str] = []
    if platform.python_version() != EXPECTED_PYTHON:
        mismatches.append("python")
    if os.environ.get("PLAYWRIGHT_BROWSERS_PATH") != str(EXPECTED_BROWSER_ROOT):
        mismatches.append("browser_path")
    for package, expected in EXPECTED_PACKAGES.items():
        if importlib.metadata.version(package) != expected:
            mismatches.append(f"package:{package}")

    executable = (
        EXPECTED_BROWSER_ROOT
        / "chromium_headless_shell-1234"
        / "chrome-headless-shell-linux64"
        / "chrome-headless-shell"
    )
    if not executable.is_file():
        mismatches.append("browser_executable")
    else:
        actual = subprocess.run(  # noqa: S603 - executable path is a frozen constant
            [str(executable), "--version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
        if actual != EXPECTED_BROWSER_VERSION:
            mismatches.append("browser_version")
    return mismatches


def main() -> int:
    try:
        mismatches = validate_runtime()
    except Exception:
        print("R1_RUNTIME_MISMATCH: validation_error", file=sys.stderr)
        return 78
    if mismatches:
        print(f"R1_RUNTIME_MISMATCH: {','.join(mismatches)}", file=sys.stderr)
        return 78
    if len(sys.argv) < 2:
        print("R1_RUNTIME_MISMATCH: missing_command", file=sys.stderr)
        return 78
    os.execvp(sys.argv[1], sys.argv[1:])  # noqa: S606 - container entrypoint contract
    return 70


if __name__ == "__main__":
    raise SystemExit(main())
