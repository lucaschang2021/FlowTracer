from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_session
from app.models.entities import Radar, RadarType, ResourceStatus, User
from app.schemas.errors import documented_error
from app.schemas.resources import RadarCreate, RadarPage, RadarResponse, RadarUpdate, SourcePage
from app.services import resources

router = APIRouter(
    responses={
        401: documented_error("Invalid access token"),
        404: documented_error("Resource not found"),
        409: documented_error("Resource conflict"),
        422: documented_error("Invalid request"),
    }
)


@router.post("", response_model=RadarResponse, status_code=status.HTTP_201_CREATED)
async def create_radar(
    payload: RadarCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Radar:
    return await resources.create_radar(session, user_id=user.id, payload=payload)


@router.get("", response_model=RadarPage)
async def list_radars(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: ResourceStatus | None = Query(None, alias="status"),
    radar_type: RadarType | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> RadarPage:
    items, total = await resources.list_radars(
        session,
        user_id=user.id,
        page=page,
        page_size=page_size,
        status=status_filter,
        radar_type=radar_type,
    )
    return RadarPage.model_validate(
        {"items": items, "page": page, "page_size": page_size, "total": total}
    )


@router.get("/{radar_id}/sources", response_model=SourcePage)
async def list_bound_sources(
    radar_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SourcePage:
    items, total = await resources.list_bound_sources(
        session,
        user_id=user.id,
        radar_id=radar_id,
        page=page,
        page_size=page_size,
    )
    return SourcePage.model_validate(
        {"items": items, "page": page, "page_size": page_size, "total": total}
    )


@router.post("/{radar_id}/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def bind_source(
    radar_id: UUID,
    source_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    await resources.bind_source(session, user_id=user.id, radar_id=radar_id, source_id=source_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{radar_id}/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unbind_source(
    radar_id: UUID,
    source_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    await resources.unbind_source(session, user_id=user.id, radar_id=radar_id, source_id=source_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{radar_id}", response_model=RadarResponse)
async def get_radar(
    radar_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Radar:
    return await resources.get_radar(session, user_id=user.id, radar_id=radar_id)


@router.patch("/{radar_id}", response_model=RadarResponse)
async def update_radar(
    radar_id: UUID,
    payload: RadarUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Radar:
    return await resources.update_radar(
        session, user_id=user.id, radar_id=radar_id, payload=payload
    )


@router.delete("/{radar_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_radar(
    radar_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    await resources.delete_radar(session, user_id=user.id, radar_id=radar_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{radar_id}/pause", response_model=RadarResponse)
async def pause_radar(
    radar_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Radar:
    return await resources.set_radar_status(
        session, user_id=user.id, radar_id=radar_id, target=ResourceStatus.PAUSED
    )


@router.post("/{radar_id}/resume", response_model=RadarResponse)
async def resume_radar(
    radar_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Radar:
    return await resources.set_radar_status(
        session, user_id=user.id, radar_id=radar_id, target=ResourceStatus.ACTIVE
    )
