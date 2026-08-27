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
    "DATABASE_URL": "postgresql+asyncpg://flowtracer:flowtracer-local-only@localhost:5432/flowtracer_test",
    "TEST_DATABASE_URL": "postgresql+asyncpg://flowtracer:flowtracer-local-only@localhost:5432/flowtracer_test",
    "REDIS_URL": "redis://localhost:6379/15",
    "CELERY_BROKER_URL": "redis://localhost:6379/15",
    "CELERY_RESULT_BACKEND": "redis://localhost:6379/14",
    "JWT_SECRET": "unit-test-jwt-secret-at-least-32-bytes-long",
    "ACCESS_TOKEN_TTL_MINUTES": "15",
    "REFRESH_TOKEN_TTL_DAYS": "30",
    "JWT_ISSUER": "flowtracer-api",
    "JWT_AUDIENCE": "flowtracer-desktop",
    "AI_PROVIDER": "fake",
    "AI_MODEL": "flowtracer-fake-v1",
    "AI_INPUT_COST_PER_MILLION": "0",
    "AI_OUTPUT_COST_PER_MILLION": "0",
}

for key, value in TEST_ENV.items():
    os.environ.setdefault(key, value)


@pytest.fixture
def test_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for key, value in TEST_ENV.items():
        monkeypatch.setenv(key, value)
    yield
