from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.entities import CollectionRunStatus, CollectionTriggerType, RawItemStatus


class CollectionQueuedResponse(BaseModel):
    run_id: UUID
    status: CollectionRunStatus


class CollectionRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_id: UUID
    trigger_type: CollectionTriggerType
    status: CollectionRunStatus
    started_at: datetime | None
    finished_at: datetime | None
    fetched_count: int
    created_count: int
    duplicate_count: int
    failed_count: int
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class CollectionRunPage(BaseModel):
    items: list[CollectionRunResponse]
    page: int
    page_size: int
    total: int


class RawItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_id: UUID
    collection_run_id: UUID
    external_id: str | None
    canonical_url: str
    title: str | None
    published_at: datetime | None
    fetched_at: datetime
    content_type: str | None
    content_hash: str
    metadata: dict[str, Any] = Field(validation_alias="item_metadata")
    status: RawItemStatus
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class RawItemPage(BaseModel):
    items: list[RawItemResponse]
    page: int
    page_size: int
    total: int
