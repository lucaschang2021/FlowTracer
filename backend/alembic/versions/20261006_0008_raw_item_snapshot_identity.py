"""Add the snapshot identity to raw_items (WP-6 I2 writer switch, ADR-040).

Revision ID: 20261006_0008
Revises: 20261006_0007

New rows are created from qualifying snapshots (``created`` / ``content_changed``)
and are identified by ``UNIQUE(snapshot_id) WHERE snapshot_id IS NOT NULL``; the
legacy partial unique index on ``(source_id, external_id)`` is rebuilt to cover
only rows without a snapshot, so multiple versions of the same source entry can
coexist. The downgrade refuses to run once any snapshot-linked row exists, because
that proves the I2 writer produced data the legacy constraint cannot express.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261006_0008"
down_revision: str | None = "20261006_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_INDEX = "uq_raw_items_source_external"
SNAPSHOT_INDEX = "uq_raw_items_snapshot"
SNAPSHOT_FK = "fk_raw_items_snapshot"


def upgrade() -> None:
    op.add_column("raw_items", sa.Column("snapshot_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        SNAPSHOT_FK,
        "raw_items",
        "acquisition_snapshots",
        ["snapshot_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        SNAPSHOT_INDEX,
        "raw_items",
        ["snapshot_id"],
        unique=True,
        postgresql_where=sa.text("snapshot_id IS NOT NULL"),
    )
    op.drop_index(LEGACY_INDEX, table_name="raw_items")
    op.create_index(
        LEGACY_INDEX,
        "raw_items",
        ["source_id", "external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL AND snapshot_id IS NULL"),
    )


def downgrade() -> None:
    """Safe downgrade guard: refuse once the I2 writer created snapshot-linked rows."""
    linked = (
        op.get_bind()
        .execute(sa.text("SELECT count(*) FROM raw_items WHERE snapshot_id IS NOT NULL"))
        .scalar()
    )
    if linked:
        raise RuntimeError(
            "refusing to drop raw_items.snapshot_id: "
            f"{linked} snapshot-linked row(s) exist (I2 writer output)"
        )
    op.drop_index(LEGACY_INDEX, table_name="raw_items")
    op.create_index(
        LEGACY_INDEX,
        "raw_items",
        ["source_id", "external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )
    op.drop_index(SNAPSHOT_INDEX, table_name="raw_items")
    op.drop_constraint(SNAPSHOT_FK, "raw_items", type_="foreignkey")
    op.drop_column("raw_items", "snapshot_id")
