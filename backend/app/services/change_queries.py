"""Read APIs for version evidence: source-level and artifact-level change history.

Ownership is enforced through the shared source loader; responses carry bounded
display evidence only (field diffs, fingerprint hashes, titles, versions) — never
raw content, prompts, or internal trace (docs/23 §12/§14).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import ColumnElement

from app.models.evidence import AcquisitionSnapshot, ChangeEvent, SourceArtifact
from app.services.resources import get_source, resource_not_found


@dataclass(frozen=True, slots=True)
class ChangeRow:
    """One change event joined with its artifact and previous/current snapshots."""

    event: ChangeEvent
    artifact: SourceArtifact
    previous: AcquisitionSnapshot | None
    current: AcquisitionSnapshot | None


async def list_source_changes(
    session: AsyncSession,
    *,
    user_id: UUID,
    source_id: UUID,
    page: int,
    page_size: int,
    artifact_id: UUID | None = None,
    change_type: str | None = None,
) -> tuple[list[ChangeRow], int]:
    source = await get_source(session, user_id=user_id, source_id=source_id)
    predicates = [SourceArtifact.source_id == source.id]
    if artifact_id is not None:
        predicates.append(ChangeEvent.artifact_id == artifact_id)
    if change_type is not None:
        predicates.append(ChangeEvent.change_type == change_type)
    return await _query_changes(session, predicates=predicates, page=page, page_size=page_size)


async def list_artifact_changes(
    session: AsyncSession,
    *,
    user_id: UUID,
    source_id: UUID,
    artifact_id: UUID,
    page: int,
    page_size: int,
    change_type: str | None = None,
) -> tuple[list[ChangeRow], int]:
    source = await get_source(session, user_id=user_id, source_id=source_id)
    owned_artifact = await session.scalar(
        select(SourceArtifact.id).where(
            SourceArtifact.id == artifact_id,
            SourceArtifact.source_id == source.id,
        )
    )
    if owned_artifact is None:
        raise resource_not_found()
    predicates = [ChangeEvent.artifact_id == artifact_id]
    if change_type is not None:
        predicates.append(ChangeEvent.change_type == change_type)
    return await _query_changes(session, predicates=predicates, page=page, page_size=page_size)


async def _query_changes(
    session: AsyncSession,
    *,
    predicates: list[ColumnElement[bool]],
    page: int,
    page_size: int,
) -> tuple[list[ChangeRow], int]:
    total = int(
        await session.scalar(
            select(func.count())
            .select_from(ChangeEvent)
            .join(SourceArtifact, SourceArtifact.id == ChangeEvent.artifact_id)
            .where(*predicates)
        )
        or 0
    )
    previous = aliased(AcquisitionSnapshot, name="previous_snapshot")
    current = aliased(AcquisitionSnapshot, name="current_snapshot")
    statement = (
        select(ChangeEvent, SourceArtifact, previous, current)
        .join(SourceArtifact, SourceArtifact.id == ChangeEvent.artifact_id)
        .outerjoin(previous, previous.id == ChangeEvent.previous_snapshot_id)
        .outerjoin(current, current.id == ChangeEvent.current_snapshot_id)
        .where(*predicates)
        .order_by(ChangeEvent.occurred_at.desc(), ChangeEvent.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await session.execute(statement)).all()
    items = [
        ChangeRow(event=row[0], artifact=row[1], previous=row[2], current=row[3]) for row in rows
    ]
    return items, total
