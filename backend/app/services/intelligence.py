from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.errors import AppError
from app.core.logging import get_logger
from app.models.entities import (
    AIUsageRecord,
    Analysis,
    AnalysisStatus,
    Document,
    DocumentStatus,
    Radar,
    Recommendation,
)
from app.providers.analysis import (
    AnalysisProvider,
    AnalysisRequest,
    ProviderError,
    ProviderResponse,
)
from app.services.cleaning import PIPELINE_VERSION

ANALYSIS_BUDGET_SECONDS = 90.0
RUNNING_STALE_AFTER = timedelta(minutes=10)


class AnalysisOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    summary: str = Field(min_length=1, max_length=2000)
    category: str = Field(min_length=1, max_length=120)
    relevance: int = Field(ge=0, le=100)
    importance: int = Field(ge=0, le=100)
    novelty: int = Field(ge=0, le=100)
    impact: int = Field(ge=0, le=100)
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("summary", "category", "reason")
    @classmethod
    def safe_text(cls, value: str) -> str:
        if any(ord(character) < 32 or 127 <= ord(character) <= 159 for character in value):
            raise ValueError("must not contain control characters")
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        try:
            normalized.encode("utf-8")
        except UnicodeEncodeError:
            raise ValueError("must contain valid Unicode") from None
        return normalized


@dataclass(frozen=True)
class ClaimedAnalysis:
    analysis_id: UUID
    document_id: UUID
    raw_item_id: UUID
    user_id: UUID
    radar_id: UUID
    claimed_at: datetime
    request: AnalysisRequest
    allowed_categories: tuple[str, ...]


def calculate_score(relevance: int, importance: int, novelty: int, impact: int) -> Decimal:
    value = (
        Decimal(relevance) * Decimal("0.40")
        + Decimal(importance) * Decimal("0.25")
        + Decimal(novelty) * Decimal("0.20")
        + Decimal(impact) * Decimal("0.15")
    )
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def recommendation_for(score: Decimal) -> Recommendation:
    if score >= Decimal("85"):
        return Recommendation.MUST_READ
    if score >= Decimal("70"):
        return Recommendation.READ
    if score >= Decimal("50"):
        return Recommendation.MONITOR
    return Recommendation.ARCHIVE


def qualifies_for_notification(score: Decimal, threshold: int) -> bool:
    return score >= Decimal(threshold)


def calculate_cost(input_tokens: int, output_tokens: int, settings: Settings) -> Decimal:
    value = (
        Decimal(input_tokens) * settings.ai_input_cost_per_million
        + Decimal(output_tokens) * settings.ai_output_cost_per_million
    ) / Decimal(1_000_000)
    return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def _reject_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def validate_output(content: str, categories: tuple[str, ...]) -> AnalysisOutput:
    try:
        raw = json.loads(content, parse_constant=_reject_constant)
        output = AnalysisOutput.model_validate(raw)
    except (json.JSONDecodeError, ValueError, ValidationError):
        raise ProviderError(
            "ai_invalid_output", "AI returned invalid output", retryable=False
        ) from None
    if categories and output.category not in {*categories, "other"}:
        raise ProviderError("ai_invalid_output", "AI returned an invalid category", retryable=False)
    return output


async def _claim_analysis(
    factory: async_sessionmaker[AsyncSession], analysis_id: UUID
) -> ClaimedAnalysis | None:
    async with factory() as session:
        row = (
            await session.execute(
                select(Analysis, Document, Radar)
                .join(Document, Document.id == Analysis.document_id)
                .join(Radar, Radar.id == Analysis.radar_id)
                .where(Analysis.id == analysis_id)
                .with_for_update(of=Analysis)
            )
        ).one_or_none()
        if row is None or row.Analysis.status != AnalysisStatus.PENDING:
            await session.rollback()
            return None
        claimed_at = datetime.now(UTC)
        row.Analysis.status = AnalysisStatus.RUNNING
        row.Analysis.updated_at = claimed_at
        row.Analysis.error_code = None
        row.Analysis.error_message = None
        request = AnalysisRequest(
            title=row.Document.title,
            content=row.Document.content[:24_000],
            radar_name=row.Radar.name,
            radar_goal=row.Radar.goal,
            categories=tuple(str(value) for value in row.Radar.categories),
            keywords=tuple(str(value) for value in row.Radar.keywords),
        )
        claimed = ClaimedAnalysis(
            analysis_id=row.Analysis.id,
            document_id=row.Document.id,
            raw_item_id=row.Document.raw_item_id,
            user_id=row.Radar.user_id,
            radar_id=row.Radar.id,
            claimed_at=claimed_at,
            request=request,
            allowed_categories=request.categories,
        )
        await session.commit()
        return claimed


async def _record_usage(
    factory: async_sessionmaker[AsyncSession],
    claimed: ClaimedAnalysis,
    provider: AnalysisProvider,
    settings: Settings,
    *,
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
                user_id=claimed.user_id,
                analysis_id=claimed.analysis_id,
                task_type="analysis",
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


async def _sync_document(session: AsyncSession, document_id: UUID) -> None:
    document = await session.scalar(
        select(Document).where(Document.id == document_id).with_for_update()
    )
    if document is None:
        return
    statuses = list(
        (
            await session.scalars(
                select(Analysis.status).where(
                    Analysis.document_id == document_id,
                    Analysis.pipeline_version == PIPELINE_VERSION,
                )
            )
        ).all()
    )
    if any(status in {AnalysisStatus.PENDING, AnalysisStatus.RUNNING} for status in statuses):
        document.status = DocumentStatus.ANALYZING
        return
    if not statuses or AnalysisStatus.COMPLETED in statuses:
        document.status = DocumentStatus.EMBEDDING
        document.error_code = None
        document.error_message = None
    else:
        document.status = DocumentStatus.FAILED
        document.error_code = "internal_analysis_error"
        document.error_message = "All analyses failed"


async def _complete_analysis(
    factory: async_sessionmaker[AsyncSession],
    claimed: ClaimedAnalysis,
    provider: AnalysisProvider,
    output: AnalysisOutput,
) -> bool:
    score = calculate_score(output.relevance, output.importance, output.novelty, output.impact)
    async with factory() as session:
        changed = await session.scalar(
            update(Analysis)
            .where(
                Analysis.id == claimed.analysis_id,
                Analysis.status == AnalysisStatus.RUNNING,
                Analysis.updated_at == claimed.claimed_at,
            )
            .values(
                summary=output.summary,
                category=output.category,
                relevance=output.relevance,
                importance=output.importance,
                novelty=output.novelty,
                impact=output.impact,
                radar_score=score,
                recommendation=recommendation_for(score),
                reason=output.reason,
                provider=provider.name,
                model=provider.model,
                status=AnalysisStatus.COMPLETED,
                error_code=None,
                error_message=None,
                updated_at=datetime.now(UTC),
            )
            .returning(Analysis.id)
        )
        if changed is not None:
            await _sync_document(session, claimed.document_id)
        await session.commit()
        return changed is not None


async def _fail_analysis(
    factory: async_sessionmaker[AsyncSession], claimed: ClaimedAnalysis, error: ProviderError
) -> bool:
    async with factory() as session:
        changed = await session.scalar(
            update(Analysis)
            .where(
                Analysis.id == claimed.analysis_id,
                Analysis.status == AnalysisStatus.RUNNING,
                Analysis.updated_at == claimed.claimed_at,
            )
            .values(
                status=AnalysisStatus.FAILED,
                error_code=error.code,
                error_message=error.safe_message[:500],
                updated_at=datetime.now(UTC),
            )
            .returning(Analysis.id)
        )
        if changed is not None:
            await _sync_document(session, claimed.document_id)
        await session.commit()
        return changed is not None


async def run_analysis(
    factory: async_sessionmaker[AsyncSession],
    analysis_id: UUID,
    provider: AnalysisProvider,
    settings: Settings,
    *,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> bool:
    claimed = await _claim_analysis(factory, analysis_id)
    if claimed is None:
        return False
    started = time.monotonic()
    repair_used = False
    repair_error: str | None = None
    last_error = ProviderError("internal_analysis_error", "Analysis failed", retryable=False)
    for attempt in range(1, 4):
        remaining = ANALYSIS_BUDGET_SECONDS - (time.monotonic() - started)
        if remaining <= 0:
            last_error = ProviderError("ai_timeout", "AI request timed out", retryable=False)
            break
        call_started = time.monotonic()
        response: ProviderResponse | None = None
        try:
            response = await asyncio.wait_for(
                provider.analyze(claimed.request, repair_error=repair_error), timeout=remaining
            )
            output = validate_output(response.content, claimed.allowed_categories)
        except TimeoutError:
            error = ProviderError("ai_timeout", "AI request timed out", retryable=True)
        except ProviderError as exc:
            error = exc
        except Exception:
            error = ProviderError(
                "internal_analysis_error", "Analysis failed unexpectedly", retryable=False
            )
        else:
            await _record_usage(
                factory,
                claimed,
                provider,
                settings,
                response=response,
                duration_ms=round((time.monotonic() - call_started) * 1000),
                succeeded=True,
                error_code=None,
            )
            completed = await _complete_analysis(factory, claimed, provider, output)
            get_logger().info(
                "analysis_completed",
                message="Analysis completed",
                analysis_id=str(claimed.analysis_id),
                document_id=str(claimed.document_id),
                raw_item_id=str(claimed.raw_item_id),
                radar_id=str(claimed.radar_id),
                provider=provider.name,
                model=provider.model,
                attempt=attempt,
                duration_ms=round((time.monotonic() - started) * 1000),
                status="completed" if completed else "superseded",
            )
            return completed
        await _record_usage(
            factory,
            claimed,
            provider,
            settings,
            response=response,
            duration_ms=round((time.monotonic() - call_started) * 1000),
            succeeded=False,
            error_code=error.code,
        )
        last_error = error
        if error.code == "ai_invalid_output" and not repair_used and attempt < 3:
            repair_used = True
            repair_error = "response did not match the required strict JSON schema"
            continue
        if error.retryable and attempt < 3:
            delay = 2.0 if attempt == 1 else 4.0
            if time.monotonic() - started + delay < ANALYSIS_BUDGET_SECONDS:
                await sleep(delay)
                continue
        break
    failed = await _fail_analysis(factory, claimed, last_error)
    get_logger().warning(
        "analysis_failed",
        message=last_error.safe_message,
        analysis_id=str(claimed.analysis_id),
        document_id=str(claimed.document_id),
        raw_item_id=str(claimed.raw_item_id),
        radar_id=str(claimed.radar_id),
        provider=provider.name,
        model=provider.model,
        attempt=attempt,
        duration_ms=round((time.monotonic() - started) * 1000),
        status="failed" if failed else "superseded",
        error_code=last_error.code,
    )
    return False


async def dispatch_pending_analyses(
    factory: async_sessionmaker[AsyncSession],
    dispatch: Callable[[str, str], None],
    *,
    batch_size: int = 100,
) -> int:
    async with factory() as session:
        analysis_ids = list(
            (
                await session.scalars(
                    select(Analysis.id)
                    .where(Analysis.status == AnalysisStatus.PENDING)
                    .order_by(Analysis.created_at.asc(), Analysis.id.asc())
                    .with_for_update(skip_locked=True)
                    .limit(batch_size)
                )
            ).all()
        )
        dispatched = 0
        for analysis_id in analysis_ids:
            try:
                dispatch(str(analysis_id), str(analysis_id))
            except Exception as exc:
                get_logger().warning(
                    "analysis_queue_unavailable",
                    message="Analysis queue is temporarily unavailable",
                    analysis_id=str(analysis_id),
                    exception_type=type(exc).__name__,
                )
                continue
            dispatched += 1
        await session.commit()
        return dispatched


async def recover_stale_analyses(
    factory: async_sessionmaker[AsyncSession], *, now: datetime | None = None, batch_size: int = 100
) -> int:
    cutoff = (now or datetime.now(UTC)) - RUNNING_STALE_AFTER
    async with factory() as session:
        analyses = list(
            (
                await session.scalars(
                    select(Analysis)
                    .where(
                        Analysis.status == AnalysisStatus.RUNNING,
                        Analysis.updated_at < cutoff,
                    )
                    .order_by(Analysis.updated_at.asc(), Analysis.id.asc())
                    .with_for_update(skip_locked=True)
                    .limit(batch_size)
                )
            ).all()
        )
        for analysis in analyses:
            analysis.status = AnalysisStatus.PENDING
            analysis.error_code = None
            analysis.error_message = None
            analysis.updated_at = datetime.now(UTC)
        await session.commit()
        return len(analyses)


def _owned_statement(user_id: UUID) -> Any:
    return (
        select(Analysis, Document, Radar)
        .join(Document, Document.id == Analysis.document_id)
        .join(Radar, Radar.id == Analysis.radar_id)
        .where(Radar.user_id == user_id, Radar.deleted_at.is_(None))
    )


async def get_owned_analysis(
    session: AsyncSession, *, user_id: UUID, analysis_id: UUID, for_update: bool = False
) -> tuple[Analysis, Document, Radar]:
    statement = _owned_statement(user_id).where(Analysis.id == analysis_id)
    if for_update:
        statement = statement.with_for_update(of=Analysis)
    row = (await session.execute(statement)).one_or_none()
    if row is None:
        raise AppError(status_code=404, code="resource_not_found", message="Resource not found")
    return row.Analysis, row.Document, row.Radar


async def list_intelligence(
    session: AsyncSession,
    *,
    user_id: UUID,
    page: int,
    page_size: int,
    radar_id: UUID | None,
    status: AnalysisStatus | None,
    recommendation: Recommendation | None,
    category: str | None,
    min_score: Decimal | None,
) -> tuple[list[dict[str, Any]], int]:
    predicates: list[Any] = []
    if radar_id is not None:
        predicates.append(Analysis.radar_id == radar_id)
    if status is not None:
        predicates.append(Analysis.status == status)
    if recommendation is not None:
        predicates.append(Analysis.recommendation == recommendation)
    if category is not None:
        predicates.append(Analysis.category == category)
    if min_score is not None:
        predicates.append(Analysis.radar_score >= min_score)
    statement = _owned_statement(user_id).where(*predicates)
    count_statement = (
        select(func.count())
        .select_from(Analysis)
        .join(Radar, Radar.id == Analysis.radar_id)
        .where(Radar.user_id == user_id, Radar.deleted_at.is_(None), *predicates)
    )
    total = int(await session.scalar(count_statement) or 0)
    rows = (
        await session.execute(
            statement.order_by(Analysis.created_at.desc(), Analysis.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return [
        _response_data(row.Analysis, row.Document, include_content=False) for row in rows
    ], total


def _response_data(
    analysis: Analysis, document: Document, *, include_content: bool
) -> dict[str, Any]:
    data = {
        "id": analysis.id,
        "document_id": document.id,
        "radar_id": analysis.radar_id,
        "title": document.title,
        "canonical_url": document.canonical_url,
        "summary": analysis.summary,
        "category": analysis.category,
        "relevance": analysis.relevance,
        "importance": analysis.importance,
        "novelty": analysis.novelty,
        "impact": analysis.impact,
        "radar_score": analysis.radar_score,
        "recommendation": analysis.recommendation,
        "reason": analysis.reason,
        "status": analysis.status,
        "error_code": analysis.error_code,
        "error_message": analysis.error_message,
        "pipeline_version": analysis.pipeline_version,
        "prompt_version": analysis.prompt_version,
        "provider": analysis.provider,
        "model": analysis.model,
        "created_at": analysis.created_at,
        "updated_at": analysis.updated_at,
    }
    if include_content:
        data.update(
            content=document.content,
            author=document.author,
            language=document.language,
            word_count=document.word_count,
        )
    return data


async def intelligence_detail(
    session: AsyncSession, *, user_id: UUID, analysis_id: UUID
) -> dict[str, Any]:
    analysis, document, _radar = await get_owned_analysis(
        session, user_id=user_id, analysis_id=analysis_id
    )
    return _response_data(analysis, document, include_content=True)


async def retry_analysis(session: AsyncSession, *, user_id: UUID, analysis_id: UUID) -> Analysis:
    analysis, _document, _radar = await get_owned_analysis(
        session, user_id=user_id, analysis_id=analysis_id, for_update=True
    )
    if analysis.status == AnalysisStatus.COMPLETED:
        await session.rollback()
        raise AppError(
            status_code=409,
            code="analysis_not_retryable",
            message="Completed analysis cannot be retried",
        )
    document = await session.scalar(
        select(Document).where(Document.id == analysis.document_id).with_for_update()
    )
    if document is None:
        await session.rollback()
        raise AppError(status_code=404, code="resource_not_found", message="Resource not found")
    if analysis.status == AnalysisStatus.FAILED:
        analysis.status = AnalysisStatus.PENDING
        analysis.error_code = None
        analysis.error_message = None
        analysis.updated_at = datetime.now(UTC)
    document.status = DocumentStatus.ANALYZING
    document.error_code = None
    document.error_message = None
    await session.commit()
    await session.refresh(analysis)
    return analysis
