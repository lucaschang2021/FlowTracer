"""Opportunity REST schemas (docs/24 §8).

Strict response models with frozen enums; the public surface never exposes raw
HTML, prompts, vectors, router traces or secrets. ``extra=forbid`` keeps the
contract closed for generated clients.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

OpportunityStatus = Literal["active", "expired", "removed", "rejected"]
OpportunityRecommendation = Literal["act_now", "review", "watch", "dismiss"]


class OpportunityScoreView(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    radar_id: UUID
    score_version: str
    hard_filter_passed: bool
    disqualifiers: list[Any]
    fit: int | None
    expected_value: int | None
    completion_probability: int | None
    effort_efficiency: int | None
    time_to_delivery: int | None
    competition: int | None
    ambiguity: int | None
    risk: int | None
    overall_score: Decimal | None
    recommendation: OpportunityRecommendation
    reason: str
    scored_at: datetime


class OpportunityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    source_id: UUID
    title: str
    platform: str | None
    description: str
    budget_min: Decimal | None
    budget_max: Decimal | None
    currency: str | None
    skills: list[Any]
    deadline: datetime | None
    published_at: datetime | None
    estimated_effort_hours: Decimal | None
    delivery_type: str | None
    profile_version: str
    source_url: str
    status: OpportunityStatus
    created_at: datetime
    updated_at: datetime
    score: OpportunityScoreView | None = None

    @classmethod
    def from_fact(cls, item: Any, score: Any | None = None) -> OpportunityResponse:
        response = cls.model_validate(item)
        if score is not None:
            response = response.model_copy(
                update={"score": OpportunityScoreView.model_validate(score)}
            )
        return response


class OpportunityPage(BaseModel):
    items: list[OpportunityResponse]
    page: int
    page_size: int
    total: int


class ActionPayloadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opportunity_id: UUID
    payload_version: str
    payload: dict[str, Any]
    payload_hash: str
    generated_at: datetime

    @classmethod
    def from_fact(cls, item: Any, payload: Any) -> ActionPayloadResponse:
        return cls(
            opportunity_id=item.id,
            payload_version=payload.payload_version,
            payload=payload.payload,
            payload_hash=payload.payload_hash,
            generated_at=payload.generated_at,
        )
