from __future__ import annotations

from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import create_app
from app.services.readiness import ReadinessService


async def healthy_probe() -> None:
    return None


@pytest.mark.asyncio
async def test_validation_error_uses_safe_unified_format() -> None:
    app = create_app(
        Settings(),
        readiness_service=ReadinessService(healthy_probe, healthy_probe),
    )

    @app.get("/api/v1/test/number/{number}")
    async def typed_path(number: int) -> dict[str, int]:
        return {"number": number}

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/test/number/not-an-integer")

    body = response.json()
    assert response.status_code == 422
    assert body["error"]["code"] == "invalid_request"
    assert body["error"]["details"]["errors"][0]["location"][-1] == "number"
    assert "input" not in body["error"]["details"]["errors"][0]
    assert UUID(body["error"]["request_id"])


@pytest.mark.asyncio
async def test_unhandled_error_is_safe_and_keeps_request_id() -> None:
    app = create_app(
        Settings(),
        readiness_service=ReadinessService(healthy_probe, healthy_probe),
    )

    @app.get("/api/v1/test/explode")
    async def explode() -> None:
        raise RuntimeError("database password=must-not-leak")

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/test/explode")

    body = response.json()
    assert response.status_code == 500
    assert body["error"]["code"] == "internal_error"
    assert "must-not-leak" not in response.text
    assert response.headers["X-Request-ID"] == body["error"]["request_id"]
    assert UUID(body["error"]["request_id"])
