from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum
from enum import StrEnum
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
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


class RadarType(StrEnum):
    ACADEMIC = "academic"
    BUSINESS = "business"
    TECHNOLOGY = "technology"
    MARKET = "market"
    POLICY = "policy"
    COMPETITIVE = "competitive"
    CUSTOM = "custom"


class ResourceStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class SourceType(StrEnum):
    RSS = "rss"
    URL = "url"
    API = "api"


class SourceFamily(StrEnum):
    POLICY = "policy"
    ACADEMIC = "academic"
    FINANCE = "finance"
    CORPORATE = "corporate"
    TECHNOLOGY = "technology"
    COMMUNITY = "community"
    EVENT = "event"
    OPPORTUNITY = "opportunity"
    GENERIC_WEB = "generic_web"


class AcquisitionMode(StrEnum):
    AUTO = "auto"
    NATIVE = "native"
    DYNAMIC = "dynamic"
    ADVANCED = "advanced"


class DiscoveryMode(StrEnum):
    SINGLE_PAGE = "single_page"
    SAME_PATH = "same_path"
    SAME_DOMAIN = "same_domain"
    APPROVED_DOMAINS = "approved_domains"


class SourceHealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CIRCUIT_OPEN = "circuit_open"


class AcquisitionAttemptStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class BackendName(StrEnum):
    RSS = "rss"
    NATIVE_HTTP = "native_http"
    SCRAPLING_HTTP = "scrapling_http"
    DYNAMIC_BROWSER = "dynamic_browser"
    ADVANCED_BROWSER = "advanced_browser"


class CollectionTriggerType(StrEnum):
    SCHEDULE = "schedule"
    MANUAL = "manual"


class CollectionRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"


class RawItemStatus(StrEnum):
    FETCHED = "fetched"
    CLEANED = "cleaned"
    DUPLICATE = "duplicate"
    FAILED = "failed"


class DocumentStatus(StrEnum):
    PENDING = "pending"
    CLEANING = "cleaning"
    DEDUPLICATING = "deduplicating"
    ANALYZING = "analyzing"
    EMBEDDING = "embedding"
    READY = "ready"
    FAILED = "failed"


class AnalysisStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Recommendation(StrEnum):
    MUST_READ = "must_read"
    READ = "read"
    MONITOR = "monitor"
    ARCHIVE = "archive"


class NotificationPriority(StrEnum):
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class NotificationStatus(StrEnum):
    UNREAD = "unread"
    READ = "read"


def enum_column(enum_type: type[PyEnum], name: str) -> Enum:
    return Enum(
        enum_type, name=name, values_callable=lambda values: [item.value for item in values]
    )


def varchar_enum(enum_type: type[PyEnum], length: int) -> Enum:
    return Enum(
        enum_type,
        native_enum=False,
        create_constraint=False,
        length=length,
        values_callable=lambda values: [item.value for item in values],
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=text("now()"),
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        Index(
            "uq_users_active_email",
            "email",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    profile: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by_token_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("refresh_tokens.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class Radar(TimestampMixin, Base):
    __tablename__ = "radars"
    __table_args__ = (
        CheckConstraint(
            "notification_threshold BETWEEN 0 AND 100", name="radars_notification_threshold_check"
        ),
        Index(
            "uq_radars_active_user_name",
            "user_id",
            "name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    radar_type: Mapped[RadarType] = mapped_column(enum_column(RadarType, "radar_type"))
    categories: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    keywords: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    status: Mapped[ResourceStatus] = mapped_column(
        enum_column(ResourceStatus, "resource_status"),
        nullable=False,
        default=ResourceStatus.ACTIVE,
        server_default="active",
    )
    notification_threshold: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=75, server_default="75"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Source(TimestampMixin, Base):
    __tablename__ = "sources"
    __table_args__ = (
        CheckConstraint("poll_interval_minutes >= 15", name="sources_poll_interval_minutes_check"),
        CheckConstraint(
            "source_family IN ('policy','academic','finance','corporate','technology',"
            "'community','event','opportunity','generic_web')",
            name="ck_sources_source_family",
        ),
        CheckConstraint(
            "acquisition_mode IN ('auto','native','dynamic','advanced')",
            name="ck_sources_acquisition_mode",
        ),
        CheckConstraint(
            "discovery_mode IN ('single_page','same_path','same_domain','approved_domains')",
            name="ck_sources_discovery_mode",
        ),
        CheckConstraint("profile_version = 'acq-source-v1'", name="ck_sources_profile_version"),
        CheckConstraint(
            "jsonb_typeof(acquisition_profile) = 'object'",
            name="ck_sources_acquisition_profile_object",
        ),
        Index(
            "uq_sources_active_user_url",
            "user_id",
            "normalized_url",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_sources_status_next_fetch_at", "status", "next_fetch_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_type: Mapped[SourceType] = mapped_column(enum_column(SourceType, "source_type"))
    url: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_url: Mapped[str] = mapped_column(Text, nullable=False)
    poll_interval_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=60, server_default="60"
    )
    status: Mapped[ResourceStatus] = mapped_column(
        enum_column(ResourceStatus, "resource_status"),
        nullable=False,
        default=ResourceStatus.ACTIVE,
        server_default="active",
    )
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_fetch_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    source_family: Mapped[SourceFamily] = mapped_column(
        varchar_enum(SourceFamily, 32),
        nullable=False,
        default=SourceFamily.GENERIC_WEB,
        server_default=SourceFamily.GENERIC_WEB.value,
    )
    acquisition_mode: Mapped[AcquisitionMode] = mapped_column(
        varchar_enum(AcquisitionMode, 16),
        nullable=False,
        default=AcquisitionMode.AUTO,
        server_default=AcquisitionMode.AUTO.value,
    )
    discovery_mode: Mapped[DiscoveryMode] = mapped_column(
        varchar_enum(DiscoveryMode, 24),
        nullable=False,
        default=DiscoveryMode.SINGLE_PAGE,
        server_default=DiscoveryMode.SINGLE_PAGE.value,
    )
    profile_version: Mapped[str] = mapped_column(
        String(40), nullable=False, default="acq-source-v1", server_default="acq-source-v1"
    )
    acquisition_profile: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SourceAcquisitionState(TimestampMixin, Base):
    __tablename__ = "source_acquisition_states"
    __table_args__ = (
        CheckConstraint(
            "health_status IN ('healthy','degraded','unhealthy','circuit_open')",
            name="ck_source_acquisition_states_health_status",
        ),
        CheckConstraint(
            "last_backend IS NULL OR last_backend IN "
            "('rss','native_http','scrapling_http','dynamic_browser','advanced_browser')",
            name="ck_source_acquisition_states_last_backend",
        ),
        CheckConstraint(
            "success_count >= 0 AND failure_count >= 0 AND consecutive_failures >= 0",
            name="ck_source_acquisition_states_counts",
        ),
        CheckConstraint(
            "latency_ewma_ms IS NULL OR latency_ewma_ms >= 0",
            name="ck_source_acquisition_states_latency",
        ),
        CheckConstraint(
            "quality_ewma IS NULL OR quality_ewma BETWEEN 0 AND 1",
            name="ck_source_acquisition_states_quality",
        ),
        CheckConstraint("version >= 1", name="ck_source_acquisition_states_version"),
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id", ondelete="CASCADE"), primary_key=True
    )
    health_status: Mapped[SourceHealthStatus] = mapped_column(
        varchar_enum(SourceHealthStatus, 20),
        nullable=False,
        default=SourceHealthStatus.HEALTHY,
        server_default=SourceHealthStatus.HEALTHY.value,
    )
    success_count: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    failure_count: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    consecutive_failures: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    latency_ewma_ms: Mapped[int | None] = mapped_column(Integer)
    quality_ewma: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    last_backend: Mapped[BackendName | None] = mapped_column(varchar_enum(BackendName, 32))
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    circuit_open_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checkpoint: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class RadarSource(Base):
    __tablename__ = "radar_sources"
    radar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("radars.id", ondelete="CASCADE"), primary_key=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class CollectionRun(TimestampMixin, Base):
    __tablename__ = "collection_runs"
    __table_args__ = (
        CheckConstraint(
            "fetched_count >= 0 AND created_count >= 0 AND "
            "duplicate_count >= 0 AND failed_count >= 0",
            name="collection_runs_check",
        ),
        CheckConstraint(
            "claim_count >= 0 AND fallback_count >= 0 AND pages_count >= 0 AND "
            "(duration_ms IS NULL OR duration_ms >= 0) AND "
            "(quality_score IS NULL OR quality_score BETWEEN 0 AND 1)",
            name="ck_collection_runs_acquisition_metrics",
        ),
        CheckConstraint(
            "status <> 'running' OR (claim_token IS NOT NULL AND "
            "lease_expires_at IS NOT NULL AND worker_id IS NOT NULL)",
            name="ck_collection_runs_running_lease",
        ),
        Index(
            "uq_collection_runs_source_idempotency",
            "source_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        Index("ix_collection_runs_source_created_at", "source_id", text("created_at DESC")),
        Index("ix_collection_runs_status_lease_expires_at", "status", "lease_expires_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    triggered_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    trigger_type: Mapped[CollectionTriggerType] = mapped_column(
        enum_column(CollectionTriggerType, "collection_trigger_type")
    )
    status: Mapped[CollectionRunStatus] = mapped_column(
        enum_column(CollectionRunStatus, "collection_run_status")
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    created_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    duplicate_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    failed_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(String(500))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    worker_id: Mapped[str | None] = mapped_column(String(160))
    claim_token: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    claim_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    backend: Mapped[str | None] = mapped_column(String(32))
    fallback_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    pages_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    quality_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    budget_summary: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )


class AcquisitionAttempt(Base):
    __tablename__ = "acquisition_attempts"
    __table_args__ = (
        CheckConstraint("ordinal >= 1", name="ck_acquisition_attempts_ordinal"),
        CheckConstraint(
            "backend IN "
            "('rss','native_http','scrapling_http','dynamic_browser','advanced_browser')",
            name="ck_acquisition_attempts_backend",
        ),
        CheckConstraint(
            "status IN ('succeeded','failed','blocked','cancelled')",
            name="ck_acquisition_attempts_status",
        ),
        CheckConstraint(
            "status_code IS NULL OR status_code BETWEEN 100 AND 599",
            name="ck_acquisition_attempts_status_code",
        ),
        CheckConstraint(
            "duration_ms >= 0 AND retry_count >= 0 AND pages >= 0 AND bytes_received >= 0",
            name="ck_acquisition_attempts_metrics",
        ),
        CheckConstraint(
            "quality_score IS NULL OR quality_score BETWEEN 0 AND 1",
            name="ck_acquisition_attempts_quality",
        ),
        UniqueConstraint("run_id", "ordinal", name="uq_acquisition_attempts_run_ordinal"),
        Index("ix_acquisition_attempts_source_started_at", "source_id", text("started_at DESC")),
        Index("ix_acquisition_attempts_run_started_at", "run_id", "started_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("collection_runs.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    backend: Mapped[BackendName] = mapped_column(varchar_enum(BackendName, 32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[AcquisitionAttemptStatus] = mapped_column(
        varchar_enum(AcquisitionAttemptStatus, 20), nullable=False
    )
    requested_url: Mapped[str] = mapped_column(Text, nullable=False)
    final_url: Mapped[str | None] = mapped_column(Text)
    status_code: Mapped[int | None] = mapped_column(SmallInteger)
    content_type: Mapped[str | None] = mapped_column(String(160))
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    retry_count: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, server_default="0"
    )
    pages: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    bytes_received: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    quality_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    fallback_reason: Mapped[str | None] = mapped_column(String(80))
    budget_used: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    error_code: Mapped[str | None] = mapped_column(String(80))
    safe_error: Mapped[str | None] = mapped_column(String(500))
    decision_version: Mapped[str] = mapped_column(String(40), nullable=False)


class RawItem(TimestampMixin, Base):
    __tablename__ = "raw_items"
    __table_args__ = (
        Index(
            "uq_raw_items_source_external",
            "source_id",
            "external_id",
            unique=True,
            postgresql_where=text("external_id IS NOT NULL"),
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


class Document(TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("word_count >= 0", name="documents_word_count_check"),
        Index("ix_documents_status_created_at", "status", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("raw_items.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str | None] = mapped_column(String(300))
    language: Mapped[str | None] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False, unique=True)
    status: Mapped[DocumentStatus] = mapped_column(enum_column(DocumentStatus, "document_status"))
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(String(500))


class Analysis(TimestampMixin, Base):
    __tablename__ = "analyses"
    __table_args__ = (
        CheckConstraint(
            "(relevance BETWEEN 0 AND 100 OR relevance IS NULL) AND "
            "(importance BETWEEN 0 AND 100 OR importance IS NULL) AND "
            "(novelty BETWEEN 0 AND 100 OR novelty IS NULL) AND "
            "(impact BETWEEN 0 AND 100 OR impact IS NULL) AND "
            "(radar_score BETWEEN 0 AND 100 OR radar_score IS NULL)",
            name="analyses_check",
        ),
        UniqueConstraint("document_id", "radar_id", "pipeline_version"),
        Index("ix_analyses_radar_status_created_at", "radar_id", "status", text("created_at DESC")),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    radar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("radars.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pipeline_version: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(120))
    relevance: Mapped[int | None] = mapped_column(SmallInteger)
    importance: Mapped[int | None] = mapped_column(SmallInteger)
    novelty: Mapped[int | None] = mapped_column(SmallInteger)
    impact: Mapped[int | None] = mapped_column(SmallInteger)
    radar_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    recommendation: Mapped[Recommendation | None] = mapped_column(
        enum_column(Recommendation, "recommendation")
    )
    reason: Mapped[str | None] = mapped_column(String(1000))
    provider: Mapped[str | None] = mapped_column(String(80))
    model: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[AnalysisStatus] = mapped_column(enum_column(AnalysisStatus, "analysis_status"))
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(String(500))


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        CheckConstraint("chunk_index >= 0", name="document_chunks_chunk_index_check"),
        UniqueConstraint("document_id", "chunk_index", "embedding_model"),
        Index(
            "ix_document_chunks_embedding_hnsw_cosine",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class Bookmark(TimestampMixin, Base):
    __tablename__ = "bookmarks"
    __table_args__ = (UniqueConstraint("user_id", "document_id"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    note: Mapped[str | None] = mapped_column(Text)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("user_id", "analysis_id"),
        Index(
            "ix_notifications_user_status_created_at", "user_id", "status", text("created_at DESC")
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analyses.id", ondelete="CASCADE"),
        nullable=False,
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


class AIUsageRecord(Base):
    __tablename__ = "ai_usage_records"
    __table_args__ = (
        CheckConstraint(
            "input_tokens >= 0 AND output_tokens >= 0 AND total_tokens >= 0 AND "
            "estimated_cost >= 0 AND duration_ms >= 0",
            name="ai_usage_records_check",
        ),
        Index("ix_ai_usage_records_user_created_at", "user_id", text("created_at DESC")),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    analysis_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analyses.id", ondelete="SET NULL"), index=True
    )
    task_type: Mapped[str] = mapped_column(String(80), nullable=False)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str] = mapped_column(String(160), nullable=False)
    input_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    output_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    total_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    estimated_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal("0"), server_default="0"
    )
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    succeeded: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
