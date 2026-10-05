"""WP-6 I1 acceptance matrix: version evidence shadow-write (ADR-036 / docs/63).

Covers pure extraction (noise normalization, three fingerprints, structure summary,
classification, materiality, bounded diff) and DB behavior (version sequence, revert
reuse, unchanged, concurrency, removed-by-two-miss rule, legacy backfill idempotency,
RawItem compatibility) plus the migration cycle with its safe downgrade guard.
"""

from __future__ import annotations

import os
import subprocess
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from app.models.entities import (
    AcquisitionMode,
    CollectionRun,
    CollectionRunStatus,
    CollectionTriggerType,
    RawItem,
    RawItemStatus,
    Source,
    SourceType,
    User,
)
from app.models.evidence import AcquisitionSnapshot, ChangeEvent, SourceArtifact
from app.schemas.resources import AcquisitionProfileV1
from app.services.acquisition_run_repository import SqlAlchemyAcquisitionRunRepository
from app.services.acquisition_types import (
    AcquisitionResult,
    FetchResponse,
    ParseResult,
    RawCandidate,
)
from app.services.change_tracking import (
    artifact_key_for,
    backfill_source_evidence,
    record_version_evidence,
)
from app.services.version_evidence import (
    DETECTOR_VERSION,
    EXTRACTOR_VERSION,
    bounded_field_diff,
    classify_trio,
    content_fingerprint,
    materiality_of,
    metadata_fingerprint,
    metadata_values,
    normalize_content,
    structure_summary,
)

BACKEND = Path(__file__).resolve().parents[1]
TABLES = (
    "change_events, acquisition_snapshots, source_artifacts, acquisition_attempts, "
    "source_acquisition_states, raw_items, collection_runs, sources, users"
)
NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)

HTML_V1 = (
    b"<html><head><title>Doc</title></head><body><main>"
    b"<p>Deterministic version evidence paragraph one for the change layer.</p>"
    b"<p>Second paragraph with stable meaning and enough characters.</p>"
    b'<img src="https://cdn.example.com/img/logo.png">'
    b'<a href="https://cdn.example.com/files/report.pdf">Report</a>'
    b"</main></body></html>"
)
HTML_V2 = HTML_V1.replace(b"paragraph one", b"paragraph one revised").replace(
    b"Second paragraph", b"Second paragraph extended"
)


def candidate(
    *,
    raw_text: str,
    canonical: str = "https://example.com/doc",
    external_id: str = "doc-1",
    title: str | None = "Doc",
    content_type: str = "text/html; charset=utf-8",
    published_at: datetime | None = None,
    author: str | None = None,
) -> RawCandidate:
    metadata = {"author": author} if author else {}
    return RawCandidate(
        external_id=external_id,
        canonical_url=canonical,
        raw_text=raw_text,
        content_type=content_type,
        title=title,
        published_at=published_at,
        metadata=metadata,
    )


class TestPureExtraction:
    def test_noise_normalization_folds_dynamic_lines_and_tracking(self) -> None:
        noisy = (
            "Last updated: 2026-10-05 12:31\r\n"
            "2026-10-05 12:31\r\n"
            "Real content line\u200b  with   spacing\r\n"
            "Real content line with spacing\r\n"
            "Link https://example.com/x?utm_source=feed&id=7&fbclid=abc"
        )
        normalized = normalize_content(noisy)
        assert "Last updated" not in normalized
        assert "utm_source" not in normalized
        assert "fbclid" not in normalized
        assert "\r" not in normalized
        assert "\u200b" not in normalized
        assert "Real content line with spacing" in normalized

    def test_fingerprints_deterministic_and_dimension_specific(self) -> None:
        text = "Deterministic content for fingerprint checks."
        assert content_fingerprint(normalize_content(text)) == content_fingerprint(
            normalize_content(text)
        )
        values = metadata_values(title="A", author=None, published_at=NOW, content_type="text/html")
        again = metadata_values(title="A", author=None, published_at=NOW, content_type="text/html")
        assert metadata_fingerprint(values) == metadata_fingerprint(again)
        different = metadata_values(
            title="B", author=None, published_at=NOW, content_type="text/html"
        )
        assert metadata_fingerprint(values) != metadata_fingerprint(different)

    def test_structure_summary_block_tags_and_attachments(self) -> None:
        normalized = normalize_content("One block\nTwo block\nThree block")
        summary = structure_summary(
            body=HTML_V1, content_type="text/html", normalized_content=normalized
        )
        assert summary["block_tags"] == ["main", "p", "p"]
        assert summary["block_count"] == 3
        assert summary["attachments"] == [  # type: ignore[comparison-overlap]
            "cdn.example.com/files/report.pdf",
            "cdn.example.com/img/logo.png",
        ]
        # Structure must not depend on text: same body with different text is identical.
        other_text = structure_summary(
            body=HTML_V1, content_type="text/html", normalized_content="Totally different text"
        )
        assert other_text == summary
        xml_summary = structure_summary(
            body=b"<rss/>", content_type="application/rss+xml", normalized_content=normalized
        )
        assert xml_summary["attachments"] == []
        assert xml_summary["block_tags"] == []

    def test_classification_and_materiality(self) -> None:
        trio = ("a" * 64, "b" * 64, "c" * 64)
        assert classify_trio(previous=None, current=trio) == "created"
        assert classify_trio(previous=trio, current=trio) == "unchanged"
        content = ("d" * 64, trio[1], trio[2])
        assert classify_trio(previous=trio, current=content) == "content_changed"
        structure = (trio[0], trio[1], "e" * 64)
        assert classify_trio(previous=trio, current=structure) == "structure_changed"
        metadata = (trio[0], "f" * 64, trio[2])
        assert classify_trio(previous=trio, current=metadata) == "metadata_changed"
        assert materiality_of(
            content_changed=True, structure_changed=False, metadata_changed=False
        ) == Decimal("0.6000")
        assert materiality_of(
            content_changed=False, structure_changed=True, metadata_changed=False
        ) == Decimal("0.3000")
        assert materiality_of(
            content_changed=True, structure_changed=True, metadata_changed=True
        ) == Decimal("1.0000")

    def test_bounded_field_diff(self) -> None:
        previous = {"title": "Old", "author": None, "published_at": None, "content_type": "x"}
        current = {"title": "New", "author": "A", "published_at": None, "content_type": "x"}
        diff = bounded_field_diff(
            change_type="metadata_changed", previous=previous, current=current
        )
        assert diff["changed"] == ["author", "title"]  # type: ignore[comparison-overlap]
        long_value = {
            "title": "x" * 500,
            "author": None,
            "published_at": None,
            "content_type": None,
        }
        bounded = bounded_field_diff(
            change_type="metadata_changed", previous=None, current=long_value
        )
        fields = bounded["fields"]  # type: ignore[assignment]
        assert len(fields["title"]["new"]) == 200  # type: ignore[index]
        assert bounded_field_diff(change_type="unchanged", previous=previous, current=current) == {
            "changed": [],
            "fields": {},
        }


async def create_source(
    engine: AsyncEngine, *, url: str = "https://example.com/doc", rss: bool = False
) -> UUID:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User(
            id=uuid4(),
            email=f"change-{uuid4()}@example.com",
            password_hash="synthetic",  # noqa: S106 - isolated database fixture
            display_name="Change",
        )
        source = Source(
            id=uuid4(),
            user_id=user.id,
            name="Change Source",
            source_type=SourceType.RSS if rss else SourceType.URL,
            url=url,
            normalized_url=url,
            acquisition_mode=AcquisitionMode.AUTO,
            acquisition_profile=AcquisitionProfileV1().storage_dict(),
        )
        session.add(user)
        await session.flush()
        session.add(source)
        await session.commit()
        return source.id


async def queue_run(engine: AsyncEngine, source_id: UUID) -> UUID:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        run = CollectionRun(
            id=uuid4(),
            source_id=source_id,
            trigger_type=CollectionTriggerType.MANUAL,
            status=CollectionRunStatus.QUEUED,
        )
        session.add(run)
        await session.commit()
        return run.id


async def shadow_write(
    engine: AsyncEngine,
    *,
    source_id: UUID,
    candidates: list[RawCandidate],
    body: bytes | None = None,
    quality: Decimal | None = Decimal("0.8000"),
    fetched_at: datetime = NOW,
) -> UUID:
    """Create a run, persist it RUNNING, then shadow-write evidence directly."""
    run_id = await queue_run(engine, source_id)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        run = await session.get(CollectionRun, run_id)
        assert run is not None
        run.status = CollectionRunStatus.RUNNING
        run.claim_token = uuid4()
        run.worker_id = "test-worker"
        run.lease_expires_at = fetched_at + timedelta(minutes=10)
        await session.commit()
        await record_version_evidence(
            session,
            run=run,
            parsed=ParseResult(candidates=candidates),
            body=body,
            quality_score=quality,
            fetched_at=fetched_at,
        )
        await session.commit()
    return run_id


async def events_for(engine: AsyncEngine, artifact_id: UUID) -> list[ChangeEvent]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        return list(
            (
                await session.scalars(
                    select(ChangeEvent)
                    .where(ChangeEvent.artifact_id == artifact_id)
                    .order_by(ChangeEvent.occurred_at.asc(), ChangeEvent.created_at.asc())
                )
            ).all()
        )


async def snapshots_for(engine: AsyncEngine, artifact_id: UUID) -> list[AcquisitionSnapshot]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        return list(
            (
                await session.scalars(
                    select(AcquisitionSnapshot)
                    .where(AcquisitionSnapshot.artifact_id == artifact_id)
                    .order_by(AcquisitionSnapshot.version.asc())
                )
            ).all()
        )


@pytest.fixture
async def change_engine() -> AsyncEngine:
    database_url = os.environ["TEST_DATABASE_URL"]
    assert "_test" in database_url.rsplit("/", maxsplit=1)[-1]
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    yield engine
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    await engine.dispose()


class TestVersionSequence:
    @pytest.mark.asyncio
    async def test_created_then_unchanged_then_content_change_and_revert(
        self, change_engine: AsyncEngine
    ) -> None:
        source_id = await create_source(change_engine)
        first = candidate(raw_text="Body one with stable content.", title="Doc")
        await shadow_write(change_engine, source_id=source_id, candidates=[first], body=HTML_V1)
        factory = async_sessionmaker(change_engine, expire_on_commit=False)
        async with factory() as session:
            artifact = await session.scalar(
                select(SourceArtifact).where(SourceArtifact.source_id == source_id)
            )
            assert artifact is not None
            events = await events_for(change_engine, artifact.id)
            assert [event.change_type for event in events] == ["created"]
            assert events[0].previous_snapshot_id is None
            assert events[0].current_snapshot_id is not None
            assert events[0].materiality == Decimal("1.0000")
            assert events[0].detector_version == DETECTOR_VERSION
            snapshots = await snapshots_for(change_engine, artifact.id)
            assert len(snapshots) == 1
            assert snapshots[0].version == 1
            assert snapshots[0].extractor_version == EXTRACTOR_VERSION
            assert snapshots[0].quality_score == Decimal("0.8000")

        await shadow_write(
            change_engine,
            source_id=source_id,
            candidates=[candidate(raw_text="Body one with stable content.", title="Doc")],
            body=HTML_V1,
            fetched_at=NOW + timedelta(minutes=5),
        )
        await shadow_write(
            change_engine,
            source_id=source_id,
            candidates=[candidate(raw_text="Body two with changed content.", title="Doc")],
            body=HTML_V1,
            fetched_at=NOW + timedelta(minutes=10),
        )
        async with factory() as session:
            artifact = await session.scalar(
                select(SourceArtifact).where(SourceArtifact.source_id == source_id)
            )
            assert artifact is not None
            events = await events_for(change_engine, artifact.id)
            assert [event.change_type for event in events] == [
                "created",
                "unchanged",
                "content_changed",
            ]
            assert events[1].materiality == Decimal("0.0000")
            assert events[1].previous_snapshot_id == events[1].current_snapshot_id
            assert events[2].materiality == Decimal("0.6000")
            diff = events[2].field_diff
            assert "content" in diff["changed"]
            assert diff["fields"] == {}
            snapshots = await snapshots_for(change_engine, artifact.id)
            assert [snapshot.version for snapshot in snapshots] == [1, 2]

        # Revert to the first content state: versions count distinct states.
        await shadow_write(
            change_engine,
            source_id=source_id,
            candidates=[candidate(raw_text="Body one with stable content.", title="Doc")],
            body=HTML_V1,
            fetched_at=NOW + timedelta(minutes=15),
        )
        async with factory() as session:
            artifact = await session.scalar(
                select(SourceArtifact).where(SourceArtifact.source_id == source_id)
            )
            assert artifact is not None
            snapshots = await snapshots_for(change_engine, artifact.id)
            assert [snapshot.version for snapshot in snapshots] == [1, 2]
            events = await events_for(change_engine, artifact.id)
            assert events[-1].change_type == "content_changed"
            assert events[-1].current_snapshot_id == snapshots[0].id

    @pytest.mark.asyncio
    async def test_metadata_and_structure_changes(self, change_engine: AsyncEngine) -> None:
        source_id = await create_source(change_engine)
        await shadow_write(
            change_engine,
            source_id=source_id,
            candidates=[candidate(raw_text="Stable body text.", title="Doc")],
            body=HTML_V1,
        )
        await shadow_write(
            change_engine,
            source_id=source_id,
            candidates=[candidate(raw_text="Stable body text.", title="Doc renamed")],
            body=HTML_V1,
            fetched_at=NOW + timedelta(minutes=5),
        )
        await shadow_write(
            change_engine,
            source_id=source_id,
            candidates=[candidate(raw_text="Stable body text.", title="Doc renamed")],
            body=HTML_V1.replace(b"logo.png", b"logo-v2.png"),
            fetched_at=NOW + timedelta(minutes=10),
        )
        factory = async_sessionmaker(change_engine, expire_on_commit=False)
        async with factory() as session:
            artifact = await session.scalar(
                select(SourceArtifact).where(SourceArtifact.source_id == source_id)
            )
            assert artifact is not None
            events = await events_for(change_engine, artifact.id)
            assert [event.change_type for event in events] == [
                "created",
                "metadata_changed",
                "structure_changed",
            ]
            assert events[1].materiality == Decimal("0.1000")
            assert events[1].field_diff["changed"] == ["title"]
            assert events[1].field_diff["fields"]["title"] == {  # type: ignore[index]
                "old": "Doc",
                "new": "Doc renamed",
            }
            assert events[2].materiality == Decimal("0.3000")

    @pytest.mark.asyncio
    async def test_concurrent_runs_keep_versions_monotonic(
        self, change_engine: AsyncEngine
    ) -> None:
        import asyncio

        source_id = await create_source(change_engine)

        async def one_round(index: int) -> None:
            await shadow_write(
                change_engine,
                source_id=source_id,
                candidates=[candidate(raw_text=f"Content revision {index}.")],
                body=HTML_V1,
                fetched_at=NOW + timedelta(minutes=index),
            )

        await asyncio.gather(one_round(1), one_round(2))
        factory = async_sessionmaker(change_engine, expire_on_commit=False)
        async with factory() as session:
            artifact = await session.scalar(
                select(SourceArtifact).where(SourceArtifact.source_id == source_id)
            )
            assert artifact is not None
            snapshots = await snapshots_for(change_engine, artifact.id)
            assert [snapshot.version for snapshot in snapshots] == [1, 2]
            events = await events_for(change_engine, artifact.id)
            assert len(events) == 2
            assert {event.change_type for event in events} == {"created", "content_changed"}
            assert len({event.collection_run_id for event in events}) == 2

    @pytest.mark.asyncio
    async def test_removed_requires_two_missing_cycles(self, change_engine: AsyncEngine) -> None:
        source_id = await create_source(change_engine, url="https://example.com/feed.xml", rss=True)
        a = candidate(
            raw_text="Article A body.", canonical="https://example.com/a", external_id="a"
        )
        b = candidate(
            raw_text="Article B body.", canonical="https://example.com/b", external_id="b"
        )
        await shadow_write(change_engine, source_id=source_id, candidates=[a, b])
        await shadow_write(
            change_engine,
            source_id=source_id,
            candidates=[a],
            fetched_at=NOW + timedelta(minutes=5),
        )
        factory = async_sessionmaker(change_engine, expire_on_commit=False)
        async with factory() as session:
            artifact_b = await session.scalar(
                select(SourceArtifact).where(SourceArtifact.artifact_key == "https://example.com/b")
            )
            assert artifact_b is not None
            assert artifact_b.removed_at is None
            assert artifact_b.safe_metadata.get("miss_streak") == 1
            events = await events_for(change_engine, artifact_b.id)
            assert [event.change_type for event in events] == ["created"]

        await shadow_write(
            change_engine,
            source_id=source_id,
            candidates=[a],
            fetched_at=NOW + timedelta(minutes=10),
        )
        async with factory() as session:
            artifact_b = await session.scalar(
                select(SourceArtifact).where(SourceArtifact.artifact_key == "https://example.com/b")
            )
            assert artifact_b is not None
            assert artifact_b.removed_at is not None
            events = await events_for(change_engine, artifact_b.id)
            assert [event.change_type for event in events] == ["created", "removed"]
            removed = events[-1]
            assert removed.previous_snapshot_id is not None
            assert removed.current_snapshot_id is None
            assert removed.materiality == Decimal("1.0000")

        # Article B returns: removal is cleared and the sighting resets the miss streak.
        await shadow_write(
            change_engine,
            source_id=source_id,
            candidates=[a, b],
            fetched_at=NOW + timedelta(minutes=15),
        )
        async with factory() as session:
            artifact_b = await session.scalar(
                select(SourceArtifact).where(SourceArtifact.artifact_key == "https://example.com/b")
            )
            assert artifact_b is not None
            assert artifact_b.removed_at is None
            assert artifact_b.safe_metadata.get("miss_streak") == 0


class TestBackfillAndCompat:
    @pytest.mark.asyncio
    async def test_legacy_backfill_is_idempotent(self, change_engine: AsyncEngine) -> None:
        source_id = await create_source(change_engine)
        factory = async_sessionmaker(change_engine, expire_on_commit=False)
        run_id = await queue_run(change_engine, source_id)
        async with factory() as session:
            session.add_all(
                [
                    RawItem(
                        id=uuid4(),
                        source_id=source_id,
                        collection_run_id=run_id,
                        external_id="legacy-1",
                        canonical_url="https://example.com/legacy-1",
                        title="Legacy One",
                        content_type="text/html",
                        raw_text="Legacy body one.",
                        content_hash="a" * 64,
                        status=RawItemStatus.FETCHED,
                        fetched_at=NOW,
                    ),
                    RawItem(
                        id=uuid4(),
                        source_id=source_id,
                        collection_run_id=run_id,
                        external_id="legacy-2",
                        canonical_url="https://example.com/legacy-2",
                        title="Legacy Two",
                        content_type="text/html",
                        raw_text="Legacy body two.",
                        content_hash="b" * 64,
                        status=RawItemStatus.FETCHED,
                        fetched_at=NOW,
                    ),
                ]
            )
            await session.commit()
            source = await session.get(Source, source_id)
            assert source is not None
            first = await backfill_source_evidence(session, source=source)
            await session.commit()
            second = await backfill_source_evidence(session, source=source)
            await session.commit()
            assert (first, second) == (2, 0)
            artifacts = list(
                (
                    await session.scalars(
                        select(SourceArtifact).where(SourceArtifact.source_id == source_id)
                    )
                ).all()
            )
            assert len(artifacts) == 2
            for artifact in artifacts:
                snapshots = await snapshots_for(change_engine, artifact.id)
                assert len(snapshots) == 1
                assert snapshots[0].evidence.get("origin") == "legacy_backfill"
                events = await events_for(change_engine, artifact.id)
                assert [event.change_type for event in events] == ["created"]

    @pytest.mark.asyncio
    async def test_raw_item_write_path_unchanged(self, change_engine: AsyncEngine) -> None:
        """The legacy writer keeps producing RawItems with unchanged columns; the
        snapshot linkage column belongs to the I2 writer switch and must not exist yet."""
        factory = async_sessionmaker(change_engine, expire_on_commit=False)
        async with factory() as session:
            columns = await session.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'raw_items'"
                )
            )
            names = {row[0] for row in columns}
            assert "snapshot_id" not in names
        source_id = await create_source(change_engine)
        run_id = await queue_run(change_engine, source_id)
        repository = SqlAlchemyAcquisitionRunRepository(factory)
        claimed = await repository.claim_run(run_id, worker_id="w")
        assert claimed is not None
        parsed = ParseResult(candidates=[candidate(raw_text="Writer compatibility body.")])
        completion = await repository.finish_success(
            claimed,
            backend_name="native_http",
            attempt_started_at=NOW,
            result=AcquisitionResult(
                FetchResponse(
                    "https://example.com/doc",
                    "text/html; charset=utf-8",
                    HTML_V1,
                ),
                retry_count=0,
                budget_used={"requests": 1, "pages": 1, "bytes_received": len(HTML_V1)},
            ),
            parsed=parsed,
            quality_score=Decimal("0.7000"),
        )
        assert completion is not None
        async with factory() as session:
            items = await session.scalar(
                select(func.count()).select_from(RawItem).where(RawItem.source_id == source_id)
            )
            assert items == 1
            artifacts = await session.scalar(
                select(func.count())
                .select_from(SourceArtifact)
                .where(SourceArtifact.source_id == source_id)
            )
            assert artifacts == 1
        assert artifact_key_for(candidate(raw_text="x")) == "https://example.com/doc"


class TestMigrationCycle:
    def run_alembic(self, *args: str) -> subprocess.CompletedProcess[str]:
        command = ["python", "-m", "alembic", *args]
        return subprocess.run(  # noqa: S603 - fixed local command
            command,
            cwd=BACKEND,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

    @pytest.mark.asyncio
    async def test_cycle_and_downgrade_guard(self, change_engine: AsyncEngine) -> None:
        # Empty evidence tables: downgrade and re-upgrade must round-trip.
        downgraded = self.run_alembic("downgrade", "20260830_0004")
        assert downgraded.returncode == 0, downgraded.stderr
        check = self.run_alembic("current")
        assert "20261005_0005" not in check.stdout
        upgraded = self.run_alembic("upgrade", "head")
        assert upgraded.returncode == 0, upgraded.stderr
        after = self.run_alembic("current")
        assert "20261005_0006" in after.stdout

        # Guard: with evidence rows present the downgrade must refuse.
        source_id = await create_source(change_engine)
        await shadow_write(
            change_engine,
            source_id=source_id,
            candidates=[candidate(raw_text="Guard body.")],
            body=HTML_V1,
        )
        guarded = self.run_alembic("downgrade", "20260830_0004")
        assert guarded.returncode != 0
        assert "refusing to drop version evidence table" in guarded.stderr
        # A later revision may already have been downgraded and committed before the
        # guard fired; restore head so the shared test database stays on the latest
        # revision for every following suite.
        restored = self.run_alembic("upgrade", "head")
        assert restored.returncode == 0, restored.stderr
        still = self.run_alembic("current")
        assert "20261005_0006" in still.stdout
