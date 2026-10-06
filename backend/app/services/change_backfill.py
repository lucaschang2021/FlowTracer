"""Legacy RawItem backfill for version evidence (docs/23 §10, docs/63 §5).

Split out of ``change_tracking`` so the writer module stays within the architecture
budget. Creates the version-1 artifact/snapshot/event chain for legacy RawItems and
links each item to its snapshot (``raw_items.snapshot_id``, the I2 writer identity).
Idempotent: an item that already carries a snapshot is skipped.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import RawItem, Source
from app.models.evidence import AcquisitionSnapshot, ChangeEvent, SourceArtifact
from app.services.acquisition_types import RawCandidate
from app.services.change_tracking import MAX_ARTIFACT_KEY, build_snapshot
from app.services.version_evidence import (
    DETECTOR_VERSION,
    EXTRACTOR_VERSION,
    content_fingerprint,
    metadata_fingerprint,
    metadata_values,
    normalize_content,
    structure_fingerprint,
    structure_summary,
)

_BOUNDARY = "async def _backfill_one("


async def _backfill_one(
    session: AsyncSession, *, source: Source, item: RawItem, identity: str
) -> bool:
    """Link one legacy RawItem to its version-1 snapshot chain.

    Creates the artifact/snapshot/event when missing; links the item (``snapshot_id``,
    the I2 writer identity) to the artifact's matching snapshot when it already exists
    without one. False when the item already carries its snapshot."""
    if item.snapshot_id is not None:
        return False
    key = identity[:MAX_ARTIFACT_KEY]
    existing_id = await session.scalar(
        select(SourceArtifact.id).where(
            SourceArtifact.source_id == source.id,
            SourceArtifact.artifact_key == key,
        )
    )
    if existing_id is not None:
        return await _link_existing_artifact(session, item=item, artifact_id=existing_id)
    normalized = normalize_content(item.raw_text)
    values = metadata_values(
        title=item.title,
        author=None,
        published_at=item.published_at,
        content_type=item.content_type,
    )
    summary = structure_summary(
        body=None, content_type=item.content_type or "", normalized_content=normalized
    )
    hashes = (
        content_fingerprint(normalized),
        metadata_fingerprint(values),
        structure_fingerprint(summary),
    )
    await _create_backfill_chain(
        session,
        item=item,
        identity=identity,
        key=key,
        normalized=normalized,
        values=values,
        summary=summary,
        hashes=hashes,
    )
    return True


async def _create_backfill_chain(
    session: AsyncSession,
    *,
    item: RawItem,
    identity: str,
    key: str,
    normalized: str,
    values: dict[str, str | None],
    summary: dict[str, object],
    hashes: tuple[str, str, str],
) -> None:
    """Create the version-1 artifact/snapshot/event chain and link the legacy item."""
    source_id = item.source_id
    artifact = SourceArtifact(
        id=uuid4(),
        source_id=source_id,
        artifact_key=key,
        canonical_url=identity[:MAX_ARTIFACT_KEY],
        first_seen_at=item.fetched_at,
        last_seen_at=item.fetched_at,
        safe_metadata={},
    )
    session.add(artifact)
    # Explicit dependency order: without ORM relationships the unit of work cannot
    # order these inserts, and each row's FKs must already exist.
    await session.flush()
    snapshot = build_snapshot(
        artifact_id=artifact.id,
        run_id=item.collection_run_id,
        version=1,
        fetched_at=item.fetched_at,
        candidate=RawCandidate(
            external_id=item.external_id or str(item.id),
            canonical_url=identity,
            raw_text=item.raw_text,
            content_type=item.content_type or "",
            title=item.title,
            published_at=item.published_at,
        ),
        normalized=normalized,
        values=values,
        summary=summary,
        hashes=hashes,
        quality=Decimal("0.0000"),
    )
    snapshot.evidence = {"extractor": EXTRACTOR_VERSION, "origin": "legacy_backfill"}
    session.add(snapshot)
    await session.flush()
    artifact.current_snapshot_id = snapshot.id
    item.snapshot_id = snapshot.id
    session.add(
        ChangeEvent(
            id=uuid4(),
            artifact_id=artifact.id,
            collection_run_id=item.collection_run_id,
            previous_snapshot_id=None,
            current_snapshot_id=snapshot.id,
            change_type="created",
            materiality=Decimal("1.0000"),
            field_diff={"changed": [], "fields": {}},
            detector_version=DETECTOR_VERSION,
            occurred_at=item.fetched_at,
        )
    )


async def _link_existing_artifact(
    session: AsyncSession, *, item: RawItem, artifact_id: UUID
) -> bool:
    """Link a legacy item to the artifact snapshot whose content fingerprint matches."""
    digest = content_fingerprint(normalize_content(item.raw_text))
    snapshot = await session.scalar(
        select(AcquisitionSnapshot)
        .where(
            AcquisitionSnapshot.artifact_id == artifact_id,
            AcquisitionSnapshot.content_hash == digest,
        )
        .order_by(AcquisitionSnapshot.version.asc())
        .limit(1)
    )
    if snapshot is None:
        return False
    item.snapshot_id = snapshot.id
    return True


async def backfill_source_evidence(
    session: AsyncSession, *, source: Source, batch_size: int = 200
) -> int:
    """One-shot legacy backfill: existing RawItems become version-1 snapshots.

    Advances a deterministic ``(created_at, id)`` cursor between batches so every item
    of the source is processed regardless of size; artifacts that already carry a
    snapshot are skipped, so repeated calls stay idempotent.
    """
    created = 0
    cursor: tuple[datetime, UUID] | None = None
    while True:
        statement = select(RawItem).where(RawItem.source_id == source.id)
        if cursor is not None:
            statement = statement.where(tuple_(RawItem.created_at, RawItem.id) > cursor)
        items = list(
            (
                await session.scalars(
                    statement.order_by(RawItem.created_at.asc(), RawItem.id.asc()).limit(batch_size)
                )
            ).all()
        )
        if not items:
            break
        for item in items:
            identity = item.canonical_url or item.external_id or str(item.id)
            if await _backfill_one(session, source=source, item=item, identity=identity):
                created += 1
        cursor = (items[-1].created_at, items[-1].id)
        if len(items) < batch_size:
            break
    return created
