from __future__ import annotations

import ipaddress
import json
import re
import unicodedata
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any, Literal, Self, cast
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    field_serializer,
    field_validator,
    model_validator,
)

from app.models.entities import (
    AcquisitionMode,
    DiscoveryMode,
    RadarType,
    ResourceStatus,
    SourceFamily,
    SourceType,
)


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


_SECRET_KEY_PARTS = (
    "authorization",
    "browser",
    "cookie",
    "token",
    "password",
    "secret",
    "proxy",
    "header",
)
_MIME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9!#$&^_.+-]*/[a-z0-9][a-z0-9!#$&^_.+-]*$")
_DEFAULT_CONTENT_TYPES = [
    "text/html",
    "application/rss+xml",
    "application/atom+xml",
    "application/xml",
    "text/xml",
]


def _has_control(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)


def _validate_public_json(value: Any, *, path: str = "config") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if _has_control(str(key)):
                raise ValueError(f"{path} must not contain control characters")
            normalized = str(key).casefold().replace("-", "_")
            if any(part in normalized for part in _SECRET_KEY_PARTS):
                raise ValueError(f"{path} must not contain secret fields")
            _validate_public_json(item, path=f"{path}.{key}")
    elif isinstance(value, list):
        for item in value:
            _validate_public_json(item, path=path)
    elif isinstance(value, str) and _has_control(value):
        raise ValueError(f"{path} must not contain control characters")


def sanitize_legacy_config(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: sanitize_legacy_config(item)
            for key, item in value.items()
            if not any(part in str(key).casefold().replace("-", "_") for part in _SECRET_KEY_PARTS)
        }
    if isinstance(value, list):
        return [sanitize_legacy_config(item) for item in value]
    if isinstance(value, str) and _has_control(value):
        return ""
    return value


def validate_config(value: dict[str, Any]) -> dict[str, Any]:
    _validate_public_json(value)
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


class ContentProfile(StrEnum):
    GENERIC = "generic"
    ARTICLE = "article"
    DOCUMENT = "document"
    FEED = "feed"
    LISTING = "listing"
    EVENT = "event"
    OPPORTUNITY = "opportunity"


class SourcePriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class RobotsMode(StrEnum):
    RESPECT = "respect"
    DENY_IF_UNAVAILABLE = "deny_if_unavailable"


class ChangeDetectionProfile(StrictSchema):
    enabled: StrictBool = True
    materiality_threshold: Decimal = Decimal("0.1500")
    semantic_enabled: StrictBool = False

    @field_validator("materiality_threshold", mode="before")
    @classmethod
    def finite_decimal(cls, value: Any) -> Decimal:
        if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
            raise ValueError("materiality_threshold must be a finite decimal")
        try:
            decimal_value = Decimal(str(value))
        except InvalidOperation:
            raise ValueError("materiality_threshold must be a finite decimal") from None
        if not decimal_value.is_finite() or not Decimal("0") <= decimal_value <= Decimal("1"):
            raise ValueError("materiality_threshold must be between 0 and 1")
        exponent = decimal_value.as_tuple().exponent
        if not isinstance(exponent, int) or exponent < -4:
            raise ValueError("materiality_threshold must have at most four decimal places")
        return decimal_value.quantize(Decimal("0.0001"))

    @field_serializer("materiality_threshold", when_used="json")
    def serialize_materiality_threshold(self, value: Decimal) -> float:
        return float(value)


class ResourceBudgetProfile(StrictSchema):
    max_requests: StrictInt = Field(10, ge=1, le=1000)
    max_pages: StrictInt = Field(1, ge=1, le=100)
    max_depth: StrictInt = Field(0, ge=0, le=3)
    max_duration_seconds: StrictInt = Field(120, ge=5, le=900)
    max_concurrency: StrictInt = Field(1, ge=1, le=8)
    max_browser_pages: StrictInt = Field(0, ge=0, le=10)
    max_retries_per_target: StrictInt = Field(2, ge=0, le=2)
    max_total_bytes: StrictInt = Field(5_242_880, ge=1024, le=52_428_800)


def _normalize_mime_types(values: list[str]) -> list[str]:
    if not 1 <= len(values) <= 16:
        raise ValueError("allowed_content_types must contain 1..16 items")
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = value.strip().lower()
        if not 1 <= len(item) <= 160 or not item.isascii() or not _MIME_PATTERN.fullmatch(item):
            raise ValueError("allowed_content_types contains an invalid MIME type")
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _normalize_paths(values: list[str]) -> list[str]:
    if len(values) > 64:
        raise ValueError("path lists must contain at most 64 items")
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = unicodedata.normalize("NFC", value.strip())
        parsed = urlsplit(item)
        if (
            not 1 <= len(item) <= 512
            or not item.startswith("/")
            or _has_control(item)
            or parsed.scheme
            or parsed.netloc
            or parsed.query
            or parsed.fragment
            or "*" in item
            or "\\" in item
        ):
            raise ValueError("path lists contain an invalid path prefix")
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


class SitePolicyProfile(StrictSchema):
    robots_mode: RobotsMode = RobotsMode.RESPECT
    crawl_delay_ms: StrictInt = Field(1000, ge=0, le=60_000)
    requests_per_minute: StrictInt = Field(30, ge=1, le=60)
    max_parallel_requests: StrictInt = Field(1, ge=1, le=8)
    allowed_content_types: list[str] = Field(default_factory=lambda: list(_DEFAULT_CONTENT_TYPES))
    allow_paths: list[str] = Field(default_factory=list)
    deny_paths: list[str] = Field(default_factory=list)

    @field_validator("allowed_content_types")
    @classmethod
    def content_types(cls, value: list[str]) -> list[str]:
        return _normalize_mime_types(value)

    @field_validator("allow_paths", "deny_paths")
    @classmethod
    def paths(cls, value: list[str]) -> list[str]:
        return _normalize_paths(value)


class FamilyOptionsV1(StrictSchema):
    pass


def _normalize_domains(values: list[str]) -> list[str]:
    if len(values) > 32:
        raise ValueError("approved_domains must contain at most 32 items")
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        candidate = value.strip().rstrip(".")
        if not candidate or _has_control(candidate):
            raise ValueError("approved_domains contains an invalid hostname")
        if any(character in candidate for character in "/?#@:*[]"):
            raise ValueError("approved_domains contains an invalid hostname")
        try:
            ascii_host = candidate.encode("idna").decode("ascii").lower()
        except UnicodeError:
            raise ValueError("approved_domains contains an invalid hostname") from None
        if (
            not 1 <= len(ascii_host) <= 253
            or "*" in ascii_host
            or any(
                not label
                or len(label) > 63
                or label.startswith("-")
                or label.endswith("-")
                or not all(character.isalnum() or character == "-" for character in label)
                for label in ascii_host.split(".")
            )
        ):
            raise ValueError("approved_domains contains an invalid hostname")
        try:
            ipaddress.ip_address(ascii_host)
        except ValueError:
            pass
        else:
            raise ValueError("approved_domains contains an invalid hostname")
        if ascii_host not in seen:
            seen.add(ascii_host)
            result.append(ascii_host)
    return result


class AcquisitionProfileV1(StrictSchema):
    content_profile: ContentProfile = ContentProfile.GENERIC
    priority: SourcePriority = SourcePriority.NORMAL
    allow_browser: StrictBool = False
    change_detection: ChangeDetectionProfile = Field(default_factory=ChangeDetectionProfile)
    resource_budget: ResourceBudgetProfile = Field(default_factory=ResourceBudgetProfile)
    site_policy: SitePolicyProfile = Field(default_factory=SitePolicyProfile)
    approved_domains: list[str] = Field(default_factory=list)
    family_options: FamilyOptionsV1 = Field(default_factory=FamilyOptionsV1)

    @field_validator("approved_domains")
    @classmethod
    def domains(cls, value: list[str]) -> list[str]:
        return _normalize_domains(value)

    @model_validator(mode="after")
    def validate_profile(self) -> Self:
        serialized = self.model_dump_json().encode("utf-8")
        if len(serialized) > 16 * 1024:
            raise ValueError("acquisition_profile must not exceed 16 KiB")
        return self

    def storage_dict(self) -> dict[str, Any]:
        return cast(dict[str, Any], json.loads(self.model_dump_json()))


class SourceCreate(StrictSchema):
    name: str = Field(min_length=1, max_length=160)
    source_type: SourceType
    url: str = Field(min_length=1, max_length=2048)
    poll_interval_minutes: int = Field(60, ge=15, le=10080)
    config: dict[str, Any] = Field(default_factory=dict)
    source_family: SourceFamily = SourceFamily.GENERIC_WEB
    acquisition_mode: AcquisitionMode = AcquisitionMode.AUTO
    discovery_mode: DiscoveryMode = DiscoveryMode.SINGLE_PAGE
    profile_version: Literal["acq-source-v1"] = "acq-source-v1"
    acquisition_profile: AcquisitionProfileV1 = Field(default_factory=AcquisitionProfileV1)

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
    source_family: SourceFamily | None = None
    acquisition_mode: AcquisitionMode | None = None
    discovery_mode: DiscoveryMode | None = None
    profile_version: Literal["acq-source-v1"] | None = None
    acquisition_profile: AcquisitionProfileV1 | None = None

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
    source_family: SourceFamily
    acquisition_mode: AcquisitionMode
    discovery_mode: DiscoveryMode
    profile_version: Literal["acq-source-v1"]
    acquisition_profile: AcquisitionProfileV1
    created_at: datetime
    updated_at: datetime

    @field_validator("config", mode="before")
    @classmethod
    def redact_legacy_config(cls, value: Any) -> dict[str, Any]:
        return (
            cast(dict[str, Any], sanitize_legacy_config(value)) if isinstance(value, dict) else {}
        )


class SourcePage(BaseModel):
    items: list[SourceResponse]
    page: int
    page_size: int
    total: int
