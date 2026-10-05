"""WP-8 repeatable fresh-startup verification (docs/25 §1/§16, docs/67 §1).

Creates a uniquely named isolated ``*_test`` database on the configured server,
runs the empty-database cycle (upgrade head -> alembic check -> downgrade base ->
re-upgrade), boots the API against that database on a loopback port, checks
liveness, compares the live OpenAPI document with the frozen snapshot, then drops
the database. Never touches a database whose name does not contain ``_test``.

Usage: python scripts/verify_fresh_startup.py
Exit code 0 means every step passed; any failure prints a JSON report and exits 1.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from urllib.parse import quote

import asyncpg  # type: ignore[import-untyped]
from sqlalchemy.engine import make_url

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

from export_openapi import SCHEMA_ENVIRONMENT, serialize_openapi  # noqa: E402

OPENAPI_PATH = BACKEND / "openapi" / "flowtracer-alpha-v0.1.json"
BOOT_TIMEOUT_SECONDS = 45.0
POLL_INTERVAL_SECONDS = 0.5


def _report(step: str, status: str, **extra: object) -> None:
    print(json.dumps({"step": step, "status": status, **extra}, ensure_ascii=False))


def _fail(step: str, message: str) -> None:
    _report(step, "failed", message=message)
    raise SystemExit(1)


def _run_alembic(database_url: str, *args: str) -> subprocess.CompletedProcess[str]:
    environment = {**os.environ, **SCHEMA_ENVIRONMENT, "DATABASE_URL": database_url}
    environment["TEST_DATABASE_URL"] = database_url
    result = subprocess.run(  # noqa: S603 - fixed interpreter and local module
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND,
        env=environment,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if result.returncode != 0:
        _fail("alembic", f"{' '.join(args)} failed: {result.stderr.strip()[-400:]}")
    return result


async def _create_database(maintenance_dsn: str, database: str) -> None:
    connection = await asyncpg.connect(maintenance_dsn)
    try:
        await connection.execute(f'CREATE DATABASE "{database}"')
    finally:
        await connection.close()


async def _drop_database(maintenance_dsn: str, database: str) -> None:
    connection = await asyncpg.connect(maintenance_dsn)
    try:
        await connection.execute(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)')
    finally:
        await connection.close()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _boot_and_check_liveness(database_url: str, port: int) -> None:
    environment = {**os.environ, **SCHEMA_ENVIRONMENT, "DATABASE_URL": database_url}
    environment["TEST_DATABASE_URL"] = database_url
    process = subprocess.Popen(  # noqa: S603 - fixed interpreter and local module
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=BACKEND,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    url = f"http://127.0.0.1:{port}/api/v1/health/live"
    deadline = time.monotonic() + BOOT_TIMEOUT_SECONDS
    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                _fail("api_boot", "uvicorn exited before serving liveness")
            try:
                with urllib.request.urlopen(url, timeout=2.0) as response:
                    if response.status == 200:
                        _report("api_boot", "passed", port=port)
                        return
            except (urllib.error.URLError, ConnectionError, TimeoutError):
                time.sleep(POLL_INTERVAL_SECONDS)
        _fail("api_boot", "liveness did not become ready before the deadline")
    finally:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:  # pragma: no cover - defensive
            process.kill()
            process.wait(timeout=15)


def _verify_openapi_snapshot(database_url: str) -> None:
    os.environ.update(
        {**SCHEMA_ENVIRONMENT, "DATABASE_URL": database_url, "TEST_DATABASE_URL": database_url}
    )
    from export_openapi import build_openapi_document

    rendered = serialize_openapi(build_openapi_document())
    expected = OPENAPI_PATH.read_text(encoding="utf-8")
    if rendered != expected:
        _fail("openapi_snapshot", "live OpenAPI differs from the frozen snapshot")
    _report("openapi_snapshot", "passed")


def main() -> None:
    source = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if source is None:
        _fail("configuration", "TEST_DATABASE_URL or DATABASE_URL must be set")
    url = make_url(source)
    if url.drivername != "postgresql+asyncpg" or not url.host or not url.username:
        _fail("configuration", "expected a postgresql+asyncpg URL with host and user")
    credentials = f"{url.username}:{quote(url.password or '')}"
    endpoint = f"{url.host}:{url.port or 5432}"
    maintenance = f"postgresql://{credentials}@{endpoint}/{url.database}"
    if "_test" not in (url.database or ""):
        _fail("configuration", "refusing to run: database name must contain _test")
    database = f"flowtracer_wp8_{uuid.uuid4().hex[:8]}_test"
    temp_url = f"postgresql+asyncpg://{credentials}@{endpoint}/{database}"
    try:
        asyncio.run(_create_database(maintenance, database))
        _report("create_database", "passed", database=database)
        _run_alembic(temp_url, "upgrade", "head")
        _report("upgrade_head", "passed")
        check = _run_alembic(temp_url, "check")
        if "No new upgrade operations detected" not in (check.stdout + check.stderr):
            _fail("alembic_check", "schema drift detected on the fresh database")
        _report("alembic_check", "passed")
        _run_alembic(temp_url, "downgrade", "base")
        _report("downgrade_base", "passed")
        _run_alembic(temp_url, "upgrade", "head")
        _report("re_upgrade_head", "passed")
        _boot_and_check_liveness(temp_url, _free_port())
        _verify_openapi_snapshot(temp_url)
    finally:
        asyncio.run(_drop_database(maintenance, database))
        _report("drop_database", "passed", database=database)
    _report("verify_fresh_startup", "passed")
    print("FRESH STARTUP VERIFIED")


if __name__ == "__main__":
    main()
