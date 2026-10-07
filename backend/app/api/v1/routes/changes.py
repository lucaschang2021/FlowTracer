"""Change-history read endpoints (WP-6 I2 read APIs, docs/23 §14, ADR-040)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import User, get_current_user, get_session
from app.schemas.changes import ChangeEventPage, ChangeEventResponse, SnapshotRef
from app.schemas.errors import documented_error
from app.services import change_queries
from app.services.change_queries import ChangeRow

CHANGE_TYPES = "^(created|unchanged|content_changed|metadata_changed|structure_changed|removed)$"

router = APIRouter(
    responses={
        401: documented_error("Invalid access token"),
        404: documented_error("Resource not found"),
        422: documented_error("Invalid request"),
    }
)


def _page(rows: list[ChangeRow], *, page: int, page_size: int, total: int) -> ChangeEventPage:
    return ChangeEventPage(
        items=[_event(row) for row in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


def _event(row: ChangeRow) -> ChangeEventResponse:
    return ChangeEventResponse(
        id=row.event.id,
        source_id=row.artifact.source_id,
        artifact_id=row.artifact.id,
        artifact_key=row.artifact.artifact_key,
        canonical_url=row.artifact.canonical_url,
        change_type=row.event.change_type,
        materiality=row.event.materiality,
        field_diff=row.event.field_diff,
        detector_version=row.event.detector_version,
        occurred_at=row.event.occurred_at,
        previous=None if row.previous is None else SnapshotRef.model_validate(row.previous),
        current=None if row.current is None else SnapshotRef.model_validate(row.current),
    )


@router.get("/{source_id}/changes", response_model=ChangeEventPage)
async def list_source_changes(
    source_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    artifact_id: UUID | None = None,
    change_type: str | None = Query(None, pattern=CHANGE_TYPES),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ChangeEventPage:
    rows, total = await change_queries.list_source_changes(
        session,
        user_id=user.id,
        source_id=source_id,
        page=page,
        page_size=page_size,
        artifact_id=artifact_id,
        change_type=change_type,
    )
    return _page(rows, page=page, page_size=page_size, total=total)


@router.get("/{source_id}/artifacts/{artifact_id}/changes", response_model=ChangeEventPage)
async def list_artifact_changes(
    source_id: UUID,
    artifact_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    change_type: str | None = Query(None, pattern=CHANGE_TYPES),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ChangeEventPage:
    rows, total = await change_queries.list_artifact_changes(
        session,
        user_id=user.id,
        source_id=source_id,
        artifact_id=artifact_id,
        page=page,
        page_size=page_size,
        change_type=change_type,
    )
    return _page(rows, page=page, page_size=page_size, total=total)
