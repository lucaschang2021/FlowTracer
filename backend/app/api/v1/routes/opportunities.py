from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import User, get_current_user, get_session
from app.schemas.errors import documented_error
from app.schemas.opportunity import (
    ActionPayloadResponse,
    OpportunityPage,
    OpportunityResponse,
)
from app.services import opportunity_queries

OpportunityStatusParam = Literal["active", "expired", "removed", "rejected"]
OpportunityRecommendationParam = Literal["act_now", "review", "watch", "dismiss"]

router = APIRouter(
    responses={
        401: documented_error("Invalid access token"),
        404: documented_error("Resource not found"),
        422: documented_error("Invalid request"),
    }
)


@router.get("", response_model=OpportunityPage)
async def list_opportunities(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    radar_id: UUID | None = None,
    status_filter: OpportunityStatusParam | None = Query(None, alias="status"),
    recommendation: OpportunityRecommendationParam | None = None,
    min_score: Decimal | None = Query(None, ge=0, le=100),
    currency: str | None = Query(None, min_length=3, max_length=3, pattern="^[A-Z]{3}$"),
    deadline_before: datetime | None = Query(None, alias="deadline"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OpportunityPage:
    rows, total = await opportunity_queries.list_opportunities(
        session,
        user_id=user.id,
        page=page,
        page_size=page_size,
        radar_id=radar_id,
        status=status_filter,
        recommendation=recommendation,
        min_score=min_score,
        currency=currency,
        deadline_before=deadline_before,
    )
    return OpportunityPage(
        items=[OpportunityResponse.from_fact(item, score) for item, score in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{opportunity_id}", response_model=OpportunityResponse)
async def get_opportunity(
    opportunity_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OpportunityResponse:
    item, scores = await opportunity_queries.opportunity_detail(
        session, user_id=user.id, opportunity_id=opportunity_id
    )
    return OpportunityResponse.from_fact(item, scores[0] if scores else None)


@router.get("/{opportunity_id}/action-payload", response_model=ActionPayloadResponse)
async def get_action_payload(
    opportunity_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ActionPayloadResponse:
    item, payload = await opportunity_queries.action_payload_for(
        session, user_id=user.id, opportunity_id=opportunity_id
    )
    return ActionPayloadResponse.from_fact(item, payload)
