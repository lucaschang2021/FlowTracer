"""WP-7 ACQ-1G opportunity: radar enum value, notification XOR, opportunity tables.

Revision ID: 20261005_0006
Revises: 20261005_0005

Scope (docs/24, ADR-025, ADR-037):
- add ``opportunity`` to the native ``radar_type`` PostgreSQL enum;
- extend ``notifications`` with ``opportunity_score_id`` and the exactly-one-fact
  named CHECK, replacing the analysis-only unique constraint with partial unique
  indexes;
- create ``opportunities``, ``opportunity_scores`` and ``opportunity_action_payloads``.

The downgrade fails fast without dropping data when any irreversible ACQ-1G fact or
the enum value itself is in use; only an empty opportunity layer is torn down.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261005_0006"
down_revision: str | None = "20261005_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPPORTUNITY_TABLES = (
    "opportunity_action_payloads",
    "opportunity_scores",
    "opportunities",
)
LEGACY_NOTIFICATION_UNIQUE = "notifications_user_id_analysis_id_key"
DIMENSIONS = (
    "fit",
    "expected_value",
    "completion_probability",
    "effort_efficiency",
    "time_to_delivery",
    "competition",
    "ambiguity",
    "risk",
)
DIMENSIONS_IN_RANGE = " AND ".join(
    f"({name} IS NULL OR {name} BETWEEN 0 AND 100)" for name in DIMENSIONS
)
DIMENSIONS_NOT_NULL = " AND ".join(f"{name} IS NOT NULL" for name in DIMENSIONS)
DIMENSIONS_NULL = " AND ".join(f"{name} IS NULL" for name in DIMENSIONS)
RADAR_ENUM_WITHOUT_OPPORTUNITY = (
    "academic",
    "business",
    "technology",
    "market",
    "policy",
    "competitive",
    "custom",
)


def upgrade() -> None:
    op.execute(sa.text("ALTER TYPE radar_type ADD VALUE IF NOT EXISTS 'opportunity'"))
    _create_opportunity_tables()
    _extend_notifications()


def _create_opportunity_tables() -> None:
    op.create_table(
        "opportunities",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("artifact_id", sa.UUID(), nullable=False),
        sa.Column("snapshot_id", sa.UUID(), nullable=False),
        sa.Column("profile_version", sa.String(40), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("platform", sa.String(120), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("budget_min", sa.Numeric(18, 2), nullable=True),
        sa.Column("budget_max", sa.Numeric(18, 2), nullable=True),
        sa.Column("currency", sa.CHAR(3), nullable=True),
        sa.Column(
            "skills", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("estimated_effort_hours", sa.Numeric(8, 2), nullable=True),
        sa.Column("delivery_type", sa.String(24), nullable=True),
        sa.Column(
            "client_metadata",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
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
        sa.CheckConstraint(
            "budget_min IS NULL OR budget_min >= 0", name="ck_opportunities_budget_min"
        ),
        sa.CheckConstraint(
            "budget_max IS NULL OR budget_max >= 0", name="ck_opportunities_budget_max"
        ),
        sa.CheckConstraint(
            "budget_min IS NULL OR budget_max IS NULL OR budget_min <= budget_max",
            name="ck_opportunities_budget_range",
        ),
        sa.CheckConstraint(
            "currency IS NULL OR currency ~ '^[A-Z]{3}$'", name="ck_opportunities_currency"
        ),
        sa.CheckConstraint("jsonb_typeof(skills) = 'array'", name="ck_opportunities_skills_array"),
        sa.CheckConstraint(
            "jsonb_typeof(client_metadata) = 'object'",
            name="ck_opportunities_client_metadata_object",
        ),
        sa.CheckConstraint(
            "estimated_effort_hours IS NULL OR estimated_effort_hours >= 0",
            name="ck_opportunities_effort",
        ),
        sa.CheckConstraint(
            "status IN ('active','expired','removed','rejected')", name="ck_opportunities_status"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["artifact_id"], ["source_artifacts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["acquisition_snapshots.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id", name="uq_opportunities_snapshot"),
    )
    op.create_index(
        "ix_opportunities_user_status_created",
        "opportunities",
        ["user_id", "status", sa.literal_column("created_at DESC"), "id"],
    )
    op.create_index(
        "ix_opportunities_source_published",
        "opportunities",
        ["source_id", sa.literal_column("published_at DESC")],
    )
    op.create_index("ix_opportunities_deadline", "opportunities", ["deadline"])

    op.create_table(
        "opportunity_scores",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("opportunity_id", sa.UUID(), nullable=False),
        sa.Column("radar_id", sa.UUID(), nullable=False),
        sa.Column("score_version", sa.String(40), nullable=False),
        sa.Column("hard_filter_passed", sa.Boolean(), nullable=False),
        sa.Column(
            "disqualifiers",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        *(sa.Column(name, sa.SmallInteger(), nullable=True) for name in DIMENSIONS),
        sa.Column("overall_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("recommendation", sa.String(20), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(DIMENSIONS_IN_RANGE, name="ck_opportunity_scores_dimensions"),
        sa.CheckConstraint(
            f"hard_filter_passed OR ({DIMENSIONS_NULL} AND overall_score IS NULL)",
            name="ck_opportunity_scores_failed_nulls",
        ),
        sa.CheckConstraint(
            f"NOT hard_filter_passed OR ({DIMENSIONS_NOT_NULL} AND overall_score IS NOT NULL)",
            name="ck_opportunity_scores_passed_not_nulls",
        ),
        sa.CheckConstraint(
            "overall_score IS NULL OR overall_score BETWEEN 0 AND 100",
            name="ck_opportunity_scores_overall",
        ),
        sa.CheckConstraint(
            "recommendation IN ('act_now','review','watch','dismiss')",
            name="ck_opportunity_scores_recommendation",
        ),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["radar_id"], ["radars.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "opportunity_id", "radar_id", "score_version", name="uq_opportunity_scores_triple"
        ),
    )
    op.create_index("ix_opportunity_scores_radar", "opportunity_scores", ["radar_id"])

    op.create_table(
        "opportunity_action_payloads",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("opportunity_score_id", sa.UUID(), nullable=False),
        sa.Column("payload_version", sa.String(40), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("payload_hash", sa.CHAR(64), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object'", name="ck_opportunity_action_payloads_object"
        ),
        sa.CheckConstraint(
            "pg_column_size(payload) <= 32768", name="ck_opportunity_action_payloads_size"
        ),
        sa.ForeignKeyConstraint(
            ["opportunity_score_id"], ["opportunity_scores.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "opportunity_score_id",
            "payload_version",
            name="uq_opportunity_action_payloads_version",
        ),
        sa.UniqueConstraint("payload_hash", name="uq_opportunity_action_payloads_hash"),
    )


def _extend_notifications() -> None:
    op.alter_column("notifications", "analysis_id", existing_type=sa.UUID(), nullable=True)
    op.add_column("notifications", sa.Column("opportunity_score_id", sa.UUID(), nullable=True))
    op.drop_constraint(LEGACY_NOTIFICATION_UNIQUE, "notifications", type_="unique")
    op.create_check_constraint(
        "ck_notifications_fact_target_xor",
        "notifications",
        "(analysis_id IS NULL) <> (opportunity_score_id IS NULL)",
    )
    op.create_index(
        "uq_notifications_user_analysis",
        "notifications",
        ["user_id", "analysis_id"],
        unique=True,
        postgresql_where=sa.text("analysis_id IS NOT NULL"),
    )
    op.create_index(
        "uq_notifications_user_opportunity_score",
        "notifications",
        ["user_id", "opportunity_score_id"],
        unique=True,
        postgresql_where=sa.text("opportunity_score_id IS NOT NULL"),
    )
    op.create_index(
        op.f("ix_notifications_opportunity_score_id"),
        "notifications",
        ["opportunity_score_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_notifications_opportunity_score",
        "notifications",
        "opportunity_scores",
        ["opportunity_score_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def _row_count(connection: sa.Connection, table: str) -> int:
    return int(connection.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar() or 0)  # noqa: S608


def downgrade() -> None:
    connection = op.get_bind()
    for table in OPPORTUNITY_TABLES:
        remaining = _row_count(connection, table)
        if remaining:
            raise RuntimeError(
                f"refusing to drop opportunity table {table}: {remaining} row(s) exist"
            )
    linked = _row_count(connection, "notifications WHERE opportunity_score_id IS NOT NULL")
    if linked:
        raise RuntimeError(
            "refusing to tear down the opportunity notification branch: "
            f"{linked} notification row(s) reference opportunity scores"
        )
    enum_used = int(
        connection.execute(
            sa.text("SELECT count(*) FROM radars WHERE radar_type = 'opportunity'")
        ).scalar()
        or 0
    )
    if enum_used:
        raise RuntimeError(
            f"refusing to rebuild radar_type: {enum_used} radar row(s) use 'opportunity'"
        )

    op.drop_constraint("fk_notifications_opportunity_score", "notifications", type_="foreignkey")
    op.drop_index("ix_notifications_opportunity_score_id", table_name="notifications")
    op.drop_index("uq_notifications_user_opportunity_score", table_name="notifications")
    op.drop_index("uq_notifications_user_analysis", table_name="notifications")
    op.drop_constraint("ck_notifications_fact_target_xor", "notifications", type_="check")
    op.drop_column("notifications", "opportunity_score_id")
    op.create_unique_constraint(
        LEGACY_NOTIFICATION_UNIQUE, "notifications", ["user_id", "analysis_id"]
    )
    op.alter_column("notifications", "analysis_id", existing_type=sa.UUID(), nullable=False)

    op.drop_table("opportunity_action_payloads")
    op.drop_index("ix_opportunity_scores_radar", table_name="opportunity_scores")
    op.drop_table("opportunity_scores")
    op.drop_index("ix_opportunities_deadline", table_name="opportunities")
    op.drop_index("ix_opportunities_source_published", table_name="opportunities")
    op.drop_index("ix_opportunities_user_status_created", table_name="opportunities")
    op.drop_table("opportunities")

    op.execute(sa.text("ALTER TYPE radar_type RENAME TO radar_type_with_opportunity"))
    op.execute(
        sa.text(
            "CREATE TYPE radar_type AS ENUM ("
            + ",".join(f"'{value}'" for value in RADAR_ENUM_WITHOUT_OPPORTUNITY)
            + ")"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE radars ALTER COLUMN radar_type TYPE radar_type "
            "USING (radar_type::text)::radar_type"
        )
    )
    op.execute(sa.text("DROP TYPE radar_type_with_opportunity"))
