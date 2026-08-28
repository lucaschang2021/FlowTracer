from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_session
from app.models.entities import NotificationPriority, NotificationStatus, User
from app.schemas.errors import documented_error
from app.schemas.notifications import (
    NotificationPage,
    NotificationReadAllResponse,
    NotificationResponse,
)
from app.services import notifications

router = APIRouter(
    responses={
        401: documented_error("Invalid access token"),
        404: documented_error("Resource not found"),
        422: documented_error("Invalid request"),
    }
)


@router.get("", response_model=NotificationPage)
async def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: NotificationStatus | None = Query(None, alias="status"),
    priority: NotificationPriority | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> NotificationPage:
    items, total = await notifications.list_notifications(
        session,
        user_id=user.id,
        page=page,
        page_size=page_size,
        status=status_filter,
        priority=priority,
    )
    return NotificationPage(
        items=[NotificationResponse.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("/read-all", response_model=NotificationReadAllResponse)
async def read_all_notifications(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> NotificationReadAllResponse:
    updated_count, read_at = await notifications.mark_all_notifications_read(
        session, user_id=user.id
    )
    return NotificationReadAllResponse(updated_count=updated_count, read_at=read_at)


@router.post("/{notification_id}/read", response_model=NotificationResponse)
async def read_notification(
    notification_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> NotificationResponse:
    item = await notifications.mark_notification_read(
        session, user_id=user.id, notification_id=notification_id
    )
    return NotificationResponse.model_validate(item)
