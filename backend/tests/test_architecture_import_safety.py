from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

from conftest import TEST_ENV

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_required_modules_import_without_external_side_effects() -> None:
    script = textwrap.dedent(
        """
        import builtins
        import importlib
        import pathlib
        import socket
        import sys

        sys.dont_write_bytecode = True

        def blocked(*args, **kwargs):
            raise AssertionError("external operation attempted during import")

        async def blocked_async(*args, **kwargs):
            blocked()

        original_open = builtins.open
        def guarded_open(file, mode="r", *args, **kwargs):
            if any(flag in mode for flag in ("w", "a", "x", "+")):
                blocked()
            return original_open(file, mode, *args, **kwargs)

        builtins.open = guarded_open
        pathlib.Path.write_bytes = blocked
        pathlib.Path.write_text = blocked
        socket.create_connection = blocked
        socket.socket.connect = blocked

        import httpx
        import redis.asyncio
        import sqlalchemy.ext.asyncio
        from celery import Celery, Task

        httpx.AsyncClient.request = blocked_async
        httpx.AsyncClient.send = blocked_async
        httpx.AsyncClient.stream = blocked
        redis.asyncio.Redis.from_url = blocked
        redis.asyncio.Redis.ping = blocked_async
        redis.asyncio.Redis.publish = blocked_async
        redis.asyncio.Redis.subscribe = blocked_async
        sqlalchemy.ext.asyncio.create_async_engine = blocked
        Celery.send_task = blocked
        Task.apply_async = blocked
        Task.delay = blocked

        for target in (
            "app.main",
            "app.tasks.celery_app",
            "app.providers.analysis",
            "app.providers.embedding",
            "app.services.acquisition",
            "app.services.intelligence",
            "app.services.memory",
        ):
            importlib.import_module(target)
        """
    )
    environment = {**os.environ, **TEST_ENV, "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script],
        cwd=BACKEND_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
