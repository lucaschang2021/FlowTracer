from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.entities import Recommendation


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _normalize_note(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if len(normalized) > 4000:
        raise ValueError("note must contain at most 4000 characters")
    return normalized


class BookmarkCreate(StrictModel):
    document_id: UUID
    note: str | None = None

    _note = field_validator("note")(_normalize_note)


class BookmarkUpdate(StrictModel):
    note: str | None

    _note = field_validator("note")(_normalize_note)


class BookmarkItem(BaseModel):
    id: UUID
    document_id: UUID
    note: str | None
    title: str
    canonical_url: str
    analysis_id: UUID | None
    radar_id: UUID | None
    summary: str | None
    category: str | None
    radar_score: Decimal | None
    recommendation: Recommendation | None
    created_at: datetime
    updated_at: datetime


class BookmarkPage(BaseModel):
    items: list[BookmarkItem]
    page: int
    page_size: int
    total: int


class MemorySearchRequest(StrictModel):
    query: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(10, ge=1, le=50)
    radar_id: UUID | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    bookmarked_only: bool = False

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("query must not be blank")
        return normalized

    @model_validator(mode="after")
    def validate_dates(self) -> MemorySearchRequest:
        if self.date_from is not None and self.date_to is not None:
            if self.date_from > self.date_to:
                raise ValueError("date_from must not be after date_to")
        return self


class MemorySearchItem(BaseModel):
    analysis_id: UUID
    document_id: UUID
    radar_id: UUID
    title: str
    canonical_url: str
    summary: str | None
    category: str | None
    radar_score: Decimal | None
    recommendation: Recommendation | None
    excerpt: str
    similarity: Decimal
    occurred_at: datetime
    bookmarked: bool


class MemorySearchResponse(BaseModel):
    items: list[MemorySearchItem]
    query: str
    top_k: int
