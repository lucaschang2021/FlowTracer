from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_session
from app.models.entities import ResourceStatus, Source, SourceType, User
from app.schemas.errors import documented_error
from app.schemas.resources import SourceCreate, SourcePage, SourceResponse, SourceUpdate
from app.services import resources

router = APIRouter(
    responses={
        401: documented_error("Invalid access token"),
        404: documented_error("Resource not found"),
        409: documented_error("Resource conflict"),
        422: documented_error("Invalid request"),
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
