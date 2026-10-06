"""Add the current-observation pointer to source_artifacts (closure Phase 0.3).

Revision ID: 20261006_0007
Revises: 20261005_0006

The pointer records the *last observed* snapshot state, which is the correct
classification baseline for change detection: after a revert re-uses an older
snapshot, comparing against the highest version number would re-report changes.
Existing artifacts are backfilled with their highest-version snapshot.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261006_0007"
down_revision: str | None = "20261005_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("source_artifacts", sa.Column("current_snapshot_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_source_artifacts_current_snapshot",
        "source_artifacts",
        "acquisition_snapshots",
        ["current_snapshot_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute(
        sa.text(
            "UPDATE source_artifacts AS sa SET current_snapshot_id = newest.id "
            "FROM (SELECT DISTINCT ON (artifact_id) artifact_id, id "
            "      FROM acquisition_snapshots ORDER BY artifact_id, version DESC) AS newest "
            "WHERE newest.artifact_id = sa.id"
        )
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_source_artifacts_current_snapshot", "source_artifacts", type_="foreignkey"
    )
    op.drop_column("source_artifacts", "current_snapshot_id")
