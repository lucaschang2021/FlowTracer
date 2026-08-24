from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import create_app
from app.services.readiness import ReadinessService

Probe = Callable[[], Awaitable[None]]


async def healthy_probe() -> None:
    return None


def failing_probe(message: str) -> Probe:
    async def probe() -> None:
        raise RuntimeError(message)

    return probe


async def slow_probe() -> None:
    await asyncio.sleep(0.1)


@asynccontextmanager
async def client_for(service: ReadinessService) -> AsyncIterator[AsyncClient]:
    app = create_app(Settings(), readiness_service=service)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_liveness_does_not_call_dependencies() -> None:
    calls = 0

    async def counted_probe() -> None:
        nonlocal calls
        calls += 1

    service = ReadinessService(counted_probe, counted_probe)
    async with client_for(service) as client:
        response = await client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "flowtracer-api",
        "version": "0.1.0",
    }
    assert calls == 0


@pytest.mark.asyncio
async def test_readiness_all_dependencies_healthy() -> None:
    service = ReadinessService(healthy_probe, healthy_probe)
    async with client_for(service) as client:
        response = await client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"database": "ok", "redis": "ok"},
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("database_probe", "redis_probe", "expected"),
    [
        (
            failing_probe("postgresql+asyncpg://user:secret@db/name"),
            healthy_probe,
            {"database": "unavailable", "redis": "ok"},
        ),
        (
            healthy_probe,
            failing_probe("redis://:secret@redis/0"),
            {"database": "ok", "redis": "unavailable"},
        ),
    ],
)
async def test_readiness_dependency_failure_is_safe(
    database_probe: Probe,
    redis_probe: Probe,
    expected: dict[str, str],
) -> None:
    service = ReadinessService(database_probe, redis_probe)
    async with client_for(service) as client:
        response = await client.get("/api/v1/health/ready")

    body = response.json()
    assert response.status_code == 503
    assert body["error"]["code"] == "service_not_ready"
    assert body["error"]["details"] == {"checks": expected}
    assert UUID(body["error"]["request_id"])
    assert "secret" not in response.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("database_probe", "redis_probe", "expected"),
    [
        (slow_probe, healthy_probe, {"database": "timeout", "redis": "ok"}),
        (healthy_probe, slow_probe, {"database": "ok", "redis": "timeout"}),
    ],
)
async def test_readiness_dependency_timeout(
    database_probe: Probe,
    redis_probe: Probe,
    expected: dict[str, str],
) -> None:
    service = ReadinessService(database_probe, redis_probe, timeout_seconds=0.01)
    async with client_for(service) as client:
        response = await client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json()["error"]["details"] == {"checks": expected}


@pytest.mark.asyncio
async def test_request_id_is_generated_and_returned() -> None:
    service = ReadinessService(healthy_probe, healthy_probe)
    async with client_for(service) as client:
        response = await client.get("/api/v1/health/live")

    assert UUID(response.headers["X-Request-ID"])


@pytest.mark.asyncio
async def test_valid_request_id_is_preserved() -> None:
    request_id = str(uuid4())
    service = ReadinessService(healthy_probe, healthy_probe)
    async with client_for(service) as client:
        response = await client.get(
            "/api/v1/health/live",
            headers={"X-Request-ID": request_id},
        )

    assert response.headers["X-Request-ID"] == request_id


@pytest.mark.asyncio
async def test_invalid_request_id_is_replaced() -> None:
    service = ReadinessService(healthy_probe, healthy_probe)
    async with client_for(service) as client:
        response = await client.get(
            "/api/v1/health/live",
            headers={"X-Request-ID": "not-a-uuid"},
        )

    assert response.headers["X-Request-ID"] != "not-a-uuid"
    assert UUID(response.headers["X-Request-ID"])


@pytest.mark.asyncio
async def test_unknown_route_uses_unified_error_format() -> None:
    service = ReadinessService(healthy_probe, healthy_probe)
    async with client_for(service) as client:
        response = await client.get("/api/v1/unknown")

    body = response.json()
    assert response.status_code == 404
    assert body["error"]["code"] == "not_found"
    assert set(body["error"]) == {"code", "message", "details", "request_id"}
    assert response.headers["X-Request-ID"] == body["error"]["request_id"]
