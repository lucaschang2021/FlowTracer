from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Literal

from app.models.entities import SourceFamily

SCHEMA_VERSION = "extraction-evidence-v1"
EXTRACTOR_VERSION = "static-extractor-v1"
QUALITY_VERSION = "extraction-quality-v1"


@dataclass(frozen=True, slots=True)
class FieldEvidence:
    present: bool
    evidence_path: str
    confidence: Decimal


@dataclass(frozen=True, slots=True)
class ExtractionMetrics:
    meaningful_chars: int
    visible_chars: int
    navigation_chars: int
    executable_script_count: int


@dataclass(frozen=True, slots=True)
class ExtractionEvidence:
    source_family: SourceFamily
    fields: dict[str, FieldEvidence]
    metrics: ExtractionMetrics
    quality_score: Decimal | None
    quality_bucket: Literal["low", "marginal", "acceptable", "unscored"]
    diagnostic_codes: tuple[str, ...] = ()
    schema_version: str = SCHEMA_VERSION
    extractor_version: str = EXTRACTOR_VERSION
    quality_version: str = QUALITY_VERSION

    def compact_json(self) -> bytes:
        payload = asdict(self)
        payload["source_family"] = self.source_family.value
        return json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class ExtractionObservation:
    evidence: ExtractionEvidence
    safe_metadata: dict[str, str]
    links: tuple[str, ...]
    title: str | None = None
    text: str = ""
    author: str | None = None
    published_at: str | None = None
    canonical_url: str | None = None
