import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_session
from app.core.context import correlation_id_context
from app.core.errors import AppError
from app.models.entities import CollectionRun, CollectionRunStatus, RawItemStatus, User
from app.schemas.acquisition import CollectionQueuedResponse, CollectionRunResponse, RawItemPage
from app.schemas.errors import documented_error
from app.services import acquisition

router = APIRouter(
    responses={
        401: documented_error("Invalid access token"),
        404: documented_error("Resource not found"),
        409: documented_error("Collection run conflict"),
        422: documented_error("Invalid request"),
        503: documented_error("Collection queue unavailable"),
    }
)


@router.post(
    "/{run_id}/retry",
    response_model=CollectionQueuedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_collection_run(
    run_id: UUID,
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CollectionQueuedResponse:
    child, _created = await acquisition.create_retry_run(
        session, user_id=user.id, original_run_id=run_id
    )
    await acquisition.publish_collection_updated(
        request.app.state.session_factory,
        child.id,
        getattr(request.app.state, "event_publisher", None),
    )
    response.headers["Location"] = f"/api/v1/collection-runs/{child.id}"
    if child.status == CollectionRunStatus.QUEUED:
        try:
            dispatcher = getattr(request.app.state, "collection_dispatcher", None)
            if dispatcher is None:
                from app.tasks.acquisition import enqueue_collection

                dispatcher = enqueue_collection
            await asyncio.to_thread(
                dispatcher,
                str(child.id),
                correlation_id_context.get() or str(child.id),
            )
        except Exception:
            await acquisition.mark_queue_failure(session, child.id)
            raise AppError(
                status_code=503,
                code="collection_queue_unavailable",
                message="Collection queue is temporarily unavailable",
            ) from None
    return CollectionQueuedResponse(run_id=child.id, status=child.status)


@router.get("/{run_id}", response_model=CollectionRunResponse)
async def get_collection_run(
    run_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CollectionRun:
    return await acquisition.get_owned_run(session, user_id=user.id, run_id=run_id)


@router.get("/{run_id}/items", response_model=RawItemPage)
async def list_collection_run_items(
    run_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: RawItemStatus | None = Query(None, alias="status"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> RawItemPage:
    items, total = await acquisition.list_run_items(
        session,
        user_id=user.id,
        run_id=run_id,
        page=page,
        page_size=page_size,
        status=status_filter,
    )
    return RawItemPage.model_validate(
        {"items": items, "page": page, "page_size": page_size, "total": total}
    )
