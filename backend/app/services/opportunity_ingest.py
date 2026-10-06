"""ACQ-1G opportunity ingestion: ChangeEvent-driven item lifecycle (docs/24, ADR-041).

Called from the acquisition success path (seed pages) and from crawl page commits
inside their transactions. ``created`` snapshots create an item keyed by its
snapshot; ``content_changed`` snapshots refresh the artifact's existing item in
place (facts + snapshot identity, reactivating removed items); ``removed`` events
mark the item removed. Extraction never guesses: a failed extraction keeps the last
good facts (or leaves the item absent when nothing was ever extractable).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import CursorResult, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.opportunity_policy import PROFILE_VERSION
from app.models.entities import Source, SourceFamily
from app.models.evidence import AcquisitionSnapshot
from app.models.opportunity import OpportunityItem
from app.services.change_tracking import EvidenceResult, EvidenceWrite
from app.services.opportunity_facts import extract_opportunity_facts

LIFECYCLE_CHANGE_TYPES = frozenset({"created", "content_changed", "removed"})


async def record_opportunity_items(
    session: AsyncSession,
    *,
    source: Source,
    evidence: EvidenceResult,
    body: bytes | None,
) -> int:
    """Advance opportunity items for one observation of an opportunity source.

    Returns the number of items created, refreshed or marked removed."""
    if source.source_family != SourceFamily.OPPORTUNITY:
        return 0
    affected = 0
    for write in evidence.writes:
        if write.change_type == "created":
            affected += await _insert_item(session, source=source, write=write, body=body)
        elif write.change_type == "content_changed":
            affected += await _refresh_item(session, source=source, write=write, body=body)
        elif write.change_type == "removed":
            affected += await _mark_removed(session, source=source, write=write)
    return affected


async def _observed_at(session: AsyncSession, write: EvidenceWrite) -> datetime:
    """Observation time of the snapshot behind this write (the item's clock)."""
    snapshot = await session.get(AcquisitionSnapshot, write.snapshot_id)
    return snapshot.fetched_at if snapshot is not None else datetime.now(UTC)


async def _insert_item(
    session: AsyncSession, *, source: Source, write: EvidenceWrite, body: bytes | None
) -> int:
    extracted = extract_opportunity_facts(write.candidate, body)
    if extracted is None:
        return 0
    facts = extracted.facts
    observed_at = await _observed_at(session, write)
    statement = (
        pg_insert(OpportunityItem)
        .values(
            id=uuid4(),
            user_id=source.user_id,
            source_id=source.id,
            artifact_id=write.artifact_id,
            snapshot_id=write.snapshot_id,
            profile_version=PROFILE_VERSION,
            title=facts.title or "",
            platform=facts.platform,
            description=facts.description or "",
            budget_min=facts.budget_min,
            budget_max=facts.budget_max,
            currency=facts.currency,
            skills=list(facts.skills),
            deadline=facts.deadline,
            published_at=facts.published_at,
            estimated_effort_hours=facts.estimated_effort_hours,
            delivery_type=facts.delivery_type,
            client_metadata=extracted.client_metadata,
            source_url=facts.source_url or "",
            status="active",
            created_at=observed_at,
            updated_at=observed_at,
        )
        .on_conflict_do_nothing(constraint="uq_opportunities_snapshot")
    )
    result = await session.execute(statement)
    return 1 if isinstance(result, CursorResult) and result.rowcount > 0 else 0


async def _refresh_item(
    session: AsyncSession, *, source: Source, write: EvidenceWrite, body: bytes | None
) -> int:
    item = await session.scalar(
        select(OpportunityItem)
        .where(
            OpportunityItem.source_id == source.id,
            OpportunityItem.artifact_id == write.artifact_id,
        )
        .with_for_update()
    )
    if item is None:
        return await _insert_item(session, source=source, write=write, body=body)
    extracted = extract_opportunity_facts(write.candidate, body)
    if extracted is None:
        return 0
    facts = extracted.facts
    item.snapshot_id = write.snapshot_id
    item.title = facts.title or ""
    item.platform = facts.platform
    item.description = facts.description or ""
    item.budget_min = facts.budget_min
    item.budget_max = facts.budget_max
    item.currency = facts.currency
    item.skills = list(facts.skills)
    item.deadline = facts.deadline
    item.published_at = facts.published_at
    item.estimated_effort_hours = facts.estimated_effort_hours
    item.delivery_type = facts.delivery_type
    item.client_metadata = extracted.client_metadata
    item.source_url = facts.source_url or ""
    # A refreshed page is actionable again; the expiry sweep re-expires it when the
    # (possibly unchanged) deadline already passed. ``updated_at`` carries the
    # observation time, which is what re-evaluation compares against.
    item.status = "active"
    item.updated_at = await _observed_at(session, write)
    await session.flush()
    return 1


async def _mark_removed(session: AsyncSession, *, source: Source, write: EvidenceWrite) -> int:
    result = await session.execute(
        update(OpportunityItem)
        .where(
            OpportunityItem.source_id == source.id,
            OpportunityItem.artifact_id == write.artifact_id,
            OpportunityItem.status == "active",
        )
        .values(status="removed", updated_at=text("now()"))
    )
    return 1 if isinstance(result, CursorResult) and result.rowcount > 0 else 0
