from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.entities import RadarType, ResourceStatus, SourceType


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _trim_required(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("must not be empty")
    return normalized


def _normalize_optional_text(value: Any) -> Any:
    if value is None or not isinstance(value, str):
        return value
    normalized = value.strip()
    return normalized or None


def _normalize_list(values: list[str], *, item_limit: int, list_limit: int) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = value.strip()
        if not item or len(item) > item_limit:
            raise ValueError(f"items must contain 1..{item_limit} characters after trimming")
        identity = item.casefold()
        if identity not in seen:
            seen.add(identity)
            normalized.append(item)
    if len(normalized) > list_limit:
        raise ValueError(f"must contain at most {list_limit} items after deduplication")
    return normalized


class RadarFields(StrictSchema):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    goal: str = Field(min_length=1, max_length=4000)
    radar_type: RadarType
    categories: list[str] = Field(default_factory=list, max_length=20)
    keywords: list[str] = Field(default_factory=list, max_length=50)
    notification_threshold: int = Field(75, ge=0, le=100)

    @field_validator("name", "goal", mode="before")
    @classmethod
    def trim_required(cls, value: Any) -> Any:
        return _trim_required(value) if isinstance(value, str) else value

    @field_validator("description", mode="before")
    @classmethod
    def trim_description(cls, value: Any) -> Any:
        return _normalize_optional_text(value)

    @field_validator("categories")
    @classmethod
    def normalize_categories(cls, value: list[str]) -> list[str]:
        return _normalize_list(value, item_limit=80, list_limit=20)

    @field_validator("keywords")
    @classmethod
    def normalize_keywords(cls, value: list[str]) -> list[str]:
        return _normalize_list(value, item_limit=120, list_limit=50)


class RadarCreate(RadarFields):
    pass


class RadarUpdate(StrictSchema):
    name: str | None = Field(None, min_length=1, max_length=120)
    description: str | None = None
    goal: str | None = Field(None, min_length=1, max_length=4000)
    radar_type: RadarType | None = None
    categories: list[str] | None = Field(None, max_length=20)
    keywords: list[str] | None = Field(None, max_length=50)
    notification_threshold: int | None = Field(None, ge=0, le=100)

    @field_validator("name", "goal", mode="before")
    @classmethod
    def trim_required(cls, value: Any) -> Any:
        return _trim_required(value) if isinstance(value, str) else value

    @field_validator("description", mode="before")
    @classmethod
    def trim_description(cls, value: Any) -> Any:
        return _normalize_optional_text(value)

    @field_validator("categories")
    @classmethod
    def normalize_categories(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else _normalize_list(value, item_limit=80, list_limit=20)

    @field_validator("keywords")
    @classmethod
    def normalize_keywords(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else _normalize_list(value, item_limit=120, list_limit=50)

    @model_validator(mode="after")
    def require_field(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        nullable = {"description"}
        if any(getattr(self, field) is None for field in self.model_fields_set - nullable):
            raise ValueError("updated fields must not be null")
        return self


class RadarResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    goal: str
    radar_type: RadarType
    categories: list[str]
    keywords: list[str]
    status: ResourceStatus
    notification_threshold: int
    created_at: datetime
    updated_at: datetime


class RadarPage(BaseModel):
    items: list[RadarResponse]
    page: int
    page_size: int
    total: int


def validate_config(value: dict[str, Any]) -> dict[str, Any]:
    try:
        serialized = json.dumps(
            value,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        raise ValueError("config must contain only standard JSON values") from None
    if len(serialized) > 16 * 1024:
        raise ValueError("config must not exceed 16 KiB")
    return value


class SourceCreate(StrictSchema):
    name: str = Field(min_length=1, max_length=160)
    source_type: SourceType
    url: str = Field(min_length=1, max_length=2048)
    poll_interval_minutes: int = Field(60, ge=15, le=10080)
    config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name", "url", mode="before")
    @classmethod
    def trim_required(cls, value: Any) -> Any:
        return _trim_required(value) if isinstance(value, str) else value

    @field_validator("config")
    @classmethod
    def config_size(cls, value: dict[str, Any]) -> dict[str, Any]:
        return validate_config(value)


class SourceUpdate(StrictSchema):
    name: str | None = Field(None, min_length=1, max_length=160)
    url: str | None = Field(None, min_length=1, max_length=2048)
    poll_interval_minutes: int | None = Field(None, ge=15, le=10080)
    config: dict[str, Any] | None = None

    @field_validator("name", "url", mode="before")
    @classmethod
    def trim_required(cls, value: Any) -> Any:
        return _trim_required(value) if isinstance(value, str) else value

    @field_validator("config")
    @classmethod
    def config_size(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return None if value is None else validate_config(value)

    @model_validator(mode="after")
    def require_field(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("updated fields must not be null")
        return self


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    source_type: SourceType
    url: str
    normalized_url: str
    poll_interval_minutes: int
    status: ResourceStatus
    last_fetched_at: datetime | None
    next_fetch_at: datetime | None
    config: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class SourcePage(BaseModel):
    items: list[SourceResponse]
    page: int
    page_size: int
    total: int
