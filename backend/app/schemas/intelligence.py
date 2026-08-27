from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from app.models.entities import AnalysisStatus, Recommendation


class IntelligenceItem(BaseModel):
    id: UUID
    document_id: UUID
    radar_id: UUID
    title: str
    canonical_url: str
    summary: str | None
    category: str | None
    relevance: int | None
    importance: int | None
    novelty: int | None
    impact: int | None
    radar_score: Decimal | None
    recommendation: Recommendation | None
    reason: str | None
    status: AnalysisStatus
    error_code: str | None
    error_message: str | None
    pipeline_version: str
    prompt_version: str
    provider: str | None
    model: str | None
    created_at: datetime
    updated_at: datetime


class IntelligenceDetail(IntelligenceItem):
    content: str
    author: str | None
    language: str | None
    word_count: int


class IntelligencePage(BaseModel):
    items: list[IntelligenceItem]
    page: int
    page_size: int
    total: int


class AnalysisRetryResponse(BaseModel):
    analysis_id: UUID
    status: AnalysisStatus
