"""Opportunity Radar persistence models (ACQ-1G / docs/24, ADR-025, ADR-037).

OpportunityItem holds bounded facts derived from an AcquisitionSnapshot;
OpportunityScore holds one deterministic score per (opportunity, radar, score
version); OpportunityActionPayload holds an immutable, non-executable projection
with its SHA-256 hash. Facts never leave the snapshot allowlist.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CHAR,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.entities import TimestampMixin

OPPORTUNITY_STATUSES = ("active", "expired", "removed", "rejected")
OPPORTUNITY_STATUS_SQL = ", ".join(f"'{value}'" for value in OPPORTUNITY_STATUSES)
OPPORTUNITY_RECOMMENDATIONS = ("act_now", "review", "watch", "dismiss")
OPPORTUNITY_RECOMMENDATION_SQL = ", ".join(f"'{value}'" for value in OPPORTUNITY_RECOMMENDATIONS)

DIMENSION_FIELDS = (
    "fit",
    "expected_value",
    "completion_probability",
    "effort_efficiency",
    "time_to_delivery",
    "competition",
    "ambiguity",
    "risk",
)

_MAX_PAYLOAD_BYTES = 32768
_DIMENSIONS_NOT_NULL = " AND ".join(f"{name} IS NOT NULL" for name in DIMENSION_FIELDS)
_DIMENSIONS_NULL = " AND ".join(f"{name} IS NULL" for name in DIMENSION_FIELDS)
_DIMENSIONS_IN_RANGE = " AND ".join(
    f"({name} IS NULL OR {name} BETWEEN 0 AND 100)" for name in DIMENSION_FIELDS
)


class OpportunityItem(TimestampMixin, Base):
    __tablename__ = "opportunities"
    __table_args__ = (
        CheckConstraint(
            "budget_min IS NULL OR budget_min >= 0", name="ck_opportunities_budget_min"
        ),
        CheckConstraint(
            "budget_max IS NULL OR budget_max >= 0", name="ck_opportunities_budget_max"
        ),
        CheckConstraint(
            "budget_min IS NULL OR budget_max IS NULL OR budget_min <= budget_max",
            name="ck_opportunities_budget_range",
        ),
        CheckConstraint(
            "currency IS NULL OR currency ~ '^[A-Z]{3}$'", name="ck_opportunities_currency"
        ),
        CheckConstraint("jsonb_typeof(skills) = 'array'", name="ck_opportunities_skills_array"),
        CheckConstraint(
            "jsonb_typeof(client_metadata) = 'object'",
            name="ck_opportunities_client_metadata_object",
        ),
        CheckConstraint(
            "estimated_effort_hours IS NULL OR estimated_effort_hours >= 0",
            name="ck_opportunities_effort",
        ),
        CheckConstraint(f"status IN ({OPPORTUNITY_STATUS_SQL})", name="ck_opportunities_status"),
        UniqueConstraint("snapshot_id", name="uq_opportunities_snapshot"),
        Index(
            "ix_opportunities_user_status_created",
            "user_id",
            "status",
            text("created_at DESC"),
            "id",
        ),
        Index("ix_opportunities_source_published", "source_id", text("published_at DESC")),
        Index("ix_opportunities_deadline", "deadline"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False
    )
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_artifacts.id", ondelete="RESTRICT"), nullable=False
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("acquisition_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    profile_version: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[str | None] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    budget_min: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    budget_max: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    currency: Mapped[str | None] = mapped_column(CHAR(3))
    skills: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estimated_effort_hours: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    delivery_type: Mapped[str | None] = mapped_column(String(24))
    client_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", server_default="active"
    )


class OpportunityScore(Base):
    __tablename__ = "opportunity_scores"
    __table_args__ = (
        CheckConstraint(_DIMENSIONS_IN_RANGE, name="ck_opportunity_scores_dimensions"),
        CheckConstraint(
            f"hard_filter_passed OR ({_DIMENSIONS_NULL} AND overall_score IS NULL)",
            name="ck_opportunity_scores_failed_nulls",
        ),
        CheckConstraint(
            f"NOT hard_filter_passed OR ({_DIMENSIONS_NOT_NULL} AND overall_score IS NOT NULL)",
            name="ck_opportunity_scores_passed_not_nulls",
        ),
        CheckConstraint(
            "overall_score IS NULL OR overall_score BETWEEN 0 AND 100",
            name="ck_opportunity_scores_overall",
        ),
        CheckConstraint(
            f"recommendation IN ({OPPORTUNITY_RECOMMENDATION_SQL})",
            name="ck_opportunity_scores_recommendation",
        ),
        UniqueConstraint(
            "opportunity_id",
            "radar_id",
            "score_version",
            name="uq_opportunity_scores_triple",
        ),
        Index("ix_opportunity_scores_radar", "radar_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False
    )
    radar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("radars.id", ondelete="RESTRICT"), nullable=False
    )
    score_version: Mapped[str] = mapped_column(String(40), nullable=False)
    hard_filter_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    disqualifiers: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    fit: Mapped[int | None] = mapped_column(SmallInteger)
    expected_value: Mapped[int | None] = mapped_column(SmallInteger)
    completion_probability: Mapped[int | None] = mapped_column(SmallInteger)
    effort_efficiency: Mapped[int | None] = mapped_column(SmallInteger)
    time_to_delivery: Mapped[int | None] = mapped_column(SmallInteger)
    competition: Mapped[int | None] = mapped_column(SmallInteger)
    ambiguity: Mapped[int | None] = mapped_column(SmallInteger)
    risk: Mapped[int | None] = mapped_column(SmallInteger)
    overall_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    recommendation: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class OpportunityActionPayload(Base):
    __tablename__ = "opportunity_action_payloads"
    __table_args__ = (
        CheckConstraint(
            "jsonb_typeof(payload) = 'object'", name="ck_opportunity_action_payloads_object"
        ),
        CheckConstraint(
            f"pg_column_size(payload) <= {_MAX_PAYLOAD_BYTES}",
            name="ck_opportunity_action_payloads_size",
        ),
        UniqueConstraint(
            "opportunity_score_id",
            "payload_version",
            name="uq_opportunity_action_payloads_version",
        ),
        UniqueConstraint("payload_hash", name="uq_opportunity_action_payloads_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    opportunity_score_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("opportunity_scores.id", ondelete="CASCADE"),
        nullable=False,
    )
    payload_version: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    payload_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
