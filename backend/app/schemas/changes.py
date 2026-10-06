"""Change history read schemas (bounded display evidence; docs/23 §12/§14)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SnapshotRef(BaseModel):
    """Bounded snapshot summary shown alongside a change event (no raw content)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version: int
    title: str | None
    content_hash: str
    quality_score: Decimal | None
    fetched_at: datetime


class ChangeEventResponse(BaseModel):
    id: UUID
    source_id: UUID
    artifact_id: UUID
    artifact_key: str
    canonical_url: str
    change_type: str
    materiality: Decimal
    field_diff: dict[str, Any]
    detector_version: str
    occurred_at: datetime
    previous: SnapshotRef | None
    current: SnapshotRef | None


class ChangeEventPage(BaseModel):
    items: list[ChangeEventResponse]
    page: int
    page_size: int
    total: int
