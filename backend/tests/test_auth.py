from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.main import create_app
from app.models.entities import RefreshToken, User
from app.services.readiness import ReadinessService

TABLES = (
    "notifications, ai_usage_records, document_chunks, bookmarks, analyses, documents, "
    "raw_items, radar_sources, collection_runs, sources, radars, refresh_tokens, users"
)


async def healthy_probe() -> None:
    return None


@pytest.fixture
async def database_engine() -> AsyncIterator[AsyncEngine]:
    database_url = os.environ["TEST_DATABASE_URL"]
    assert "_test" in database_url.rsplit("/", maxsplit=1)[-1]
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    yield engine
    await engine.dispose()


@pytest.fixture
async def auth_client(database_engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    app = create_app(
        Settings(),
        readiness_service=ReadinessService(healthy_probe, healthy_probe),
    )
    app.state.session_factory = async_sessionmaker(database_engine, expire_on_commit=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def register(client: AsyncClient, email: str = "Person@EXAMPLE.com") -> dict[str, Any]:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "unicode-password-安全",
            "display_name": "Person",
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.asyncio
async def test_register_normalizes_email_and_never_exposes_sensitive_fields(
    auth_client: AsyncClient,
) -> None:
    body = await register(auth_client)
    assert body["user"]["email"] == "Person@example.com"
    assert body["tokens"]["token_type"] == "bearer"
    assert body["tokens"]["expires_in"] == 900
    assert "password_hash" not in auth_client.cookies
    assert "password_hash" not in str(body)
    assert "deleted_at" not in str(body)


@pytest.mark.asyncio
async def test_duplicate_and_concurrent_registration_use_unique_constraint(
    auth_client: AsyncClient,
) -> None:
    await register(auth_client, "duplicate@example.com")
    duplicate = await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "duplicate@example.com",
            "password": "another-password",
            "display_name": "Duplicate",
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "email_already_registered"

    async def attempt() -> int:
        response = await auth_client.post(
            "/api/v1/auth/register",
            json={
                "email": "race@example.com",
                "password": "race-password-123",
                "display_name": "Race",
            },
        )
        return response.status_code

    assert sorted(await asyncio.gather(attempt(), attempt())) == [201, 409]


@pytest.mark.asyncio
async def test_login_success_and_invalid_credentials_are_unified(
    auth_client: AsyncClient,
) -> None:
    await register(auth_client, "login@example.com")
    success = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "unicode-password-安全"},
    )
    assert success.status_code == 200

    for email, password in [
        ("missing@example.com", "unicode-password-安全"),
        ("login@example.com", "wrong-password-value"),
    ]:
        response = await auth_client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "invalid_credentials"


@pytest.mark.asyncio
async def test_refresh_rotates_once_and_reuse_is_rejected(auth_client: AsyncClient) -> None:
    body = await register(auth_client, "refresh@example.com")
    old_token = body["tokens"]["refresh_token"]
    rotated = await auth_client.post("/api/v1/auth/refresh", json={"refresh_token": old_token})
    assert rotated.status_code == 200
    assert rotated.json()["tokens"]["refresh_token"] != old_token
    reused = await auth_client.post("/api/v1/auth/refresh", json={"refresh_token": old_token})
    assert reused.status_code == 401
    assert reused.json()["error"]["code"] == "invalid_refresh_token"


@pytest.mark.asyncio
async def test_concurrent_refresh_has_at_most_one_success(auth_client: AsyncClient) -> None:
    old_token = (await register(auth_client, "refresh-race@example.com"))["tokens"]["refresh_token"]

    async def attempt() -> int:
        response = await auth_client.post("/api/v1/auth/refresh", json={"refresh_token": old_token})
        return response.status_code

    assert sorted(await asyncio.gather(attempt(), attempt())) == [200, 401]


@pytest.mark.asyncio
async def test_expired_revoked_and_malformed_refresh_are_unified(
    auth_client: AsyncClient,
    database_engine: AsyncEngine,
) -> None:
    token = (await register(auth_client, "expired@example.com"))["tokens"]["refresh_token"]
    token_id = token.split(".", maxsplit=1)[0]
    factory = async_sessionmaker(database_engine, expire_on_commit=False)
    async with factory() as session:
        record = await session.get(RefreshToken, token_id)
        assert record is not None
        record.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()
    for value in (token, "malformed"):
        response = await auth_client.post("/api/v1/auth/refresh", json={"refresh_token": value})
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "invalid_refresh_token"


@pytest.mark.asyncio
async def test_logout_is_idempotent(auth_client: AsyncClient) -> None:
    token = (await register(auth_client, "logout@example.com"))["tokens"]["refresh_token"]
    for value in (token, token, "unknown.invalid"):
        response = await auth_client.post("/api/v1/auth/logout", json={"refresh_token": value})
        assert response.status_code == 204
        assert not response.content


@pytest.mark.asyncio
async def test_me_patch_empty_patch_and_auth_boundaries(auth_client: AsyncClient) -> None:
    body = await register(auth_client, "me@example.com")
    headers = {"Authorization": f"Bearer {body['tokens']['access_token']}"}
    me = await auth_client.get("/api/v1/users/me", headers=headers)
    assert me.status_code == 200
    previous_updated_at = datetime.fromisoformat(me.json()["updated_at"])
    patched = await auth_client.patch(
        "/api/v1/users/me",
        headers=headers,
        json={"display_name": "Updated", "profile": {"theme": "dark"}},
    )
    assert patched.status_code == 200
    assert patched.json()["profile"] == {"theme": "dark"}
    assert datetime.fromisoformat(patched.json()["updated_at"]) > previous_updated_at
    empty = await auth_client.patch("/api/v1/users/me", headers=headers, json={})
    assert empty.status_code == 422
    assert empty.json()["error"]["code"] == "invalid_request"
    for invalid_headers in ({}, {"Authorization": "Bearer invalid"}):
        response = await auth_client.get("/api/v1/users/me", headers=invalid_headers)
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"
        assert response.json()["error"]["code"] == "invalid_access_token"


@pytest.mark.asyncio
@pytest.mark.parametrize("soft_delete", [False, True])
async def test_inactive_or_deleted_user_is_rejected(
    auth_client: AsyncClient,
    database_engine: AsyncEngine,
    soft_delete: bool,
) -> None:
    body = await register(auth_client, f"disabled-{soft_delete}@example.com")
    factory = async_sessionmaker(database_engine, expire_on_commit=False)
    async with factory() as session:
        user = await session.get(User, body["user"]["id"])
        assert user is not None
        if soft_delete:
            user.deleted_at = datetime.now(UTC)
        else:
            user.is_active = False
        await session.commit()
    headers = {"Authorization": f"Bearer {body['tokens']['access_token']}"}
    assert (await auth_client.get("/api/v1/users/me", headers=headers)).status_code == 401
    refresh = await auth_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": body["tokens"]["refresh_token"]}
    )
    assert refresh.status_code == 401


@pytest.mark.asyncio
async def test_auth_responses_do_not_echo_secrets(auth_client: AsyncClient) -> None:
    password = "do-not-echo-password"
    response = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": password},
        headers={"Authorization": "Bearer do-not-echo-token"},
    )
    assert response.status_code == 401
    assert password not in response.text
    assert "do-not-echo-token" not in response.text


def test_openapi_contains_auth_user_bearer_and_error_contract() -> None:
    app = create_app(Settings(), readiness_service=ReadinessService(healthy_probe, healthy_probe))
    schema = app.openapi()
    assert "HTTPBearer" in schema["components"]["securitySchemes"]
    for path in (
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/logout",
        "/api/v1/users/me",
    ):
        assert path in schema["paths"]
    assert "RegisterRequest" in schema["components"]["schemas"]
    assert "UserResponse" in schema["components"]["schemas"]
    assert "ErrorEnvelope" in schema["components"]["schemas"]
    assert "401" in schema["paths"]["/api/v1/users/me"]["get"]["responses"]
