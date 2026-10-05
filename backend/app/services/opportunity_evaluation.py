"""ACQ-1G opportunity evaluation (docs/24 §5/§6, ADR-025/ADR-037).

Flow per (opportunity, radar): claim -> hard filter (no AI before it) -> bounded
provider call (<=3 real calls, 2/4s backoff, one repair) -> score + immutable
action payload + notification fact in one transaction. Remote calls never run
inside a database transaction or lock; identical replays are no-ops guarded by the
score triple and partial unique indexes.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CursorResult, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.logging import get_logger
from app.domains.opportunity_policy import (
    PAYLOAD_VERSION,
    SCORE_VERSION,
    Dimensions,
    EvaluationOutput,
    EvaluationOutputError,
    HardFilterOutcome,
    OpportunityFacts,
    hard_filter,
    notification_qualified,
    overall_score,
    parse_evaluation,
    recommendation_for,
)
from app.domains.provider_ports import (
    OpportunityEvaluationProvider,
    OpportunityEvaluationRequest,
    ProviderError,
    ProviderResponse,
)
from app.models.entities import AIUsageRecord, Radar, RadarSource, RadarType, ResourceStatus
from app.models.notification import Notification, NotificationStatus
from app.models.opportunity import (
    OpportunityActionPayload,
    OpportunityItem,
    OpportunityScore,
)
from app.services.intelligence import calculate_cost
from app.services.notifications import notification_priority
from app.services.opportunity_payload import build_action_payload, payload_digest

EVAL_BUDGET_SECONDS = 120.0
MAX_EVAL_CALLS = 3
MAX_REASON_CHARS = 1000


@dataclass(frozen=True, slots=True)
class _Target:
    opportunity_id: UUID
    radar_id: UUID
    user_id: UUID
    radar_threshold: int
    request: OpportunityEvaluationRequest
    facts: OpportunityFacts


@dataclass(frozen=True, slots=True)
class _CallResult:
    evaluation: EvaluationOutput | None
    response: ProviderResponse | None
    error: ProviderError | None


def facts_for_item(item: OpportunityItem) -> OpportunityFacts:
    """Rebuild the bounded fact set from persisted item columns (no guessing)."""
    metadata = item.client_metadata or {}
    meetings = metadata.get("required_meetings")
    maintenance = metadata.get("maintenance_required")
    return OpportunityFacts(
        title=item.title,
        description=item.description,
        source_url=item.source_url,
        platform=item.platform,
        budget_min=item.budget_min,
        budget_max=item.budget_max,
        currency=item.currency,
        skills=tuple(str(skill) for skill in (item.skills or ())),
        deadline=item.deadline,
        published_at=item.published_at,
        estimated_effort_hours=item.estimated_effort_hours,
        delivery_type=item.delivery_type,
        required_meetings=(
            meetings if isinstance(meetings, int) and not isinstance(meetings, bool) else None
        ),
        maintenance_required=maintenance if isinstance(maintenance, bool) else None,
    )


def _request_for(
    item: OpportunityItem, radar: Radar, facts: OpportunityFacts
) -> OpportunityEvaluationRequest:
    return OpportunityEvaluationRequest(
        title=item.title,
        description=item.description,
        platform=item.platform,
        budget_min=item.budget_min,
        budget_max=item.budget_max,
        currency=item.currency,
        skills=facts.skills,
        deadline=item.deadline,
        published_at=item.published_at,
        estimated_effort_hours=item.estimated_effort_hours,
        delivery_type=item.delivery_type,
        radar_name=radar.name,
        radar_goal=radar.goal,
        radar_keywords=tuple(str(keyword) for keyword in (radar.keywords or ())),
    )


async def _claim_target(
    factory: async_sessionmaker[AsyncSession], opportunity_id: UUID, radar_id: UUID
) -> _Target | None:
    async with factory() as session:
        scored = await session.scalar(
            select(OpportunityScore.id).where(
                OpportunityScore.opportunity_id == opportunity_id,
                OpportunityScore.radar_id == radar_id,
                OpportunityScore.score_version == SCORE_VERSION,
            )
        )
        if scored is not None:
            return None
        row = (
            await session.execute(
                select(OpportunityItem, Radar)
                .join(RadarSource, RadarSource.source_id == OpportunityItem.source_id)
                .join(Radar, Radar.id == RadarSource.radar_id)
                .where(
                    OpportunityItem.id == opportunity_id,
                    OpportunityItem.status == "active",
                    Radar.id == radar_id,
                    Radar.user_id == OpportunityItem.user_id,
                    Radar.radar_type == RadarType.OPPORTUNITY,
                    Radar.status == ResourceStatus.ACTIVE,
                    Radar.deleted_at.is_(None),
                )
            )
        ).one_or_none()
        if row is None:
            return None
        item, radar = row
        facts = facts_for_item(item)
        return _Target(
            opportunity_id=item.id,
            radar_id=radar.id,
            user_id=item.user_id,
            radar_threshold=radar.notification_threshold,
            request=_request_for(item, radar, facts),
            facts=facts,
        )


async def evaluate_opportunity(
    factory: async_sessionmaker[AsyncSession],
    *,
    opportunity_id: UUID,
    radar_id: UUID,
    provider: OpportunityEvaluationProvider,
    settings: Settings,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    now: datetime | None = None,
) -> str:
    """Evaluate one pair; returns scored | dismissed | skipped | failed."""
    reference = now or datetime.now(UTC)
    target = await _claim_target(factory, opportunity_id, radar_id)
    if target is None:
        return "skipped"
    outcome = hard_filter(target.facts)
    if not outcome.passed:
        await _write_hard_filter_failure(factory, target=target, outcome=outcome, now=reference)
        return "dismissed"
    evaluation = await _run_provider(
        factory, target=target, provider=provider, settings=settings, sleep=sleep
    )
    if evaluation is None:
        return "failed"
    written = await _write_score_bundle(
        factory, target=target, evaluation=evaluation, now=reference
    )
    return "scored" if written else "skipped"


async def _run_provider(
    factory: async_sessionmaker[AsyncSession],
    *,
    target: _Target,
    provider: OpportunityEvaluationProvider,
    settings: Settings,
    sleep: Callable[[float], Awaitable[None]],
) -> EvaluationOutput | None:
    started = time.monotonic()
    calls = 0
    repair_used = False
    repair_error: str | None = None
    last_error = ProviderError("internal_opportunity_error", "Evaluation failed", retryable=False)
    while calls < MAX_EVAL_CALLS:
        remaining = EVAL_BUDGET_SECONDS - (time.monotonic() - started)
        if remaining <= 0:
            last_error = ProviderError("ai_timeout", "AI request timed out", retryable=False)
            break
        calls += 1
        call_started = time.monotonic()
        result = await _call_provider(target.request, provider, repair_error, remaining)
        await _record_usage(
            factory,
            target=target,
            provider=provider,
            settings=settings,
            response=result.response,
            duration_ms=round((time.monotonic() - call_started) * 1000),
            succeeded=result.error is None,
            error_code=None if result.error is None else result.error.code,
        )
        if result.error is None:
            return result.evaluation
        last_error = result.error
        if result.error.code == "ai_invalid_output" and not repair_used and calls < MAX_EVAL_CALLS:
            repair_used = True
            repair_error = "response did not match the required strict JSON schema"
            continue
        if result.error.retryable and calls < MAX_EVAL_CALLS:
            delay = 2.0 if calls == 1 else 4.0
            if time.monotonic() - started + delay < EVAL_BUDGET_SECONDS:
                await sleep(delay)
                continue
        break
    get_logger().warning(
        "opportunity_evaluation_failed",
        message=last_error.safe_message,
        opportunity_id=str(target.opportunity_id),
        radar_id=str(target.radar_id),
        provider=provider.name,
        model=provider.model,
        attempt=calls,
        error_code=last_error.code,
    )
    return None


async def _call_provider(
    request: OpportunityEvaluationRequest,
    provider: OpportunityEvaluationProvider,
    repair_error: str | None,
    remaining_seconds: float,
) -> _CallResult:
    response: ProviderResponse | None = None
    try:
        response = await asyncio.wait_for(
            provider.evaluate(request, repair_error=repair_error), timeout=remaining_seconds
        )
        evaluation = parse_evaluation(_loads(response.content))
        return _CallResult(evaluation, response, None)
    except TimeoutError:
        return _CallResult(None, None, ProviderError("ai_timeout", "Timed out", retryable=True))
    except ProviderError as exc:
        return _CallResult(None, None, exc)
    except (EvaluationOutputError, ValueError, TypeError):
        return _CallResult(
            None,
            response,
            ProviderError("ai_invalid_output", "AI returned invalid output", retryable=False),
        )
    except Exception:
        return _CallResult(
            None,
            None,
            ProviderError(
                "internal_opportunity_error", "Evaluation failed unexpectedly", retryable=False
            ),
        )


def _loads(content: str) -> Any:
    return json.loads(content, parse_constant=_reject_constant)


def _reject_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


async def _record_usage(
    factory: async_sessionmaker[AsyncSession],
    *,
    target: _Target,
    provider: OpportunityEvaluationProvider,
    settings: Settings,
    response: ProviderResponse | None,
    duration_ms: int,
    succeeded: bool,
    error_code: str | None,
) -> None:
    usage = response.usage if response else None
    input_tokens = usage.input_tokens if usage else 0
    output_tokens = usage.output_tokens if usage else 0
    total_tokens = usage.total_tokens if usage else 0
    async with factory() as session:
        session.add(
            AIUsageRecord(
                user_id=target.user_id,
                analysis_id=None,
                task_type="opportunity_evaluation",
                provider=provider.name,
                model=provider.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                estimated_cost=calculate_cost(input_tokens, output_tokens, settings),
                duration_ms=max(0, duration_ms),
                succeeded=succeeded,
                error_code=error_code,
            )
        )
        await session.commit()


def _dismiss_reason(outcome: HardFilterOutcome) -> str:
    return f"Hard filter not passed: {', '.join(outcome.disqualifiers)}"[:MAX_REASON_CHARS]


async def _write_hard_filter_failure(
    factory: async_sessionmaker[AsyncSession],
    *,
    target: _Target,
    outcome: HardFilterOutcome,
    now: datetime,
) -> bool:
    async with factory() as session:
        statement = (
            pg_insert(OpportunityScore)
            .values(
                id=uuid4(),
                opportunity_id=target.opportunity_id,
                radar_id=target.radar_id,
                score_version=SCORE_VERSION,
                hard_filter_passed=False,
                disqualifiers=list(outcome.disqualifiers),
                recommendation="dismiss",
                reason=_dismiss_reason(outcome),
                scored_at=now,
            )
            .on_conflict_do_nothing(constraint="uq_opportunity_scores_triple")
        )
        result = await session.execute(statement)
        await session.commit()
        return isinstance(result, CursorResult) and result.rowcount > 0


async def _write_score_bundle(
    factory: async_sessionmaker[AsyncSession],
    *,
    target: _Target,
    evaluation: EvaluationOutput,
    now: datetime,
) -> bool:
    dimensions = evaluation.dimensions
    overall = overall_score(dimensions)
    recommendation = recommendation_for(overall)
    payload = build_action_payload(
        facts=target.facts,
        evaluation=evaluation,
        overall=overall,
        recommendation=recommendation,
        opportunity_id=target.opportunity_id,
        radar_id=target.radar_id,
        now=now,
    )
    _canonical, digest = payload_digest(payload)
    async with factory() as session:
        score_id = uuid4()
        statement = (
            pg_insert(OpportunityScore)
            .values(
                id=score_id,
                opportunity_id=target.opportunity_id,
                radar_id=target.radar_id,
                score_version=SCORE_VERSION,
                hard_filter_passed=True,
                disqualifiers=[],
                fit=dimensions.fit,
                expected_value=dimensions.expected_value,
                completion_probability=dimensions.completion_probability,
                effort_efficiency=dimensions.effort_efficiency,
                time_to_delivery=dimensions.time_to_delivery,
                competition=dimensions.competition,
                ambiguity=dimensions.ambiguity,
                risk=dimensions.risk,
                overall_score=overall,
                recommendation=recommendation,
                reason=evaluation.reason,
                scored_at=now,
            )
            .on_conflict_do_nothing(constraint="uq_opportunity_scores_triple")
        )
        result = await session.execute(statement)
        if not (isinstance(result, CursorResult) and result.rowcount > 0):
            await session.rollback()
            return False
        await session.execute(
            pg_insert(OpportunityActionPayload)
            .values(
                id=uuid4(),
                opportunity_score_id=score_id,
                payload_version=PAYLOAD_VERSION,
                payload=payload,
                payload_hash=digest,
                generated_at=now,
            )
            .on_conflict_do_nothing()
        )
        await _maybe_notify(
            session,
            target=target,
            evaluation=evaluation,
            dimensions=dimensions,
            overall=overall,
            score_id=score_id,
            now=now,
        )
        await session.commit()
        return True


async def _maybe_notify(
    session: AsyncSession,
    *,
    target: _Target,
    evaluation: EvaluationOutput,
    dimensions: Dimensions,
    overall: Decimal,
    score_id: UUID,
    now: datetime,
) -> bool:
    item = await session.get(OpportunityItem, target.opportunity_id)
    radar = await session.get(Radar, target.radar_id)
    if item is None or radar is None:
        return False
    radar_active = (
        radar.status == ResourceStatus.ACTIVE and radar.deleted_at is None and radar.id is not None
    )
    eligible = notification_qualified(
        hard_filter_passed=True,
        overall=overall,
        risk=dimensions.risk,
        ambiguity=dimensions.ambiguity,
        opportunity_status=item.status,
        deadline=item.deadline,
        radar_threshold=radar.notification_threshold,
        now=now,
        radar_active=radar_active,
    )
    if not eligible:
        return False
    statement = (
        pg_insert(Notification)
        .values(
            id=uuid4(),
            user_id=target.user_id,
            analysis_id=None,
            opportunity_score_id=score_id,
            title=item.title[:240],
            content=evaluation.reason[:MAX_REASON_CHARS],
            priority=notification_priority(overall),
            reason=evaluation.reason[:MAX_REASON_CHARS],
            url=item.source_url,
            status=NotificationStatus.UNREAD,
        )
        .on_conflict_do_nothing(
            index_elements=["user_id", "opportunity_score_id"],
            index_where=text("opportunity_score_id IS NOT NULL"),
        )
    )
    result = await session.execute(statement)
    return isinstance(result, CursorResult) and result.rowcount > 0


async def _pending_pairs(
    factory: async_sessionmaker[AsyncSession], *, batch_size: int
) -> list[tuple[UUID, UUID]]:
    score_exists = (
        select(OpportunityScore.id)
        .where(
            OpportunityScore.opportunity_id == OpportunityItem.id,
            OpportunityScore.radar_id == Radar.id,
            OpportunityScore.score_version == SCORE_VERSION,
        )
        .exists()
    )
    async with factory() as session:
        rows = (
            await session.execute(
                select(OpportunityItem.id, Radar.id)
                .join(RadarSource, RadarSource.source_id == OpportunityItem.source_id)
                .join(Radar, Radar.id == RadarSource.radar_id)
                .where(
                    OpportunityItem.status == "active",
                    Radar.user_id == OpportunityItem.user_id,
                    Radar.radar_type == RadarType.OPPORTUNITY,
                    Radar.status == ResourceStatus.ACTIVE,
                    Radar.deleted_at.is_(None),
                    ~score_exists,
                )
                .order_by(OpportunityItem.created_at.asc(), OpportunityItem.id.asc())
                .limit(batch_size)
            )
        ).all()
    return [(row[0], row[1]) for row in rows]


async def dispatch_pending_opportunities(
    factory: async_sessionmaker[AsyncSession],
    provider: OpportunityEvaluationProvider,
    settings: Settings,
    *,
    batch_size: int = 10,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    now: datetime | None = None,
) -> int:
    reference = now or datetime.now(UTC)
    pairs = await _pending_pairs(factory, batch_size=batch_size)
    completed = 0
    for opportunity_id, radar_id in pairs:
        outcome = await evaluate_opportunity(
            factory,
            opportunity_id=opportunity_id,
            radar_id=radar_id,
            provider=provider,
            settings=settings,
            sleep=sleep,
            now=reference,
        )
        if outcome in {"scored", "dismissed"}:
            completed += 1
    return completed
