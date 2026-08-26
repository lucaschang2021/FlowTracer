from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_session
from app.models.entities import CollectionRun, RawItemStatus, User
from app.schemas.acquisition import CollectionRunResponse, RawItemPage
from app.schemas.errors import documented_error
from app.services import acquisition

router = APIRouter(
    responses={
        401: documented_error("Invalid access token"),
        404: documented_error("Resource not found"),
        422: documented_error("Invalid request"),
    }
)


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
