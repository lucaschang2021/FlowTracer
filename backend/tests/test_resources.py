from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.main import create_app
from app.models.entities import Radar, RadarSource, ResourceStatus, Source
from app.schemas.resources import RadarCreate, SourceCreate
from app.services.readiness import ReadinessService

TABLES = (
    "notifications, ai_usage_records, document_chunks, bookmarks, analyses, documents, "
    "raw_items, radar_sources, collection_runs, sources, radars, refresh_tokens, users"
)


async def healthy_probe() -> None:
    return None


@pytest.fixture
async def resource_engine() -> AsyncIterator[AsyncEngine]:
    database_url = os.environ["TEST_DATABASE_URL"]
    assert "_test" in database_url.rsplit("/", maxsplit=1)[-1]
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    yield engine
    await engine.dispose()


@pytest.fixture
async def resource_client(resource_engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    app = create_app(Settings(), readiness_service=ReadinessService(healthy_probe, healthy_probe))
    app.state.session_factory = async_sessionmaker(resource_engine, expire_on_commit=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def headers_for(client: AsyncClient, email: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "resource-password-安全", "display_name": "Owner"},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['tokens']['access_token']}"}


def radar_payload(name: str = "Radar One") -> dict[str, Any]:
    return {
        "name": name,
        "description": "  description  ",
        "goal": "  Track important changes  ",
        "radar_type": "technology",
        "categories": [" AI ", "ai", "Security"],
        "keywords": ["LLM", " llm ", "Postgres"],
        "notification_threshold": 80,
    }


def source_payload(
    name: str = "Source One", url: str = "HTTPS://Example.COM:443/feed#top"
) -> dict[str, Any]:
    return {
        "name": name,
        "source_type": "rss",
        "url": url,
        "poll_interval_minutes": 30,
        "config": {"label": "public"},
    }


async def create_radar(
    client: AsyncClient, headers: dict[str, str], name: str = "Radar One"
) -> Response:
    response = await client.post("/api/v1/radars", headers=headers, json=radar_payload(name))
    assert response.status_code == 201
    return response


async def create_source(
    client: AsyncClient,
    headers: dict[str, str],
    name: str = "Source One",
    url: str = "HTTPS://Example.COM:443/feed#top",
) -> Response:
    response = await client.post("/api/v1/sources", headers=headers, json=source_payload(name, url))
    assert response.status_code == 201
    return response


def test_string_boundaries_are_checked_after_trimming() -> None:
    radar = RadarCreate.model_validate(
        {
            **radar_payload(" " + "r" * 120 + " "),
            "goal": " " + "g" * 4000 + " ",
        }
    )
    source = SourceCreate.model_validate(
        source_payload(" " + "s" * 160 + " ", " https://example.com/trimmed ")
    )
    assert len(radar.name) == 120
    assert len(radar.goal) == 4000
    assert len(source.name) == 160
    assert source.url == "https://example.com/trimmed"


@pytest.mark.asyncio
async def test_radar_crud_validation_pagination_and_state(resource_client: AsyncClient) -> None:
    headers = await headers_for(resource_client, "radar-owner@example.com")
    created = await create_radar(resource_client, headers)
    body = created.json()
    radar_id = body["id"]
    assert body["name"] == "Radar One"
    assert body["description"] == "description"
    assert body["goal"] == "Track important changes"
    assert body["categories"] == ["AI", "Security"]
    assert body["keywords"] == ["LLM", "Postgres"]
    assert "user_id" not in body and "deleted_at" not in body

    radar_two = (await create_radar(resource_client, headers, "Radar Two")).json()
    await create_radar(resource_client, headers, "Radar Three")
    update_conflict = await resource_client.patch(
        f"/api/v1/radars/{radar_two['id']}", headers=headers, json={"name": "Radar One"}
    )
    assert update_conflict.status_code == 409
    assert update_conflict.json()["error"]["code"] == "radar_name_conflict"
    page_one = await resource_client.get(
        "/api/v1/radars?page=1&page_size=2&radar_type=technology&status=active",
        headers=headers,
    )
    page_two = await resource_client.get("/api/v1/radars?page=2&page_size=2", headers=headers)
    assert page_one.status_code == page_two.status_code == 200
    assert page_one.json()["total"] == 3
    assert len(page_one.json()["items"]) == 2
    assert len(page_two.json()["items"]) == 1
    assert {item["id"] for item in page_one.json()["items"]}.isdisjoint(
        {item["id"] for item in page_two.json()["items"]}
    )

    previous = datetime.fromisoformat(body["updated_at"])
    patched = await resource_client.patch(
        f"/api/v1/radars/{radar_id}", headers=headers, json={"description": "  changed  "}
    )
    assert patched.status_code == 200
    assert patched.json()["description"] == "changed"
    assert datetime.fromisoformat(patched.json()["updated_at"]) > previous
    same_previous = datetime.fromisoformat(patched.json()["updated_at"])
    same_value = await resource_client.patch(
        f"/api/v1/radars/{radar_id}", headers=headers, json={"description": "changed"}
    )
    assert same_value.status_code == 200
    assert datetime.fromisoformat(same_value.json()["updated_at"]) > same_previous

    paused = await resource_client.post(f"/api/v1/radars/{radar_id}/pause", headers=headers)
    paused_again = await resource_client.post(f"/api/v1/radars/{radar_id}/pause", headers=headers)
    resumed = await resource_client.post(f"/api/v1/radars/{radar_id}/resume", headers=headers)
    assert paused.json()["status"] == paused_again.json()["status"] == "paused"
    assert resumed.json()["status"] == "active"

    for payload in ({}, {"status": "paused"}, {"name": None}, {"unknown": True}):
        invalid = await resource_client.patch(
            f"/api/v1/radars/{radar_id}", headers=headers, json=payload
        )
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "invalid_request"
    assert (await resource_client.get("/api/v1/radars?page=0", headers=headers)).status_code == 422
    assert (
        await resource_client.get("/api/v1/radars?page_size=101", headers=headers)
    ).status_code == 422

    deleted = await resource_client.delete(f"/api/v1/radars/{radar_id}", headers=headers)
    assert deleted.status_code == 204 and not deleted.content
    missing = await resource_client.get(f"/api/v1/radars/{radar_id}", headers=headers)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "resource_not_found"
    assert (await create_radar(resource_client, headers, "Radar One")).status_code == 201


@pytest.mark.asyncio
async def test_radar_boundaries_conflicts_and_user_scope(resource_client: AsyncClient) -> None:
    first = await headers_for(resource_client, "radar-first@example.com")
    second = await headers_for(resource_client, "radar-second@example.com")
    radar_id = (await create_radar(resource_client, first, "Shared Name")).json()["id"]
    duplicate = await resource_client.post(
        "/api/v1/radars", headers=first, json=radar_payload("Shared Name")
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "radar_name_conflict"
    assert (await create_radar(resource_client, second, "Shared Name")).status_code == 201

    async def attempt(name: str) -> int:
        return (
            await resource_client.post("/api/v1/radars", headers=first, json=radar_payload(name))
        ).status_code

    assert sorted(await asyncio.gather(attempt("Concurrent"), attempt("Concurrent"))) == [201, 409]
    for method, suffix, payload in [
        ("GET", "", None),
        ("PATCH", "", {"goal": "not yours"}),
        ("DELETE", "", None),
        ("POST", "/pause", None),
        ("POST", "/resume", None),
    ]:
        response = await resource_client.request(
            method, f"/api/v1/radars/{radar_id}{suffix}", headers=second, json=payload
        )
        missing = await resource_client.request(
            method, f"/api/v1/radars/{uuid4()}{suffix}", headers=second, json=payload
        )
        assert response.status_code == missing.status_code == 404
        assert (
            response.json()["error"]["code"]
            == missing.json()["error"]["code"]
            == "resource_not_found"
        )

    for field, value in [
        ("name", " "),
        ("goal", "x" * 4001),
        ("categories", [str(index) for index in range(21)]),
        ("keywords", ["x" * 121]),
        ("notification_threshold", 101),
        ("description", 123),
    ]:
        payload = radar_payload(f"Boundary {field}")
        payload[field] = value
        response = await resource_client.post("/api/v1/radars", headers=first, json=payload)
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_source_crud_url_conflicts_filters_and_state(resource_client: AsyncClient) -> None:
    headers = await headers_for(resource_client, "source-owner@example.com")
    created = await create_source(resource_client, headers)
    body = created.json()
    source_id = body["id"]
    assert body["url"] == "HTTPS://Example.COM:443/feed#top"
    assert body["normalized_url"] == "https://example.com/feed"
    assert "user_id" not in body and "deleted_at" not in body

    duplicate = await resource_client.post(
        "/api/v1/sources",
        headers=headers,
        json=source_payload("Duplicate", "https://example.com/feed"),
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "source_url_conflict"
    source_two = (
        await create_source(resource_client, headers, "Source Two", "https://two.example/feed")
    ).json()
    await create_source(resource_client, headers, "Source Three", "https://three.example/feed")

    unsupported = await resource_client.post(
        "/api/v1/sources",
        headers=headers,
        json={**source_payload("API", "https://api.example.com"), "source_type": "api"},
    )
    assert unsupported.status_code == 422
    assert unsupported.json()["error"]["code"] == "unsupported_source_type"

    previous = datetime.fromisoformat(body["updated_at"])
    patched = await resource_client.patch(
        f"/api/v1/sources/{source_id}",
        headers=headers,
        json={"name": "  Updated  ", "url": "http://BÜCHER.example.:80/a/../rss"},
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "Updated"
    assert patched.json()["normalized_url"] == "http://xn--bcher-kva.example/rss"
    assert datetime.fromisoformat(patched.json()["updated_at"]) > previous
    same_previous = datetime.fromisoformat(patched.json()["updated_at"])
    same_value = await resource_client.patch(
        f"/api/v1/sources/{source_id}", headers=headers, json={"name": "Updated"}
    )
    assert same_value.status_code == 200
    assert datetime.fromisoformat(same_value.json()["updated_at"]) > same_previous
    update_conflict = await resource_client.patch(
        f"/api/v1/sources/{source_two['id']}",
        headers=headers,
        json={"url": "http://bücher.example/rss"},
    )
    assert update_conflict.status_code == 409
    assert update_conflict.json()["error"]["code"] == "source_url_conflict"

    paused = await resource_client.post(f"/api/v1/sources/{source_id}/pause", headers=headers)
    paused_again = await resource_client.post(f"/api/v1/sources/{source_id}/pause", headers=headers)
    resumed = await resource_client.post(f"/api/v1/sources/{source_id}/resume", headers=headers)
    assert paused.json()["status"] == paused_again.json()["status"] == "paused"
    assert resumed.json()["status"] == "active"
    listed = await resource_client.get(
        "/api/v1/sources?status=active&source_type=rss&page=1&page_size=2", headers=headers
    )
    second_page = await resource_client.get(
        "/api/v1/sources?status=active&source_type=rss&page=2&page_size=2", headers=headers
    )
    assert listed.status_code == second_page.status_code == 200
    assert listed.json()["total"] == second_page.json()["total"] == 3
    assert len(listed.json()["items"]) == 2 and len(second_page.json()["items"]) == 1
    assert {item["id"] for item in listed.json()["items"]}.isdisjoint(
        {item["id"] for item in second_page.json()["items"]}
    )

    for payload in ({}, {"status": "paused"}, {"source_type": "url"}, {"config": None}):
        invalid = await resource_client.patch(
            f"/api/v1/sources/{source_id}", headers=headers, json=payload
        )
        assert invalid.status_code == 422
    for invalid_create in (
        source_payload(" ", "https://blank-name.example"),
        source_payload("x" * 161, "https://long-name.example"),
        {**source_payload("Short poll", "https://short-poll.example"), "poll_interval_minutes": 14},
        {
            **source_payload("Long poll", "https://long-poll.example"),
            "poll_interval_minutes": 10081,
        },
    ):
        assert (
            await resource_client.post("/api/v1/sources", headers=headers, json=invalid_create)
        ).status_code == 422
    huge_config = {"value": "x" * (16 * 1024)}
    assert (
        await resource_client.patch(
            f"/api/v1/sources/{source_id}", headers=headers, json={"config": huge_config}
        )
    ).status_code == 422


@pytest.mark.asyncio
async def test_source_concurrency_different_users_and_ownership(
    resource_client: AsyncClient,
) -> None:
    first = await headers_for(resource_client, "source-first@example.com")
    second = await headers_for(resource_client, "source-second@example.com")
    source_id = (
        await create_source(resource_client, first, url="https://same.example/path")
    ).json()["id"]
    assert (
        await create_source(resource_client, second, url="HTTPS://SAME.EXAMPLE:443/path#x")
    ).status_code == 201

    async def attempt(name: str) -> int:
        response = await resource_client.post(
            "/api/v1/sources",
            headers=first,
            json=source_payload(name, "https://race.example/feed"),
        )
        return response.status_code

    assert sorted(await asyncio.gather(attempt("Race A"), attempt("Race B"))) == [201, 409]
    for method, suffix, payload in [
        ("GET", "", None),
        ("PATCH", "", {"name": "not yours"}),
        ("DELETE", "", None),
        ("POST", "/pause", None),
        ("POST", "/resume", None),
    ]:
        response = await resource_client.request(
            method, f"/api/v1/sources/{source_id}{suffix}", headers=second, json=payload
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "resource_not_found"


@pytest.mark.asyncio
async def test_bind_unbind_ownership_state_concurrency_and_delete_semantics(
    resource_client: AsyncClient, resource_engine: AsyncEngine
) -> None:
    owner = await headers_for(resource_client, "binding-owner@example.com")
    other = await headers_for(resource_client, "binding-other@example.com")
    radar_id = (await create_radar(resource_client, owner)).json()["id"]
    source_id = (await create_source(resource_client, owner)).json()["id"]
    other_source = (
        await create_source(resource_client, other, "Other", "https://other.example/")
    ).json()["id"]
    binding_path = f"/api/v1/radars/{radar_id}/sources/{source_id}"

    async def bind() -> int:
        return (await resource_client.post(binding_path, headers=owner)).status_code

    assert await asyncio.gather(bind(), bind()) == [204, 204]
    listed = await resource_client.get(f"/api/v1/radars/{radar_id}/sources", headers=owner)
    assert listed.status_code == 200 and listed.json()["total"] == 1
    assert (
        await resource_client.post(
            f"/api/v1/radars/{radar_id}/sources/{other_source}", headers=owner
        )
    ).status_code == 404
    assert (
        await resource_client.get(f"/api/v1/radars/{radar_id}/sources", headers=other)
    ).status_code == 404

    assert (
        await resource_client.post(f"/api/v1/radars/{radar_id}/pause", headers=owner)
    ).status_code == 200
    assert (
        await resource_client.post(f"/api/v1/sources/{source_id}/pause", headers=owner)
    ).status_code == 200
    assert (await resource_client.post(binding_path, headers=owner)).status_code == 204
    assert (await resource_client.delete(binding_path, headers=owner)).status_code == 204
    assert (await resource_client.delete(binding_path, headers=owner)).status_code == 204

    await resource_client.post(binding_path, headers=owner)
    assert (
        await resource_client.delete(f"/api/v1/radars/{radar_id}", headers=owner)
    ).status_code == 204
    assert (
        await resource_client.get(f"/api/v1/sources/{source_id}", headers=owner)
    ).status_code == 200
    factory = async_sessionmaker(resource_engine, expire_on_commit=False)
    async with factory() as session:
        assert (
            await session.scalar(select(RadarSource).where(RadarSource.radar_id == UUID(radar_id)))
            is None
        )

    radar_two = (await create_radar(resource_client, owner, "Radar Two")).json()["id"]
    await resource_client.post(f"/api/v1/radars/{radar_two}/sources/{source_id}", headers=owner)
    assert (
        await resource_client.delete(f"/api/v1/sources/{source_id}", headers=owner)
    ).status_code == 204
    assert (
        await resource_client.get(f"/api/v1/radars/{radar_two}", headers=owner)
    ).status_code == 200
    async with factory() as session:
        assert (
            await session.scalar(
                select(RadarSource).where(RadarSource.source_id == UUID(source_id))
            )
            is None
        )


@pytest.mark.asyncio
async def test_archived_state_conflicts_and_openapi_contract(
    resource_client: AsyncClient, resource_engine: AsyncEngine
) -> None:
    headers = await headers_for(resource_client, "archived@example.com")
    radar_id = (await create_radar(resource_client, headers)).json()["id"]
    source_id = (await create_source(resource_client, headers)).json()["id"]
    factory = async_sessionmaker(resource_engine, expire_on_commit=False)
    async with factory() as session:
        radar = await session.get(Radar, UUID(radar_id))
        source = await session.get(Source, UUID(source_id))
        assert radar is not None and source is not None
        radar.status = ResourceStatus.ARCHIVED
        source.status = ResourceStatus.ARCHIVED
        await session.commit()
    for path in (
        f"/api/v1/radars/{radar_id}/pause",
        f"/api/v1/radars/{radar_id}/resume",
    ):
        response = await resource_client.post(path, headers=headers)
        assert (
            response.status_code == 409
            and response.json()["error"]["code"] == "invalid_radar_state"
        )
    for path in (
        f"/api/v1/sources/{source_id}/pause",
        f"/api/v1/sources/{source_id}/resume",
    ):
        response = await resource_client.post(path, headers=headers)
        assert (
            response.status_code == 409
            and response.json()["error"]["code"] == "invalid_source_state"
        )
    binding = await resource_client.post(
        f"/api/v1/radars/{radar_id}/sources/{source_id}", headers=headers
    )
    assert (
        binding.status_code == 409 and binding.json()["error"]["code"] == "invalid_resource_state"
    )

    document = (await resource_client.get("/openapi.json")).json()
    required_paths = {
        "/api/v1/radars",
        "/api/v1/radars/{radar_id}",
        "/api/v1/radars/{radar_id}/pause",
        "/api/v1/radars/{radar_id}/resume",
        "/api/v1/radars/{radar_id}/sources",
        "/api/v1/radars/{radar_id}/sources/{source_id}",
        "/api/v1/sources",
        "/api/v1/sources/{source_id}",
        "/api/v1/sources/{source_id}/pause",
        "/api/v1/sources/{source_id}/resume",
    }
    assert required_paths <= document["paths"].keys()
    assert {
        "RadarCreate",
        "RadarResponse",
        "RadarPage",
        "SourceCreate",
        "SourceResponse",
        "SourcePage",
        "ErrorEnvelope",
    } <= document["components"]["schemas"].keys()
    assert "HTTPBearer" in document["components"]["securitySchemes"]
    for path in required_paths:
        for operation in document["paths"][path].values():
            assert operation["security"] == [{"HTTPBearer": []}]
            assert "422" in operation["responses"]
