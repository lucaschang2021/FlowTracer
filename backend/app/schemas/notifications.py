from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.entities import NotificationPriority, NotificationStatus

NotificationKind = Literal["intelligence", "opportunity"]

_FACT_FIELDS = (
    "id",
    "analysis_id",
    "title",
    "content",
    "priority",
    "reason",
    "url",
    "status",
    "created_at",
    "read_at",
)


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: NotificationKind
    analysis_id: UUID | None
    opportunity_id: UUID | None
    title: str
    content: str
    priority: NotificationPriority
    reason: str
    url: str | None
    status: NotificationStatus
    created_at: datetime
    read_at: datetime | None

    @classmethod
    def from_fact(cls, fact: Any, opportunity_id: UUID | None = None) -> NotificationResponse:
        data = {field: getattr(fact, field) for field in _FACT_FIELDS}
        is_opportunity = getattr(fact, "opportunity_score_id", None) is not None
        data["kind"] = "opportunity" if is_opportunity else "intelligence"
        data["opportunity_id"] = opportunity_id
        return cls(**data)


class NotificationPage(BaseModel):
    items: list[NotificationResponse]
    page: int
    page_size: int
    total: int


class NotificationReadAllResponse(BaseModel):
    updated_count: int
    read_at: datetime
