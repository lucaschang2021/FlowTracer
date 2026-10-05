"""add version evidence tables

Revision ID: 20261005_0005
Revises: 20260830_0004
Create Date: 2026-10-05

ACQ-1F shadow-write version evidence (docs/23 §10, §13): source_artifacts,
acquisition_snapshots, change_events. No raw_items change in this increment.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261005_0005"
down_revision: str | None = "20260830_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CHANGE_TYPE_SQL = (
    "'created', 'unchanged', 'content_changed', 'metadata_changed', 'structure_changed', 'removed'"
)
EVIDENCE_TABLES = ("change_events", "acquisition_snapshots", "source_artifacts")


def upgrade() -> None:
    op.create_table(
        "source_artifacts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("artifact_key", sa.String(length=512), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "safe_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "artifact_key", name="uq_source_artifacts_source_key"),
    )
    op.create_table(
        "acquisition_snapshots",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("artifact_id", sa.UUID(), nullable=False),
        sa.Column("collection_run_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("author", sa.String(length=300), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_type", sa.String(length=160), nullable=True),
        sa.Column("normalized_content", sa.Text(), nullable=False),
        sa.Column(
            "safe_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "structure_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("content_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("metadata_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("structure_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("extractor_version", sa.String(length=40), nullable=False),
        sa.Column("quality_score", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column(
            "evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "quality_score BETWEEN 0 AND 1", name="ck_acquisition_snapshots_quality"
        ),
        sa.CheckConstraint("version >= 1", name="ck_acquisition_snapshots_version"),
        sa.ForeignKeyConstraint(["artifact_id"], ["source_artifacts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["collection_run_id"], ["collection_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "artifact_id", "version", name="uq_acquisition_snapshots_artifact_version"
        ),
        sa.UniqueConstraint(
            "artifact_id",
            "content_hash",
            "metadata_hash",
            "structure_hash",
            name="uq_acquisition_snapshots_artifact_fingerprints",
        ),
    )
    op.create_table(
        "change_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("artifact_id", sa.UUID(), nullable=False),
        sa.Column("collection_run_id", sa.UUID(), nullable=False),
        sa.Column("previous_snapshot_id", sa.UUID(), nullable=True),
        sa.Column("current_snapshot_id", sa.UUID(), nullable=True),
        sa.Column("change_type", sa.String(length=24), nullable=False),
        sa.Column("materiality", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column(
            "field_diff",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("detector_version", sa.String(length=40), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(f"change_type IN ({CHANGE_TYPE_SQL})", name="ck_change_events_type"),
        sa.CheckConstraint("materiality BETWEEN 0 AND 1", name="ck_change_events_materiality"),
        sa.CheckConstraint(
            "change_type <> 'created' OR "
            "(previous_snapshot_id IS NULL AND current_snapshot_id IS NOT NULL)",
            name="ck_change_events_created",
        ),
        sa.CheckConstraint(
            "change_type <> 'removed' OR "
            "(previous_snapshot_id IS NOT NULL AND current_snapshot_id IS NULL)",
            name="ck_change_events_removed",
        ),
        sa.CheckConstraint(
            "change_type IN ('created', 'removed') OR "
            "(previous_snapshot_id IS NOT NULL AND current_snapshot_id IS NOT NULL)",
            name="ck_change_events_standard",
        ),
        sa.ForeignKeyConstraint(["artifact_id"], ["source_artifacts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["collection_run_id"], ["collection_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["current_snapshot_id"], ["acquisition_snapshots.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["previous_snapshot_id"], ["acquisition_snapshots.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "collection_run_id", "artifact_id", name="uq_change_events_run_artifact"
        ),
    )


def downgrade() -> None:
    """Safe downgrade guard: refuse to drop the evidence layer while rows exist."""
    connection = op.get_bind()
    for table in EVIDENCE_TABLES:
        remaining = connection.execute(
            sa.text(f"SELECT count(*) FROM {table}")  # noqa: S608 - frozen module tuple
        ).scalar()
        if remaining:
            raise RuntimeError(
                f"refusing to drop version evidence table {table}: {remaining} row(s) exist"
            )
    op.drop_table("change_events")
    op.drop_table("acquisition_snapshots")
    op.drop_table("source_artifacts")
