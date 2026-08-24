from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

TEST_ENV = {
    "FLOWTRACER_ENV": "test",
    "FLOWTRACER_LOG_LEVEL": "INFO",
    "FLOWTRACER_APP_VERSION": "0.1.0",
    "FLOWTRACER_API_HOST": "127.0.0.1",
    "FLOWTRACER_API_PORT": "8000",
    "DATABASE_URL": "postgresql+asyncpg://flowtracer:unit-test@localhost:5432/flowtracer_test",
    "REDIS_URL": "redis://localhost:6379/15",
    "CELERY_BROKER_URL": "redis://localhost:6379/15",
    "CELERY_RESULT_BACKEND": "redis://localhost:6379/14",
}

for key, value in TEST_ENV.items():
    os.environ.setdefault(key, value)


@pytest.fixture
def test_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for key, value in TEST_ENV.items():
        monkeypatch.setenv(key, value)
    yield
