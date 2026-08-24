from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.entities import Radar, RadarSource, RadarType, ResourceStatus, Source, SourceType
from app.schemas.resources import RadarCreate, RadarUpdate, SourceCreate, SourceUpdate
from app.services.url_normalization import normalize_source_url


def resource_not_found() -> AppError:
    return AppError(status_code=404, code="resource_not_found", message="Resource not found")


def invalid_state(resource: str) -> AppError:
    return AppError(
        status_code=409,
        code=f"invalid_{resource}_state",
        message=f"Invalid {resource} state",
    )


def _constraint_name(exc: IntegrityError) -> str | None:
    candidates = (exc.orig, getattr(exc.orig, "__cause__", None))
    for candidate in candidates:
        name = getattr(candidate, "constraint_name", None)
        if isinstance(name, str):
            return name
        diagnostic = getattr(candidate, "diag", None)
        name = getattr(diagnostic, "constraint_name", None)
        if isinstance(name, str):
            return name
    return None


async def _commit_with_conflict(
    session: AsyncSession,
    *,
    constraint: str,
    code: str,
    message: str,
) -> None:
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        if _constraint_name(exc) == constraint:
            raise AppError(status_code=409, code=code, message=message) from None
        raise


async def get_radar(
    session: AsyncSession,
    *,
    user_id: UUID,
    radar_id: UUID,
    for_update: bool = False,
) -> Radar:
    statement = select(Radar).where(
        Radar.id == radar_id,
        Radar.user_id == user_id,
        Radar.deleted_at.is_(None),
    )
    if for_update:
        statement = statement.with_for_update()
    radar = await session.scalar(statement)
    if radar is None:
        raise resource_not_found()
    return radar


async def list_radars(
    session: AsyncSession,
    *,
    user_id: UUID,
    page: int,
    page_size: int,
    status: ResourceStatus | None,
    radar_type: RadarType | None,
) -> tuple[list[Radar], int]:
    predicates = [Radar.user_id == user_id, Radar.deleted_at.is_(None)]
    if status is not None:
        predicates.append(Radar.status == status)
    if radar_type is not None:
        predicates.append(Radar.radar_type == radar_type)
    total = int(
        await session.scalar(select(func.count()).select_from(Radar).where(*predicates)) or 0
    )
    items = list(
        (
            await session.scalars(
                select(Radar)
                .where(*predicates)
                .order_by(Radar.created_at.desc(), Radar.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    return items, total


async def create_radar(session: AsyncSession, *, user_id: UUID, payload: RadarCreate) -> Radar:
    radar = Radar(user_id=user_id, **payload.model_dump())
    session.add(radar)
    await _commit_with_conflict(
        session,
        constraint="uq_radars_active_user_name",
        code="radar_name_conflict",
        message="An active radar with this name already exists",
    )
    await session.refresh(radar)
    return radar


async def update_radar(
    session: AsyncSession,
    *,
    user_id: UUID,
    radar_id: UUID,
    payload: RadarUpdate,
) -> Radar:
    radar = await get_radar(session, user_id=user_id, radar_id=radar_id, for_update=True)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(radar, field, value)
    radar.updated_at = datetime.now(UTC)
    await _commit_with_conflict(
        session,
        constraint="uq_radars_active_user_name",
        code="radar_name_conflict",
        message="An active radar with this name already exists",
    )
    await session.refresh(radar)
    return radar


async def delete_radar(session: AsyncSession, *, user_id: UUID, radar_id: UUID) -> None:
    radar = await get_radar(session, user_id=user_id, radar_id=radar_id, for_update=True)
    await session.execute(delete(RadarSource).where(RadarSource.radar_id == radar.id))
    radar.status = ResourceStatus.ARCHIVED
    radar.deleted_at = datetime.now(UTC)
    await session.commit()


async def set_radar_status(
    session: AsyncSession,
    *,
    user_id: UUID,
    radar_id: UUID,
    target: ResourceStatus,
) -> Radar:
    radar = await get_radar(session, user_id=user_id, radar_id=radar_id, for_update=True)
    if radar.status == ResourceStatus.ARCHIVED:
        await session.rollback()
        raise invalid_state("radar")
    if radar.status != target:
        radar.status = target
        await session.commit()
        await session.refresh(radar)
    else:
        await session.commit()
    return radar


async def get_source(
    session: AsyncSession,
    *,
    user_id: UUID,
    source_id: UUID,
    for_update: bool = False,
) -> Source:
    statement = select(Source).where(
        Source.id == source_id,
        Source.user_id == user_id,
        Source.deleted_at.is_(None),
    )
    if for_update:
        statement = statement.with_for_update()
    source = await session.scalar(statement)
    if source is None:
        raise resource_not_found()
    return source


async def list_sources(
    session: AsyncSession,
    *,
    user_id: UUID,
    page: int,
    page_size: int,
    status: ResourceStatus | None,
    source_type: SourceType | None,
) -> tuple[list[Source], int]:
    predicates = [Source.user_id == user_id, Source.deleted_at.is_(None)]
    if status is not None:
        predicates.append(Source.status == status)
    if source_type is not None:
        predicates.append(Source.source_type == source_type)
    total = int(
        await session.scalar(select(func.count()).select_from(Source).where(*predicates)) or 0
    )
    items = list(
        (
            await session.scalars(
                select(Source)
                .where(*predicates)
                .order_by(Source.created_at.desc(), Source.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    return items, total


def _ensure_supported_source_type(source_type: SourceType) -> None:
    if source_type == SourceType.API:
        raise AppError(
            status_code=422,
            code="unsupported_source_type",
            message="Source type is not supported",
        )


async def create_source(session: AsyncSession, *, user_id: UUID, payload: SourceCreate) -> Source:
    _ensure_supported_source_type(payload.source_type)
    original_url, normalized_url = normalize_source_url(payload.url)
    values = payload.model_dump(exclude={"url"})
    source = Source(user_id=user_id, url=original_url, normalized_url=normalized_url, **values)
    session.add(source)
    await _commit_with_conflict(
        session,
        constraint="uq_sources_active_user_url",
        code="source_url_conflict",
        message="An active source with this URL already exists",
    )
    await session.refresh(source)
    return source


async def update_source(
    session: AsyncSession,
    *,
    user_id: UUID,
    source_id: UUID,
    payload: SourceUpdate,
) -> Source:
    source = await get_source(session, user_id=user_id, source_id=source_id, for_update=True)
    values = payload.model_dump(exclude_unset=True)
    if "url" in values:
        original_url, normalized_url = normalize_source_url(values.pop("url"))
        source.url = original_url
        source.normalized_url = normalized_url
    for field, value in values.items():
        setattr(source, field, value)
    source.updated_at = datetime.now(UTC)
    await _commit_with_conflict(
        session,
        constraint="uq_sources_active_user_url",
        code="source_url_conflict",
        message="An active source with this URL already exists",
    )
    await session.refresh(source)
    return source


async def delete_source(session: AsyncSession, *, user_id: UUID, source_id: UUID) -> None:
    source = await get_source(session, user_id=user_id, source_id=source_id, for_update=True)
    await session.execute(delete(RadarSource).where(RadarSource.source_id == source.id))
    source.status = ResourceStatus.ARCHIVED
    source.deleted_at = datetime.now(UTC)
    await session.commit()


async def set_source_status(
    session: AsyncSession,
    *,
    user_id: UUID,
    source_id: UUID,
    target: ResourceStatus,
) -> Source:
    source = await get_source(session, user_id=user_id, source_id=source_id, for_update=True)
    if source.status == ResourceStatus.ARCHIVED:
        await session.rollback()
        raise invalid_state("source")
    if source.status != target:
        source.status = target
        await session.commit()
        await session.refresh(source)
    else:
        await session.commit()
    return source


async def bind_source(
    session: AsyncSession,
    *,
    user_id: UUID,
    radar_id: UUID,
    source_id: UUID,
) -> None:
    radar = await get_radar(session, user_id=user_id, radar_id=radar_id)
    source = await get_source(session, user_id=user_id, source_id=source_id)
    if radar.status == ResourceStatus.ARCHIVED or source.status == ResourceStatus.ARCHIVED:
        raise AppError(
            status_code=409,
            code="invalid_resource_state",
            message="Archived resources cannot be bound",
        )
    await session.execute(
        insert(RadarSource)
        .values(radar_id=radar.id, source_id=source.id)
        .on_conflict_do_nothing(index_elements=[RadarSource.radar_id, RadarSource.source_id])
    )
    await session.commit()


async def unbind_source(
    session: AsyncSession,
    *,
    user_id: UUID,
    radar_id: UUID,
    source_id: UUID,
) -> None:
    await get_radar(session, user_id=user_id, radar_id=radar_id)
    await get_source(session, user_id=user_id, source_id=source_id)
    await session.execute(
        delete(RadarSource).where(
            RadarSource.radar_id == radar_id,
            RadarSource.source_id == source_id,
        )
    )
    await session.commit()


async def list_bound_sources(
    session: AsyncSession,
    *,
    user_id: UUID,
    radar_id: UUID,
    page: int,
    page_size: int,
) -> tuple[list[Source], int]:
    await get_radar(session, user_id=user_id, radar_id=radar_id)
    predicates = [
        RadarSource.radar_id == radar_id,
        Source.user_id == user_id,
        Source.deleted_at.is_(None),
    ]
    total = int(
        await session.scalar(
            select(func.count())
            .select_from(RadarSource)
            .join(Source, Source.id == RadarSource.source_id)
            .where(*predicates)
        )
        or 0
    )
    items = list(
        (
            await session.scalars(
                select(Source)
                .join(RadarSource, Source.id == RadarSource.source_id)
                .where(*predicates)
                .order_by(Source.created_at.desc(), Source.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    return items, total
