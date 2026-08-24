from __future__ import annotations

import os

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.db.base import Base
from app.models.entities import Radar, RadarType, RawItem, User


def test_all_alpha_models_registered_and_raw_metadata_is_aliased() -> None:
    expected = {
        "users",
        "refresh_tokens",
        "radars",
        "sources",
        "radar_sources",
        "collection_runs",
        "raw_items",
        "documents",
        "analyses",
        "document_chunks",
        "bookmarks",
        "notifications",
        "ai_usage_records",
    }
    assert expected == set(Base.metadata.tables)
    assert RawItem.item_metadata.property.columns[0].name == "metadata"
    assert not any(
        "ivfflat" in index.name or "hnsw" in index.name
        for table in Base.metadata.tables.values()
        for index in table.indexes
    )


@pytest.mark.asyncio
async def test_database_schema_has_frozen_constraints_indexes_and_delete_policies() -> None:
    database_url = os.environ["TEST_DATABASE_URL"]
    assert "_test" in database_url
    engine = create_async_engine(database_url)
    async with engine.connect() as connection:
        data = await connection.run_sync(
            lambda sync: {
                "tables": set(inspect(sync).get_table_names()),
                "user_indexes": inspect(sync).get_indexes("users"),
                "radar_checks": inspect(sync).get_check_constraints("radars"),
                "raw_fks": inspect(sync).get_foreign_keys("raw_items"),
                "enums": inspect(sync).get_enums(),
            }
        )
    await engine.dispose()
    assert set(Base.metadata.tables) <= data["tables"]
    assert any(index["name"] == "uq_users_active_email" for index in data["user_indexes"])
    assert any("notification_threshold" in check["sqltext"] for check in data["radar_checks"])
    assert {fk["options"].get("ondelete") for fk in data["raw_fks"]} == {"CASCADE", "RESTRICT"}
    radar_enum = next(item for item in data["enums"] if item["name"] == "radar_type")
    assert set(radar_enum["labels"]) == {item.value for item in RadarType}


@pytest.mark.asyncio
async def test_database_enforces_partial_unique_and_check_constraints() -> None:
    database_url = os.environ["TEST_DATABASE_URL"]
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.execute(text("TRUNCATE radars, refresh_tokens, users CASCADE"))
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User(
            email="constraints@example.com",
            password_hash="synthetic",
            display_name="Constraints",
        )
        session.add(user)
        await session.flush()
        session.add(
            Radar(
                user_id=user.id,
                name="Invalid",
                goal="test",
                radar_type=RadarType.CUSTOM,
                notification_threshold=101,
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()

    async with factory() as session:
        session.add_all(
            [
                User(email="same@example.com", password_hash="one", display_name="One"),
                User(email="same@example.com", password_hash="two", display_name="Two"),
            ]
        )
        with pytest.raises(IntegrityError):
            await session.commit()
    await engine.dispose()
