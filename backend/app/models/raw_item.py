"""RawItem fact model with the ACQ-1F snapshot identity (docs/23 §10/§13, ADR-040).

Moved out of ``entities.py`` so the I2 writer switch (``snapshot_id`` column plus the
partial-unique rebuild) does not grow a baseline warning module. Legacy semantics are
kept: rows without a snapshot stay guarded by the legacy partial unique index on
``(source_id, external_id)``, while every new row is identified by the qualifying
snapshot it was created from (``UNIQUE(snapshot_id) WHERE snapshot_id IS NOT NULL``).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import CHAR, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.types import TimestampMixin, enum_column


class RawItemStatus(StrEnum):
    FETCHED = "fetched"
    CLEANED = "cleaned"
    DUPLICATE = "duplicate"
    FAILED = "failed"


class RawItem(TimestampMixin, Base):
    __tablename__ = "raw_items"
    __table_args__ = (
        Index(
            "uq_raw_items_source_external",
            "source_id",
            "external_id",
            unique=True,
            postgresql_where=text("external_id IS NOT NULL AND snapshot_id IS NULL"),
        ),
        Index(
            "uq_raw_items_snapshot",
            "snapshot_id",
            unique=True,
            postgresql_where=text("snapshot_id IS NOT NULL"),
        ),
        Index("ix_raw_items_content_hash", "content_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    collection_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collection_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("acquisition_snapshots.id", ondelete="RESTRICT"),
    )
    external_id: Mapped[str | None] = mapped_column(String(512))
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(160))
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    item_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    status: Mapped[RawItemStatus] = mapped_column(enum_column(RawItemStatus, "raw_item_status"))
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(String(500))
