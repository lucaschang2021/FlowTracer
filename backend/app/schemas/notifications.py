from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.entities import NotificationPriority, NotificationStatus


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    analysis_id: UUID
    title: str
    content: str
    priority: NotificationPriority
    reason: str
    url: str | None
    status: NotificationStatus
    created_at: datetime
    read_at: datetime | None


class NotificationPage(BaseModel):
    items: list[NotificationResponse]
    page: int
    page_size: int
    total: int


class NotificationReadAllResponse(BaseModel):
    updated_count: int
    read_at: datetime
