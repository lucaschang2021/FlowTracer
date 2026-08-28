from __future__ import annotations

import os
from typing import Any

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.db.base import Base
from app.models.entities import Radar, RadarType, RawItem, User

EXPECTED_TABLES = {
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

EXPECTED_ENUMS = {
    "radar_type": {
        "academic",
        "business",
        "technology",
        "market",
        "policy",
        "competitive",
        "custom",
    },
    "resource_status": {"active", "paused", "archived"},
    "source_type": {"rss", "url", "api"},
    "collection_trigger_type": {"schedule", "manual"},
    "collection_run_status": {"queued", "running", "succeeded", "partial", "failed"},
    "raw_item_status": {"fetched", "cleaned", "duplicate", "failed"},
    "document_status": {
        "pending",
        "cleaning",
        "deduplicating",
        "analyzing",
        "embedding",
        "ready",
        "failed",
    },
    "analysis_status": {"pending", "running", "completed", "failed"},
    "recommendation": {"must_read", "read", "monitor", "archive"},
    "notification_priority": {"normal", "high", "critical"},
    "notification_status": {"unread", "read"},
}

EXPECTED_INDEXES = {
    "users": {"uq_users_active_email"},
    "refresh_tokens": {
        "ix_refresh_tokens_expires_at",
        "ix_refresh_tokens_replaced_by_token_id",
        "ix_refresh_tokens_user_id",
    },
    "radars": {"ix_radars_user_id", "uq_radars_active_user_name"},
    "sources": {
        "ix_sources_status_next_fetch_at",
        "ix_sources_user_id",
        "uq_sources_active_user_url",
    },
    "radar_sources": {"ix_radar_sources_source_id"},
    "collection_runs": {
        "ix_collection_runs_source_created_at",
        "ix_collection_runs_source_id",
        "ix_collection_runs_triggered_by_user_id",
        "uq_collection_runs_source_idempotency",
    },
    "raw_items": {
        "ix_raw_items_collection_run_id",
        "ix_raw_items_content_hash",
        "ix_raw_items_source_id",
        "uq_raw_items_source_external",
    },
    "documents": {"ix_documents_raw_item_id", "ix_documents_status_created_at"},
    "analyses": {
        "ix_analyses_document_id",
        "ix_analyses_radar_id",
        "ix_analyses_radar_status_created_at",
    },
    "document_chunks": {
        "ix_document_chunks_document_id",
        "ix_document_chunks_embedding_hnsw_cosine",
    },
    "bookmarks": {"ix_bookmarks_document_id", "ix_bookmarks_user_id"},
    "notifications": {
        "ix_notifications_analysis_id",
        "ix_notifications_user_id",
        "ix_notifications_user_status_created_at",
    },
    "ai_usage_records": {
        "ix_ai_usage_records_analysis_id",
        "ix_ai_usage_records_user_created_at",
        "ix_ai_usage_records_user_id",
    },
}

EXPECTED_UNIQUES = {
    "refresh_tokens": {("token_hash",)},
    "documents": {("content_hash",)},
    "analyses": {("document_id", "radar_id", "pipeline_version")},
    "document_chunks": {("document_id", "chunk_index", "embedding_model")},
    "bookmarks": {("user_id", "document_id")},
    "notifications": {("user_id", "analysis_id")},
}

EXPECTED_PARTIAL_INDEXES = {
    "uq_users_active_email": "deleted_at IS NULL",
    "uq_radars_active_user_name": "deleted_at IS NULL",
    "uq_sources_active_user_url": "deleted_at IS NULL",
    "uq_collection_runs_source_idempotency": "idempotency_key IS NOT NULL",
    "uq_raw_items_source_external": "external_id IS NOT NULL",
}

EXPECTED_CHECKS = {
    "radars": ("notification_threshold",),
    "sources": ("poll_interval_minutes",),
    "collection_runs": ("fetched_count", "duplicate_count", "failed_count"),
    "documents": ("word_count",),
    "analyses": ("relevance", "importance", "novelty", "impact", "radar_score"),
    "document_chunks": ("chunk_index",),
    "ai_usage_records": ("input_tokens", "total_tokens", "estimated_cost", "duration_ms"),
}

EXPECTED_FOREIGN_KEYS = {
    "refresh_tokens": {
        (("user_id",), "users", ("id",), "CASCADE"),
        (("replaced_by_token_id",), "refresh_tokens", ("id",), "SET NULL"),
    },
    "radars": {(("user_id",), "users", ("id",), "CASCADE")},
    "sources": {(("user_id",), "users", ("id",), "CASCADE")},
    "radar_sources": {
        (("radar_id",), "radars", ("id",), "CASCADE"),
        (("source_id",), "sources", ("id",), "CASCADE"),
    },
    "collection_runs": {
        (("source_id",), "sources", ("id",), "RESTRICT"),
        (("triggered_by_user_id",), "users", ("id",), "SET NULL"),
    },
    "raw_items": {
        (("source_id",), "sources", ("id",), "RESTRICT"),
        (("collection_run_id",), "collection_runs", ("id",), "CASCADE"),
    },
    "documents": {(("raw_item_id",), "raw_items", ("id",), "RESTRICT")},
    "analyses": {
        (("document_id",), "documents", ("id",), "CASCADE"),
        (("radar_id",), "radars", ("id",), "CASCADE"),
    },
    "document_chunks": {(("document_id",), "documents", ("id",), "CASCADE")},
    "bookmarks": {
        (("user_id",), "users", ("id",), "CASCADE"),
        (("document_id",), "documents", ("id",), "CASCADE"),
    },
    "notifications": {
        (("user_id",), "users", ("id",), "CASCADE"),
        (("analysis_id",), "analyses", ("id",), "CASCADE"),
    },
    "ai_usage_records": {
        (("user_id",), "users", ("id",), "CASCADE"),
        (("analysis_id",), "analyses", ("id",), "SET NULL"),
    },
}


def test_all_alpha_models_registered_and_raw_metadata_is_aliased() -> None:
    assert EXPECTED_TABLES == set(Base.metadata.tables)
    assert RawItem.item_metadata.property.columns[0].name == "metadata"
    assert not any(
        "ivfflat" in index.name
        for table in Base.metadata.tables.values()
        for index in table.indexes
    )
    hnsw = next(
        index
        for index in Base.metadata.tables["document_chunks"].indexes
        if index.name == "ix_document_chunks_embedding_hnsw_cosine"
    )
    assert hnsw.dialect_options["postgresql"]["using"] == "hnsw"
    assert hnsw.dialect_options["postgresql"]["ops"] == {"embedding": "vector_cosine_ops"}


def _inspect_contract(sync_connection: Any) -> dict[str, Any]:
    inspector = inspect(sync_connection)
    return {
        "tables": set(inspector.get_table_names()),
        "columns": {
            table: {column["name"] for column in inspector.get_columns(table)}
            for table in EXPECTED_TABLES
        },
        "indexes": {table: inspector.get_indexes(table) for table in EXPECTED_TABLES},
        "uniques": {table: inspector.get_unique_constraints(table) for table in EXPECTED_TABLES},
        "checks": {table: inspector.get_check_constraints(table) for table in EXPECTED_TABLES},
        "foreign_keys": {table: inspector.get_foreign_keys(table) for table in EXPECTED_TABLES},
        "enums": inspector.get_enums(),
    }


@pytest.mark.asyncio
async def test_every_table_matches_frozen_postgresql_contract() -> None:
    database_url = os.environ["TEST_DATABASE_URL"]
    assert "_test" in database_url.rsplit("/", maxsplit=1)[-1]
    engine = create_async_engine(database_url)
    async with engine.connect() as connection:
        contract = await connection.run_sync(_inspect_contract)
    await engine.dispose()

    assert EXPECTED_TABLES <= contract["tables"]
    for table_name, table in Base.metadata.tables.items():
        assert contract["columns"][table_name] == {column.name for column in table.columns}

    all_indexes: dict[str, dict[str, Any]] = {}
    for table_name, expected_names in EXPECTED_INDEXES.items():
        actual = {
            item["name"]: item
            for item in contract["indexes"][table_name]
            if not item.get("duplicates_constraint")
        }
        assert set(actual) == expected_names
        all_indexes.update(actual)

    for index_name, predicate in EXPECTED_PARTIAL_INDEXES.items():
        options = all_indexes[index_name]["dialect_options"]
        assert predicate.lower() in str(options["postgresql_where"]).lower()

    hnsw_options = all_indexes["ix_document_chunks_embedding_hnsw_cosine"]["dialect_options"]
    assert hnsw_options["postgresql_using"] == "hnsw"
    assert hnsw_options["postgresql_ops"] == {"embedding": "vector_cosine_ops"}
    assert hnsw_options["postgresql_with"] == {"m": "16", "ef_construction": "64"}

    for table_name in EXPECTED_TABLES:
        actual_unique = {tuple(item["column_names"]) for item in contract["uniques"][table_name]}
        assert actual_unique == EXPECTED_UNIQUES.get(table_name, set())

    for table_name, fragments in EXPECTED_CHECKS.items():
        sql = " ".join(item["sqltext"] for item in contract["checks"][table_name])
        for fragment in fragments:
            assert fragment in sql

    for table_name in EXPECTED_TABLES:
        actual_foreign_keys = {
            (
                tuple(item["constrained_columns"]),
                item["referred_table"],
                tuple(item["referred_columns"]),
                item["options"].get("ondelete"),
            )
            for item in contract["foreign_keys"][table_name]
        }
        assert actual_foreign_keys == EXPECTED_FOREIGN_KEYS.get(table_name, set())

    actual_enums = {item["name"]: set(item["labels"]) for item in contract["enums"]}
    assert actual_enums == EXPECTED_ENUMS


@pytest.mark.asyncio
async def test_database_enforces_partial_unique_and_check_constraints() -> None:
    database_url = os.environ["TEST_DATABASE_URL"]
    assert "_test" in database_url.rsplit("/", maxsplit=1)[-1]
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
