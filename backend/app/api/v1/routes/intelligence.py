import asyncio
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_session
from app.core.context import correlation_id_context
from app.core.errors import AppError
from app.models.entities import AnalysisStatus, Recommendation, User
from app.schemas.errors import documented_error
from app.schemas.intelligence import (
    AnalysisRetryResponse,
    IntelligenceDetail,
    IntelligencePage,
)
from app.services import intelligence

router = APIRouter(
    responses={
        401: documented_error("Invalid access token"),
        404: documented_error("Resource not found"),
        409: documented_error("Analysis conflict"),
        422: documented_error("Invalid request"),
        503: documented_error("Analysis queue unavailable"),
    }
)


@router.get("", response_model=IntelligencePage)
async def list_intelligence(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    radar_id: UUID | None = None,
    status_filter: AnalysisStatus | None = Query(None, alias="status"),
    recommendation: Recommendation | None = None,
    category: str | None = Query(None, min_length=1, max_length=120),
    min_score: Decimal | None = Query(None, ge=0, le=100),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> IntelligencePage:
    items, total = await intelligence.list_intelligence(
        session,
        user_id=user.id,
        page=page,
        page_size=page_size,
        radar_id=radar_id,
        status=status_filter,
        recommendation=recommendation,
        category=category,
        min_score=min_score,
    )
    return IntelligencePage.model_validate(
        {"items": items, "page": page, "page_size": page_size, "total": total}
    )


@router.get("/{analysis_id}", response_model=IntelligenceDetail)
async def get_intelligence(
    analysis_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    return await intelligence.intelligence_detail(session, user_id=user.id, analysis_id=analysis_id)


analyses_router = APIRouter(
    responses={
        401: documented_error("Invalid access token"),
        404: documented_error("Resource not found"),
        409: documented_error("Analysis conflict"),
        422: documented_error("Invalid request"),
        503: documented_error("Analysis queue unavailable"),
    }
)


@analyses_router.post(
    "/{analysis_id}/retry",
    response_model=AnalysisRetryResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_analysis(
    analysis_id: UUID,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AnalysisRetryResponse:
    analysis = await intelligence.retry_analysis(session, user_id=user.id, analysis_id=analysis_id)
    if analysis.status == AnalysisStatus.PENDING:
        try:
            dispatcher = getattr(request.app.state, "analysis_dispatcher", None)
            if dispatcher is None:
                from app.tasks.intelligence import enqueue_analysis

                dispatcher = enqueue_analysis
            await asyncio.to_thread(
                dispatcher,
                str(analysis.id),
                correlation_id_context.get() or str(analysis.id),
            )
        except Exception:
            raise AppError(
                status_code=503,
                code="analysis_queue_unavailable",
                message="Analysis queue is temporarily unavailable",
            ) from None
    return AnalysisRetryResponse(analysis_id=analysis.id, status=analysis.status)
