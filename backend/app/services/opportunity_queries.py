"""ACQ-1G opportunity read models: list, detail and action payload.

Ownership is enforced on every query; missing or foreign rows raise the unified
404 ``opportunity_not_found``, and an existing opportunity without an immutable
payload raises ``action_payload_unavailable``.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.opportunity import (
    OpportunityActionPayload,
    OpportunityItem,
    OpportunityScore,
)


def _not_found() -> AppError:
    return AppError(status_code=404, code="opportunity_not_found", message="Opportunity not found")


def _latest_score_id_subquery(radar_id: UUID | None) -> object:
    statement = (
        select(OpportunityScore.id)
        .where(OpportunityScore.opportunity_id == OpportunityItem.id)
        .order_by(OpportunityScore.scored_at.desc(), OpportunityScore.id.desc())
        .limit(1)
        .correlate(OpportunityItem)
    )
    if radar_id is not None:
        statement = statement.where(OpportunityScore.radar_id == radar_id)
    return statement.scalar_subquery()


async def list_opportunities(
    session: AsyncSession,
    *,
    user_id: UUID,
    page: int,
    page_size: int,
    radar_id: UUID | None,
    status: str | None,
    recommendation: str | None,
    min_score: Decimal | None,
    currency: str | None,
    deadline_before: datetime | None,
) -> tuple[list[tuple[OpportunityItem, OpportunityScore | None]], int]:
    latest = _latest_score_id_subquery(radar_id)
    predicates = [OpportunityItem.user_id == user_id]
    if status is not None:
        predicates.append(OpportunityItem.status == status)
    if currency is not None:
        predicates.append(OpportunityItem.currency == currency)
    if deadline_before is not None:
        predicates.append(OpportunityItem.deadline.is_not(None))
        predicates.append(OpportunityItem.deadline <= deadline_before)
    if recommendation is not None:
        predicates.append(OpportunityScore.recommendation == recommendation)
    if min_score is not None:
        predicates.append(OpportunityScore.overall_score >= min_score)
    total = int(
        await session.scalar(
            select(func.count())
            .select_from(OpportunityItem)
            .outerjoin(OpportunityScore, OpportunityScore.id == latest)
            .where(*predicates)
        )
        or 0
    )
    rows = (
        await session.execute(
            select(OpportunityItem, OpportunityScore)
            .outerjoin(OpportunityScore, OpportunityScore.id == latest)
            .where(*predicates)
            .order_by(OpportunityItem.created_at.desc(), OpportunityItem.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return [(row[0], row[1]) for row in rows], total


async def opportunity_detail(
    session: AsyncSession, *, user_id: UUID, opportunity_id: UUID
) -> tuple[OpportunityItem, list[OpportunityScore]]:
    item = await session.scalar(
        select(OpportunityItem).where(
            OpportunityItem.id == opportunity_id, OpportunityItem.user_id == user_id
        )
    )
    if item is None:
        raise _not_found()
    scores = list(
        (
            await session.scalars(
                select(OpportunityScore)
                .where(OpportunityScore.opportunity_id == opportunity_id)
                .order_by(OpportunityScore.scored_at.desc(), OpportunityScore.id.desc())
            )
        ).all()
    )
    return item, scores


async def action_payload_for(
    session: AsyncSession, *, user_id: UUID, opportunity_id: UUID
) -> tuple[OpportunityItem, OpportunityActionPayload]:
    item = await session.scalar(
        select(OpportunityItem).where(
            OpportunityItem.id == opportunity_id, OpportunityItem.user_id == user_id
        )
    )
    if item is None:
        raise _not_found()
    payload = await session.scalar(
        select(OpportunityActionPayload)
        .join(
            OpportunityScore,
            OpportunityScore.id == OpportunityActionPayload.opportunity_score_id,
        )
        .where(OpportunityScore.opportunity_id == opportunity_id)
        .order_by(OpportunityActionPayload.generated_at.desc(), OpportunityActionPayload.id.desc())
        .limit(1)
    )
    if payload is None:
        raise AppError(
            status_code=404,
            code="action_payload_unavailable",
            message="Action payload is not available",
        )
    return item, payload
