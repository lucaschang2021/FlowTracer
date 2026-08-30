"""Expand acquisition source profile, health, attempt, and lease state.

Revision ID: 20260830_0004
Revises: 20260827_0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260830_0004"
down_revision: str | None = "20260827_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_PROFILE = """{
  "content_profile": "generic",
  "priority": "normal",
  "allow_browser": false,
  "change_detection": {
    "enabled": true,
    "materiality_threshold": 0.1500,
    "semantic_enabled": false
  },
  "resource_budget": {
    "max_requests": 10,
    "max_pages": 1,
    "max_depth": 0,
    "max_duration_seconds": 120,
    "max_concurrency": 1,
    "max_browser_pages": 0,
    "max_retries_per_target": 2,
    "max_total_bytes": 5242880
  },
  "site_policy": {
    "robots_mode": "respect",
    "crawl_delay_ms": 1000,
    "requests_per_minute": 30,
    "max_parallel_requests": 1,
    "allowed_content_types": [
      "text/html",
      "application/rss+xml",
      "application/atom+xml",
      "application/xml",
      "text/xml"
    ],
    "allow_paths": [],
    "deny_paths": []
  },
  "approved_domains": [],
  "family_options": {}
}"""


def upgrade() -> None:
    op.add_column(
        "sources",
        sa.Column("source_family", sa.String(32), server_default="generic_web", nullable=False),
    )
    op.add_column(
        "sources",
        sa.Column("acquisition_mode", sa.String(16), server_default="auto", nullable=False),
    )
    op.add_column(
        "sources",
        sa.Column("discovery_mode", sa.String(24), server_default="single_page", nullable=False),
    )
    op.add_column(
        "sources",
        sa.Column("profile_version", sa.String(40), server_default="acq-source-v1", nullable=False),
    )
    op.add_column(
        "sources",
        sa.Column(
            "acquisition_profile",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_sources_source_family",
        "sources",
        "source_family IN ('policy','academic','finance','corporate','technology',"
        "'community','event','opportunity','generic_web')",
    )
    op.create_check_constraint(
        "ck_sources_acquisition_mode",
        "sources",
        "acquisition_mode IN ('auto','native','dynamic','advanced')",
    )
    op.create_check_constraint(
        "ck_sources_discovery_mode",
        "sources",
        "discovery_mode IN ('single_page','same_path','same_domain','approved_domains')",
    )
    op.create_check_constraint(
        "ck_sources_profile_version", "sources", "profile_version = 'acq-source-v1'"
    )
    op.create_check_constraint(
        "ck_sources_acquisition_profile_object",
        "sources",
        "jsonb_typeof(acquisition_profile) = 'object'",
    )
    op.execute(
        sa.text(
            "UPDATE sources SET acquisition_profile = CAST(:profile AS jsonb) "
            "WHERE acquisition_profile = '{}'::jsonb"
        ).bindparams(profile=DEFAULT_PROFILE)
    )

    op.create_table(
        "source_acquisition_states",
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("health_status", sa.String(20), server_default="healthy", nullable=False),
        sa.Column("success_count", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("failure_count", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("consecutive_failures", sa.Integer(), server_default="0", nullable=False),
        sa.Column("latency_ewma_ms", sa.Integer(), nullable=True),
        sa.Column("quality_ewma", sa.Numeric(5, 4), nullable=True),
        sa.Column("last_backend", sa.String(32), nullable=True),
        sa.Column("last_error_code", sa.String(80), nullable=True),
        sa.Column("circuit_open_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "checkpoint", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
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
            "health_status IN ('healthy','degraded','unhealthy','circuit_open')",
            name="ck_source_acquisition_states_health_status",
        ),
        sa.CheckConstraint(
            "last_backend IS NULL OR last_backend IN ('rss','native_http','scrapling_http','dynamic_browser','advanced_browser')",
            name="ck_source_acquisition_states_last_backend",
        ),
        sa.CheckConstraint(
            "success_count >= 0 AND failure_count >= 0 AND consecutive_failures >= 0",
            name="ck_source_acquisition_states_counts",
        ),
        sa.CheckConstraint(
            "latency_ewma_ms IS NULL OR latency_ewma_ms >= 0",
            name="ck_source_acquisition_states_latency",
        ),
        sa.CheckConstraint(
            "quality_ewma IS NULL OR quality_ewma BETWEEN 0 AND 1",
            name="ck_source_acquisition_states_quality",
        ),
        sa.CheckConstraint("version >= 1", name="ck_source_acquisition_states_version"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("source_id"),
    )
    op.execute(
        sa.text(
            "INSERT INTO source_acquisition_states (source_id) "
            "SELECT id FROM sources ON CONFLICT (source_id) DO NOTHING"
        )
    )

    for column in (
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("worker_id", sa.String(160), nullable=True),
        sa.Column("claim_token", sa.UUID(), nullable=True),
        sa.Column("claim_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("backend", sa.String(32), nullable=True),
        sa.Column("fallback_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("pages_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("quality_score", sa.Numeric(5, 4), nullable=True),
        sa.Column(
            "budget_summary",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    ):
        op.add_column("collection_runs", column)
    op.execute(
        sa.text(
            "UPDATE collection_runs SET "
            "claimed_at = COALESCE(started_at, now()), "
            "heartbeat_at = now(), "
            "lease_expires_at = now(), "
            "worker_id = 'legacy-migration', "
            "claim_token = id, "
            "claim_count = GREATEST(claim_count, 1) "
            "WHERE status = 'running'"
        )
    )
    op.create_check_constraint(
        "ck_collection_runs_acquisition_metrics",
        "collection_runs",
        "claim_count >= 0 AND fallback_count >= 0 AND pages_count >= 0 AND "
        "(duration_ms IS NULL OR duration_ms >= 0) AND "
        "(quality_score IS NULL OR quality_score BETWEEN 0 AND 1)",
    )
    op.create_check_constraint(
        "ck_collection_runs_running_lease",
        "collection_runs",
        "status <> 'running' OR (claim_token IS NOT NULL AND lease_expires_at IS NOT NULL "
        "AND worker_id IS NOT NULL)",
    )
    op.create_index(
        "ix_collection_runs_status_lease_expires_at",
        "collection_runs",
        ["status", "lease_expires_at"],
    )

    op.create_table(
        "acquisition_attempts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("ordinal", sa.SmallInteger(), nullable=False),
        sa.Column("backend", sa.String(32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("requested_url", sa.Text(), nullable=False),
        sa.Column("final_url", sa.Text(), nullable=True),
        sa.Column("status_code", sa.SmallInteger(), nullable=True),
        sa.Column("content_type", sa.String(160), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("retry_count", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("pages", sa.Integer(), server_default="0", nullable=False),
        sa.Column("bytes_received", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("quality_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("fallback_reason", sa.String(80), nullable=True),
        sa.Column(
            "budget_used", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.Column("safe_error", sa.String(500), nullable=True),
        sa.Column("decision_version", sa.String(40), nullable=False),
        sa.CheckConstraint("ordinal >= 1", name="ck_acquisition_attempts_ordinal"),
        sa.CheckConstraint(
            "backend IN ('rss','native_http','scrapling_http','dynamic_browser','advanced_browser')",
            name="ck_acquisition_attempts_backend",
        ),
        sa.CheckConstraint(
            "status IN ('succeeded','failed','blocked','cancelled')",
            name="ck_acquisition_attempts_status",
        ),
        sa.CheckConstraint(
            "status_code IS NULL OR status_code BETWEEN 100 AND 599",
            name="ck_acquisition_attempts_status_code",
        ),
        sa.CheckConstraint(
            "duration_ms >= 0 AND retry_count >= 0 AND pages >= 0 AND bytes_received >= 0",
            name="ck_acquisition_attempts_metrics",
        ),
        sa.CheckConstraint(
            "quality_score IS NULL OR quality_score BETWEEN 0 AND 1",
            name="ck_acquisition_attempts_quality",
        ),
        sa.ForeignKeyConstraint(["run_id"], ["collection_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "ordinal", name="uq_acquisition_attempts_run_ordinal"),
    )
    op.create_index(
        "ix_acquisition_attempts_source_started_at",
        "acquisition_attempts",
        ["source_id", sa.literal_column("started_at DESC")],
    )
    op.create_index(
        "ix_acquisition_attempts_run_started_at", "acquisition_attempts", ["run_id", "started_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_acquisition_attempts_run_started_at", table_name="acquisition_attempts")
    op.drop_index("ix_acquisition_attempts_source_started_at", table_name="acquisition_attempts")
    op.drop_table("acquisition_attempts")
    op.drop_index("ix_collection_runs_status_lease_expires_at", table_name="collection_runs")
    op.drop_constraint("ck_collection_runs_running_lease", "collection_runs", type_="check")
    op.drop_constraint("ck_collection_runs_acquisition_metrics", "collection_runs", type_="check")
    for name in (
        "budget_summary",
        "quality_score",
        "duration_ms",
        "pages_count",
        "fallback_count",
        "backend",
        "claim_count",
        "claim_token",
        "worker_id",
        "lease_expires_at",
        "heartbeat_at",
        "claimed_at",
    ):
        op.drop_column("collection_runs", name)
    op.drop_table("source_acquisition_states")
    for name in (
        "ck_sources_acquisition_profile_object",
        "ck_sources_profile_version",
        "ck_sources_discovery_mode",
        "ck_sources_acquisition_mode",
        "ck_sources_source_family",
    ):
        op.drop_constraint(name, "sources", type_="check")
    for name in (
        "acquisition_profile",
        "profile_version",
        "discovery_mode",
        "acquisition_mode",
        "source_family",
    ):
        op.drop_column("sources", name)
