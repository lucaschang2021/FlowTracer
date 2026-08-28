from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import AppError
from app.models.entities import (
    Analysis,
    AnalysisStatus,
    Document,
    Notification,
    NotificationPriority,
    NotificationStatus,
    Radar,
    ResourceStatus,
)
from app.services.events import EventPublisher, build_event, publish_safely


def notification_priority(score: Decimal) -> NotificationPriority:
    if score >= Decimal("95"):
        return NotificationPriority.CRITICAL
    if score >= Decimal("85"):
        return NotificationPriority.HIGH
    return NotificationPriority.NORMAL


def _resource_not_found() -> AppError:
    return AppError(status_code=404, code="resource_not_found", message="Resource not found")


async def dispatch_notifications(
    factory: async_sessionmaker[AsyncSession],
    publisher: EventPublisher | None = None,
    *,
    analysis_id: UUID | None = None,
    batch_size: int = 100,
) -> int:
    async with factory() as session:
        predicates = [
            Analysis.status == AnalysisStatus.COMPLETED,
            Analysis.radar_score.is_not(None),
            Radar.status == ResourceStatus.ACTIVE,
            Radar.deleted_at.is_(None),
            Analysis.radar_score >= Radar.notification_threshold,
            Notification.id.is_(None),
        ]
        if analysis_id is not None:
            predicates.append(Analysis.id == analysis_id)
        eligible = (
            await session.execute(
                select(Analysis, Radar, Document)
                .join(Radar, Radar.id == Analysis.radar_id)
                .join(Document, Document.id == Analysis.document_id)
                .outerjoin(
                    Notification,
                    (Notification.user_id == Radar.user_id)
                    & (Notification.analysis_id == Analysis.id),
                )
                .where(*predicates)
                .order_by(Analysis.created_at.asc(), Analysis.id.asc())
                .with_for_update(of=Analysis, skip_locked=True)
                .limit(batch_size)
            )
        ).all()
        created: list[tuple[UUID, UUID, UUID, NotificationPriority, datetime]] = []
        for analysis, radar, document in eligible:
            score = analysis.radar_score
            if score is None:
                continue
            priority = notification_priority(score)
            reason = (analysis.reason or "Analysis met the notification threshold")[:1000]
            result = await session.execute(
                insert(Notification)
                .values(
                    user_id=radar.user_id,
                    analysis_id=analysis.id,
                    title=document.title[:240],
                    content=analysis.summary or reason,
                    priority=priority,
                    reason=reason,
                    url=document.canonical_url,
                    status=NotificationStatus.UNREAD,
                )
                .on_conflict_do_nothing(index_elements=["user_id", "analysis_id"])
                .returning(Notification.id, Notification.created_at)
            )
            inserted = result.one_or_none()
            if inserted is not None:
                created.append(
                    (inserted.id, analysis.id, radar.user_id, priority, inserted.created_at)
                )
        await session.commit()
    for notification_id, created_analysis_id, user_id, priority, created_at in created:
        event = build_event(
            "notification.created",
            notification_id,
            created_at.isoformat(),
            {
                "notification_id": notification_id,
                "analysis_id": created_analysis_id,
                "priority": priority,
            },
            occurred_at=created_at,
        )
        await publish_safely(publisher, user_id=user_id, event=event, resource_id=notification_id)
    return len(created)


async def list_notifications(
    session: AsyncSession,
    *,
    user_id: UUID,
    page: int,
    page_size: int,
    status: NotificationStatus | None,
    priority: NotificationPriority | None,
) -> tuple[list[Notification], int]:
    predicates = [Notification.user_id == user_id]
    if status is not None:
        predicates.append(Notification.status == status)
    if priority is not None:
        predicates.append(Notification.priority == priority)
    total = int(
        await session.scalar(select(func.count()).select_from(Notification).where(*predicates)) or 0
    )
    items = list(
        (
            await session.scalars(
                select(Notification)
                .where(*predicates)
                .order_by(Notification.created_at.desc(), Notification.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    return items, total


async def mark_notification_read(
    session: AsyncSession,
    *,
    user_id: UUID,
    notification_id: UUID,
    now: datetime | None = None,
) -> Notification:
    notification = await session.scalar(
        select(Notification)
        .where(Notification.id == notification_id, Notification.user_id == user_id)
        .with_for_update()
    )
    if notification is None:
        raise _resource_not_found()
    if notification.status == NotificationStatus.UNREAD:
        notification.status = NotificationStatus.READ
        notification.read_at = now or datetime.now(UTC)
        await session.commit()
        await session.refresh(notification)
    return notification


async def mark_all_notifications_read(
    session: AsyncSession,
    *,
    user_id: UUID,
    now: datetime | None = None,
) -> tuple[int, datetime]:
    read_at = now or datetime.now(UTC)
    result = await session.scalars(
        update(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.status == NotificationStatus.UNREAD,
        )
        .values(status=NotificationStatus.READ, read_at=read_at)
        .returning(Notification.id)
    )
    updated_count = len(list(result.all()))
    await session.commit()
    return updated_count, read_at
