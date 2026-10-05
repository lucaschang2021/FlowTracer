"""ACQ-1G opportunity ingestion: first sightings become OpportunityItems.

Called from the acquisition success path inside the run transaction. Only
``created`` change events produce items in I1: the item is a projection of one
AcquisitionSnapshot, keyed by ``snapshot_id`` (unique), so replays are no-ops.
Version-change driven re-evaluation is deliberately out of I1 scope (docs/65).
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import CursorResult
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.opportunity_policy import PROFILE_VERSION
from app.models.entities import Source, SourceFamily
from app.models.opportunity import OpportunityItem
from app.services.change_tracking import EvidenceResult
from app.services.opportunity_facts import extract_opportunity_facts


async def record_opportunity_items(
    session: AsyncSession,
    *,
    source: Source,
    evidence: EvidenceResult,
    body: bytes | None,
) -> int:
    """Create opportunity items for first-sighting writes of opportunity sources."""
    if source.source_family != SourceFamily.OPPORTUNITY:
        return 0
    created = 0
    for write in evidence.writes:
        if write.change_type != "created":
            continue
        extracted = extract_opportunity_facts(write.candidate, body)
        if extracted is None:
            continue
        facts = extracted.facts
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
            )
            .on_conflict_do_nothing(constraint="uq_opportunities_snapshot")
        )
        result = await session.execute(statement)
        if isinstance(result, CursorResult) and result.rowcount > 0:
            created += 1
    return created
