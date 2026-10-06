"""Add the evaluation version to opportunity scores (WP-7 I2 re-evaluation, ADR-041).

Revision ID: 20261006_0009
Revises: 20261006_0008

Re-evaluating a changed opportunity under the same rubric must coexist with the
previous score, so the uniqueness moves from ``(opportunity_id, radar_id,
score_version)`` to ``(opportunity_id, radar_id, score_version,
evaluation_version)``. Existing rows backfill to evaluation_version 1. The
downgrade refuses once any re-evaluation (evaluation_version > 1) exists, because
the legacy constraint cannot express that history.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261006_0009"
down_revision: str | None = "20261006_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_CONSTRAINT = "uq_opportunity_scores_triple"
NEW_CONSTRAINT = "uq_opportunity_scores_versioned"


def upgrade() -> None:
    op.add_column(
        "opportunity_scores",
        sa.Column("evaluation_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.drop_constraint(OLD_CONSTRAINT, "opportunity_scores", type_="unique")
    op.create_unique_constraint(
        NEW_CONSTRAINT,
        "opportunity_scores",
        ["opportunity_id", "radar_id", "score_version", "evaluation_version"],
    )


def downgrade() -> None:
    """Safe downgrade guard: refuse once any re-evaluation row exists."""
    rereviewed = (
        op.get_bind()
        .execute(sa.text("SELECT count(*) FROM opportunity_scores WHERE evaluation_version > 1"))
        .scalar()
    )
    if rereviewed:
        raise RuntimeError(
            "refusing to drop opportunity_scores.evaluation_version: "
            f"{rereviewed} re-evaluation row(s) exist (I2 lifecycle output)"
        )
    op.drop_constraint(NEW_CONSTRAINT, "opportunity_scores", type_="unique")
    op.create_unique_constraint(
        OLD_CONSTRAINT, "opportunity_scores", ["opportunity_id", "radar_id", "score_version"]
    )
    op.drop_column("opportunity_scores", "evaluation_version")
