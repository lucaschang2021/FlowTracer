from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.entities import CollectionRunStatus, NotificationPriority, Recommendation


class StrictEventModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CollectionUpdatedData(StrictEventModel):
    collection_run_id: UUID
    source_id: UUID
    status: CollectionRunStatus
    fetched_count: int
    created_count: int
    duplicate_count: int
    failed_count: int


class AnalysisCompletedData(StrictEventModel):
    analysis_id: UUID
    document_id: UUID
    radar_id: UUID
    radar_score: Decimal
    recommendation: Recommendation


class NotificationCreatedData(StrictEventModel):
    notification_id: UUID
    analysis_id: UUID
    priority: NotificationPriority


EventData = CollectionUpdatedData | AnalysisCompletedData | NotificationCreatedData


class EventEnvelope(StrictEventModel):
    event_id: UUID
    event_type: Literal["collection.updated", "analysis.completed", "notification.created"]
    occurred_at: datetime
    data: EventData
