"""Version Evidence persistence models (ACQ-1F / docs/23 §10, §13).

SourceArtifact / AcquisitionSnapshot / ChangeEvent form the shadow-written version
evidence layer. They live outside ``entities.py`` so the baseline module stays within the
architecture gate's growth budget; metadata registration happens in ``app.models``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.entities import TimestampMixin

CHANGE_TYPES = (
    "created",
    "unchanged",
    "content_changed",
    "metadata_changed",
    "structure_changed",
    "removed",
)
CHANGE_TYPE_SQL = ", ".join(f"'{value}'" for value in CHANGE_TYPES)


class SourceArtifact(TimestampMixin, Base):
    __tablename__ = "source_artifacts"
    __table_args__ = (
        UniqueConstraint("source_id", "artifact_key", name="uq_source_artifacts_source_key"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False
    )
    artifact_key: Mapped[str] = mapped_column(String(512), nullable=False)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    safe_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )


class AcquisitionSnapshot(Base):
    __tablename__ = "acquisition_snapshots"
    __table_args__ = (
        CheckConstraint("version >= 1", name="ck_acquisition_snapshots_version"),
        CheckConstraint("quality_score BETWEEN 0 AND 1", name="ck_acquisition_snapshots_quality"),
        UniqueConstraint(
            "artifact_id", "version", name="uq_acquisition_snapshots_artifact_version"
        ),
        UniqueConstraint(
            "artifact_id",
            "content_hash",
            "metadata_hash",
            "structure_hash",
            name="uq_acquisition_snapshots_artifact_fingerprints",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_artifacts.id", ondelete="RESTRICT"), nullable=False
    )
    collection_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("collection_runs.id", ondelete="RESTRICT"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(300))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_type: Mapped[str | None] = mapped_column(String(160))
    normalized_content: Mapped[str] = mapped_column(Text, nullable=False)
    safe_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    structure_summary: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    content_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    metadata_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    structure_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    extractor_version: Mapped[str] = mapped_column(String(40), nullable=False)
    quality_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class ChangeEvent(Base):
    __tablename__ = "change_events"
    __table_args__ = (
        CheckConstraint(f"change_type IN ({CHANGE_TYPE_SQL})", name="ck_change_events_type"),
        CheckConstraint("materiality BETWEEN 0 AND 1", name="ck_change_events_materiality"),
        CheckConstraint(
            "change_type <> 'created' OR "
            "(previous_snapshot_id IS NULL AND current_snapshot_id IS NOT NULL)",
            name="ck_change_events_created",
        ),
        CheckConstraint(
            "change_type <> 'removed' OR "
            "(previous_snapshot_id IS NOT NULL AND current_snapshot_id IS NULL)",
            name="ck_change_events_removed",
        ),
        CheckConstraint(
            "change_type IN ('created', 'removed') OR "
            "(previous_snapshot_id IS NOT NULL AND current_snapshot_id IS NOT NULL)",
            name="ck_change_events_standard",
        ),
        UniqueConstraint("collection_run_id", "artifact_id", name="uq_change_events_run_artifact"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_artifacts.id", ondelete="RESTRICT"), nullable=False
    )
    collection_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("collection_runs.id", ondelete="RESTRICT"), nullable=False
    )
    previous_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("acquisition_snapshots.id", ondelete="RESTRICT"),
    )
    current_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("acquisition_snapshots.id", ondelete="RESTRICT"),
    )
    change_type: Mapped[str] = mapped_column(String(24), nullable=False)
    materiality: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    field_diff: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    detector_version: Mapped[str] = mapped_column(String(40), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
