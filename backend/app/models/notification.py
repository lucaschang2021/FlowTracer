"""Notification fact model with the ACQ-1G XOR extension (docs/24 §6, ADR-025).

Moved out of ``entities.py`` and extended so one notification row points at exactly
one fact source: either an Analysis (legacy intelligence path) or an
OpportunityScore. Existing intelligence IDs, statuses, read_at and event semantics
are unchanged; only the uniqueness enforcement moves to partial unique indexes.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.types import enum_column


class NotificationPriority(StrEnum):
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class NotificationStatus(StrEnum):
    UNREAD = "unread"
    READ = "read"


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "(analysis_id IS NULL) <> (opportunity_score_id IS NULL)",
            name="ck_notifications_fact_target_xor",
        ),
        Index(
            "uq_notifications_user_analysis",
            "user_id",
            "analysis_id",
            unique=True,
            postgresql_where=text("analysis_id IS NOT NULL"),
        ),
        Index(
            "uq_notifications_user_opportunity_score",
            "user_id",
            "opportunity_score_id",
            unique=True,
            postgresql_where=text("opportunity_score_id IS NOT NULL"),
        ),
        Index(
            "ix_notifications_user_status_created_at", "user_id", "status", text("created_at DESC")
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    analysis_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analyses.id", ondelete="CASCADE"),
        index=True,
    )
    opportunity_score_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("opportunity_scores.id", ondelete="RESTRICT"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[NotificationPriority] = mapped_column(
        enum_column(NotificationPriority, "notification_priority")
    )
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[NotificationStatus] = mapped_column(
        enum_column(NotificationStatus, "notification_status"),
        nullable=False,
        default=NotificationStatus.UNREAD,
        server_default="unread",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
