"""ACQ-1F change tracking: shadow-write version evidence from successful acquisitions.

Writes SourceArtifact / AcquisitionSnapshot / ChangeEvent rows inside the caller's
transaction. Never touches RawItem or the document pipeline: the legacy writer keeps
working unchanged while version evidence accumulates alongside it (docs/23 §10).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import CollectionRun, Source
from app.models.evidence import AcquisitionSnapshot, ChangeEvent, SourceArtifact
from app.services.acquisition_types import CollectionError, ParseResult, RawCandidate
from app.services.version_evidence import (
    DETECTOR_VERSION,
    EXTRACTOR_VERSION,
    FOUR_PLACES,
    bounded_field_diff,
    classify_trio,
    content_fingerprint,
    materiality_of,
    metadata_fingerprint,
    metadata_values,
    normalize_content,
    structure_fingerprint,
    structure_summary,
)

MAX_ARTIFACT_KEY = 512
MAX_SAFE_METADATA_VALUE = 2000
REMOVED_MISS_THRESHOLD = 2


@dataclass(frozen=True, slots=True)
class EvidenceWrite:
    """One artifact/event observation from a successful run."""

    artifact_id: UUID
    snapshot_id: UUID
    change_type: str
    candidate: RawCandidate


@dataclass(frozen=True, slots=True)
class EvidenceResult:
    """Evidence written for one successful run: event count and per-candidate writes."""

    events: int
    writes: tuple[EvidenceWrite, ...]


def artifact_key_for(candidate: RawCandidate) -> str:
    """Stable per-source identity: canonical URL, or content-addressed without a stable id."""
    if candidate.dedupe_by_canonical:
        return candidate.canonical_url[:MAX_ARTIFACT_KEY]
    return f"content:{candidate.external_id}"[:MAX_ARTIFACT_KEY]


def _clamp(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if len(text) <= MAX_SAFE_METADATA_VALUE else text[:MAX_SAFE_METADATA_VALUE]


async def _upsert_artifact(
    session: AsyncSession,
    *,
    source_id: UUID,
    artifact_key: str,
    canonical_url: str,
    now: datetime,
) -> SourceArtifact:
    statement = (
        pg_insert(SourceArtifact)
        .values(
            id=uuid4(),
            source_id=source_id,
            artifact_key=artifact_key,
            canonical_url=canonical_url,
            first_seen_at=now,
            last_seen_at=now,
            safe_metadata={},
        )
        .on_conflict_do_nothing(constraint="uq_source_artifacts_source_key")
    )
    await session.execute(statement)
    artifact = await session.scalar(
        select(SourceArtifact)
        .where(
            SourceArtifact.source_id == source_id,
            SourceArtifact.artifact_key == artifact_key,
        )
        .with_for_update()
    )
    if artifact is None:  # pragma: no cover - the unique constraint guarantees the row
        raise CollectionError("internal_collection_error", "Version evidence artifact is missing")
    return artifact


async def _current_snapshot(
    session: AsyncSession, artifact: SourceArtifact
) -> AcquisitionSnapshot | None:
    """Last observed state of the artifact; the classification baseline.

    Distinct from ``_latest_snapshot`` (highest version number): after a revert the
    pointer references the older, re-used snapshot, so repeated observations of the
    same state classify as ``unchanged`` instead of re-reporting a change.
    """
    if artifact.current_snapshot_id is None:
        return None
    return await session.get(AcquisitionSnapshot, artifact.current_snapshot_id)


async def _latest_snapshot(session: AsyncSession, artifact_id: UUID) -> AcquisitionSnapshot | None:
    return await session.scalar(
        select(AcquisitionSnapshot)
        .where(AcquisitionSnapshot.artifact_id == artifact_id)
        .order_by(AcquisitionSnapshot.version.desc())
        .limit(1)
    )


async def _snapshot_by_trio(
    session: AsyncSession,
    artifact_id: UUID,
    content_hash: str,
    metadata_hash: str,
    structure_hash: str,
) -> AcquisitionSnapshot | None:
    return await session.scalar(
        select(AcquisitionSnapshot).where(
            AcquisitionSnapshot.artifact_id == artifact_id,
            AcquisitionSnapshot.content_hash == content_hash,
            AcquisitionSnapshot.metadata_hash == metadata_hash,
            AcquisitionSnapshot.structure_hash == structure_hash,
        )
    )


def build_snapshot(
    *,
    artifact_id: UUID,
    run_id: UUID,
    version: int,
    fetched_at: datetime,
    candidate: RawCandidate,
    normalized: str,
    values: dict[str, str | None],
    summary: dict[str, object],
    hashes: tuple[str, str, str],
    quality: Decimal,
) -> AcquisitionSnapshot:
    return AcquisitionSnapshot(
        id=uuid4(),
        artifact_id=artifact_id,
        collection_run_id=run_id,
        version=version,
        fetched_at=fetched_at,
        title=candidate.title,
        author=_clamp(values.get("author")),
        published_at=candidate.published_at,
        content_type=_clamp(candidate.content_type),
        normalized_content=normalized,
        safe_metadata={"metadata_values": {name: _clamp(value) for name, value in values.items()}},
        structure_summary=summary,
        content_hash=hashes[0],
        metadata_hash=hashes[1],
        structure_hash=hashes[2],
        extractor_version=EXTRACTOR_VERSION,
        quality_score=quality,
        evidence={"extractor": EXTRACTOR_VERSION},
    )


def _snapshot_quality(quality_score: Decimal | None) -> Decimal:
    value = Decimal(0) if quality_score is None else quality_score
    return value.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)


def _compose_candidate(
    candidate: RawCandidate, body: bytes | None
) -> tuple[str, dict[str, str | None], dict[str, object], tuple[str, str, str]]:
    normalized = normalize_content(candidate.raw_text)
    values = metadata_values(
        title=candidate.title,
        author=_clamp(candidate.metadata.get("author") if candidate.metadata else None),
        published_at=candidate.published_at,
        content_type=candidate.content_type,
    )
    summary = structure_summary(
        body=body, content_type=candidate.content_type, normalized_content=normalized
    )
    hashes = (
        content_fingerprint(normalized),
        metadata_fingerprint(values),
        structure_fingerprint(summary),
    )
    return normalized, values, summary, hashes


def _trio(snapshot: AcquisitionSnapshot) -> tuple[str, str, str]:
    return (snapshot.content_hash, snapshot.metadata_hash, snapshot.structure_hash)


def _change_materiality(
    change_type: str, prior: tuple[str, str, str], current: tuple[str, str, str]
) -> Decimal:
    if change_type == "created":
        return Decimal("1.0000")
    if change_type == "unchanged":
        return Decimal("0.0000")
    return materiality_of(
        content_changed=prior[0] != current[0],
        structure_changed=prior[2] != current[2],
        metadata_changed=prior[1] != current[1],
    )


async def _resolve_current(
    session: AsyncSession,
    *,
    run: CollectionRun,
    artifact: SourceArtifact,
    prior_snapshot: AcquisitionSnapshot | None,
    latest: AcquisitionSnapshot | None,
    hashes: tuple[str, str, str],
    change_type: str,
    normalized: str,
    values: dict[str, str | None],
    summary: dict[str, object],
    candidate: RawCandidate,
    quality: Decimal,
    fetched_at: datetime,
) -> AcquisitionSnapshot | None:
    """Return the snapshot representing the current state; insert v-next unless reverted."""
    if change_type == "unchanged":
        return prior_snapshot
    existing = await _snapshot_by_trio(session, artifact.id, *hashes)
    if existing is not None:
        # Content reverted to an earlier state: versions count distinct states.
        return existing
    version = 1 if latest is None else latest.version + 1
    snapshot = build_snapshot(
        artifact_id=artifact.id,
        run_id=run.id,
        version=version,
        fetched_at=fetched_at,
        candidate=candidate,
        normalized=normalized,
        values=values,
        summary=summary,
        hashes=hashes,
        quality=quality,
    )
    session.add(snapshot)
    return snapshot


async def _record_candidate(
    session: AsyncSession,
    *,
    run: CollectionRun,
    candidate: RawCandidate,
    body: bytes | None,
    quality: Decimal,
    fetched_at: datetime,
) -> EvidenceWrite:
    artifact = await _upsert_artifact(
        session,
        source_id=run.source_id,
        artifact_key=artifact_key_for(candidate),
        canonical_url=candidate.canonical_url,
        now=fetched_at,
    )
    normalized, values, summary, hashes = _compose_candidate(candidate, body)
    # Classification baseline is the *last observed* state (the pointer), not the
    # highest version number; version numbering still uses the latest snapshot.
    prior_snapshot = await _current_snapshot(session, artifact)
    latest = await _latest_snapshot(session, artifact.id)
    prior = None if prior_snapshot is None else _trio(prior_snapshot)
    change_type = classify_trio(previous=prior, current=hashes)
    current = await _resolve_current(
        session,
        run=run,
        artifact=artifact,
        prior_snapshot=prior_snapshot,
        latest=latest,
        hashes=hashes,
        change_type=change_type,
        normalized=normalized,
        values=values,
        summary=summary,
        candidate=candidate,
        quality=quality,
        fetched_at=fetched_at,
    )
    if current is None:  # pragma: no cover - created/changed always resolve a snapshot
        raise CollectionError("internal_collection_error", "Version evidence snapshot is missing")
    previous_values = (
        None if prior_snapshot is None else prior_snapshot.safe_metadata.get("metadata_values")
    )
    # Flush the newly inserted snapshot first: without ORM relationships the unit of
    # work cannot infer insert order, and the event's FKs need the snapshot row to exist.
    await session.flush()
    artifact.current_snapshot_id = current.id
    session.add(
        ChangeEvent(
            id=uuid4(),
            artifact_id=artifact.id,
            collection_run_id=run.id,
            previous_snapshot_id=None if prior_snapshot is None else prior_snapshot.id,
            current_snapshot_id=current.id,
            change_type=change_type,
            materiality=_change_materiality(change_type, prior or hashes, hashes),
            field_diff=bounded_field_diff(
                change_type=change_type, previous=previous_values, current=values
            ),
            detector_version=DETECTOR_VERSION,
            occurred_at=fetched_at,
        )
    )
    artifact.last_seen_at = fetched_at
    if artifact.removed_at is not None:
        artifact.removed_at = None
    meta = dict(artifact.safe_metadata or {})
    if meta.get("miss_streak"):
        meta["miss_streak"] = 0
        artifact.safe_metadata = meta
    return EvidenceWrite(
        artifact_id=artifact.id,
        snapshot_id=current.id,
        change_type=change_type,
        candidate=candidate,
    )


async def _mark_missing(
    session: AsyncSession,
    *,
    run: CollectionRun,
    observed: set[str],
    now: datetime,
) -> int:
    """Two consecutive successful observation cycles without a sighting mark removal."""
    artifacts = (
        await session.scalars(
            select(SourceArtifact).where(
                SourceArtifact.source_id == run.source_id,
                SourceArtifact.removed_at.is_(None),
            )
        )
    ).all()
    events = 0
    for artifact in artifacts:
        if artifact.artifact_key in observed:
            continue
        meta = dict(artifact.safe_metadata or {})
        streak = int(meta.get("miss_streak", 0)) + 1
        meta["miss_streak"] = streak
        artifact.safe_metadata = meta
        if streak < REMOVED_MISS_THRESHOLD:
            continue
        previous = await _current_snapshot(session, artifact)
        if previous is None:  # pragma: no cover - every artifact keeps a current pointer
            previous = await _latest_snapshot(session, artifact.id)
        if previous is None:  # pragma: no cover - every artifact is created with a snapshot
            continue
        artifact.removed_at = now
        session.add(
            ChangeEvent(
                id=uuid4(),
                artifact_id=artifact.id,
                collection_run_id=run.id,
                previous_snapshot_id=previous.id,
                current_snapshot_id=None,
                change_type="removed",
                materiality=Decimal("1.0000"),
                field_diff={"changed": [], "fields": {}},
                detector_version=DETECTOR_VERSION,
                occurred_at=now,
            )
        )
        events += 1
    return events


async def record_version_evidence(
    session: AsyncSession,
    *,
    run: CollectionRun,
    parsed: ParseResult,
    body: bytes | None,
    quality_score: Decimal | None,
    fetched_at: datetime,
    mark_missing: bool = True,
) -> EvidenceResult:
    """Shadow-write evidence for one successful run; returns writes and event count.

    ``mark_missing=False`` defers removal detection to the end of a multi-page crawl,
    where the observed set is the union of the seed and every crawled page."""
    quality = _snapshot_quality(quality_score)
    observed: set[str] = set()
    events = 0
    writes: list[EvidenceWrite] = []
    for candidate in parsed.candidates:
        observed.add(artifact_key_for(candidate))
        writes.append(
            await _record_candidate(
                session,
                run=run,
                candidate=candidate,
                body=body,
                quality=quality,
                fetched_at=fetched_at,
            )
        )
        events += 1
    if mark_missing:
        events += await _mark_missing(session, run=run, observed=observed, now=fetched_at)
    return EvidenceResult(events=events, writes=tuple(writes))


async def record_page_evidence(
    session: AsyncSession,
    *,
    run: CollectionRun,
    candidate: RawCandidate,
    body: bytes | None,
    quality_score: Decimal | None,
    fetched_at: datetime,
) -> EvidenceWrite:
    """Evidence for a single observed page (crawl target): one artifact write.

    Removal detection stays with the run-level call and applies only to repeated
    full-observation cycles (see ``record_version_evidence`` callers)."""
    return await _record_candidate(
        session,
        run=run,
        candidate=candidate,
        body=body,
        quality=_snapshot_quality(quality_score),
        fetched_at=fetched_at,
    )


async def backfill_source_evidence(
    session: AsyncSession, *, source: Source, batch_size: int = 200
) -> int:
    """One-shot legacy backfill entry point (implementation in ``change_backfill``)."""
    from app.services.change_backfill import backfill_source_evidence as implementation

    return await implementation(session, source=source, batch_size=batch_size)
