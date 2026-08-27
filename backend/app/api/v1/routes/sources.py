import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_session
from app.core.context import correlation_id_context
from app.core.errors import AppError
from app.models.entities import (
    CollectionRunStatus,
    CollectionTriggerType,
    ResourceStatus,
    Source,
    SourceType,
    User,
)
from app.schemas.acquisition import CollectionQueuedResponse, CollectionRunPage
from app.schemas.errors import documented_error
from app.schemas.resources import SourceCreate, SourcePage, SourceResponse, SourceUpdate
from app.services import acquisition, resources

router = APIRouter(
    responses={
        401: documented_error("Invalid access token"),
        404: documented_error("Resource not found"),
        409: documented_error("Resource conflict"),
        422: documented_error("Invalid request"),
        503: documented_error("Collection queue unavailable"),
    }
)


@router.post("", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    payload: SourceCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Source:
    return await resources.create_source(session, user_id=user.id, payload=payload)


@router.get("", response_model=SourcePage)
async def list_sources(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: ResourceStatus | None = Query(None, alias="status"),
    source_type: SourceType | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SourcePage:
    items, total = await resources.list_sources(
        session,
        user_id=user.id,
        page=page,
        page_size=page_size,
        status=status_filter,
        source_type=source_type,
    )
    return SourcePage.model_validate(
        {"items": items, "page": page, "page_size": page_size, "total": total}
    )


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Source:
    return await resources.get_source(session, user_id=user.id, source_id=source_id)


@router.patch("/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: UUID,
    payload: SourceUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Source:
    return await resources.update_source(
        session, user_id=user.id, source_id=source_id, payload=payload
    )


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    await resources.delete_source(session, user_id=user.id, source_id=source_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{source_id}/pause", response_model=SourceResponse)
async def pause_source(
    source_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Source:
    return await resources.set_source_status(
        session, user_id=user.id, source_id=source_id, target=ResourceStatus.PAUSED
    )


@router.post("/{source_id}/resume", response_model=SourceResponse)
async def resume_source(
    source_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Source:
    return await resources.set_source_status(
        session, user_id=user.id, source_id=source_id, target=ResourceStatus.ACTIVE
    )


@router.post(
    "/{source_id}/collect",
    response_model=CollectionQueuedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def collect_source(
    source_id: UUID,
    request: Request,
    response: Response,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CollectionQueuedResponse:
    run, _created = await acquisition.create_manual_run(
        session,
        user_id=user.id,
        source_id=source_id,
        idempotency_key=idempotency_key,
    )
    response.headers["Location"] = f"/api/v1/collection-runs/{run.id}"
    if run.status == CollectionRunStatus.QUEUED:
        try:
            dispatcher = getattr(request.app.state, "collection_dispatcher", None)
            if dispatcher is None:
                from app.tasks.acquisition import enqueue_collection

                dispatcher = enqueue_collection
            await asyncio.to_thread(
                dispatcher,
                str(run.id),
                correlation_id_context.get() or str(run.id),
            )
        except Exception:
            await acquisition.mark_queue_failure(session, run.id)
            raise AppError(
                status_code=503,
                code="collection_queue_unavailable",
                message="Collection queue is temporarily unavailable",
            ) from None
    return CollectionQueuedResponse(run_id=run.id, status=run.status)


@router.get("/{source_id}/runs", response_model=CollectionRunPage)
async def list_source_runs(
    source_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: CollectionRunStatus | None = Query(None, alias="status"),
    trigger_type: CollectionTriggerType | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CollectionRunPage:
    items, total = await acquisition.list_source_runs(
        session,
        user_id=user.id,
        source_id=source_id,
        page=page,
        page_size=page_size,
        status=status_filter,
        trigger_type=trigger_type,
    )
    return CollectionRunPage.model_validate(
        {"items": items, "page": page, "page_size": page_size, "total": total}
    )
