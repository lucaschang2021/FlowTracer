"""WP-8 final offline value-loop acceptance (docs/67 §1, docs/25 §16).

Three closed loops, all on local fixtures with deterministic providers:

1. routed intelligence loop: router execution -> version evidence -> discovery
   checkpoint -> RawItem -> Document -> Analysis -> Embedding -> notification;
2. opportunity loop: acquisition -> snapshot -> OpportunityItem -> hard filter ->
   score -> action payload -> notification -> REST;
3. disabled capabilities stay closed: browser fail-closed, RawItem writer switch
   absent, and no crawl execution beyond the seed page.

No public network access: fetches are deterministic in-process doubles and URLs
are ``.invalid``/``example.com`` fixtures only.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings
from app.core.security import create_access_token
from app.domains.provider_ports import (
    OpportunityEvaluationRequest,
    ProviderResponse,
    ProviderUsage,
)
from app.main import create_app
from app.models.entities import (
    AcquisitionAttempt,
    AcquisitionMode,
    BackendName,
    CollectionRun,
    CollectionRunStatus,
    CollectionTriggerType,
    DiscoveryMode,
    Notification,
    Radar,
    RadarSource,
    RadarType,
    RawItem,
    ResourceStatus,
    Source,
    SourceAcquisitionState,
    SourceFamily,
    SourceType,
    User,
)
from app.models.evidence import AcquisitionSnapshot, ChangeEvent, SourceArtifact
from app.models.opportunity import OpportunityItem, OpportunityScore
from app.providers.analysis import FakeAnalysisProvider
from app.providers.embedding import FakeEmbeddingProvider
from app.schemas.events import EventEnvelope
from app.schemas.resources import AcquisitionProfileV1
from app.services.acquisition_route import execute_route_run
from app.services.acquisition_router import BROWSER_DYNAMIC_ENABLED, select_candidates
from app.services.acquisition_run_repository import SqlAlchemyAcquisitionRunRepository
from app.services.acquisition_types import (
    AcquisitionResult,
    CollectionError,
    FetchResponse,
)
from app.services.cleaning import clean_raw_item
from app.services.intelligence import run_analysis
from app.services.memory import run_embedding
from app.services.notifications import dispatch_notifications
from app.services.opportunity_evaluation import dispatch_pending_opportunities
from app.services.readiness import ReadinessService

TABLES = (
    "notifications, ai_usage_records, opportunity_action_payloads, opportunity_scores, "
    "opportunities, change_events, acquisition_snapshots, source_artifacts, "
    "acquisition_attempts, source_acquisition_states, document_chunks, bookmarks, analyses, "
    "documents, raw_items, radar_sources, collection_runs, sources, radars, refresh_tokens, users"
)
NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)
SEED = "https://example.com/guide/start.html"

INTEL_BODY = (
    b"<html><head><title>Guide</title></head><body><main>"
    b"<p>" + b"Deterministic acceptable extraction content for the final loop. " * 40 + b"</p>"
    b'<a href="https://example.com/guide/next.html">Read the next chapter</a>'
    b'<a href="https://example.com/guide/other.html?utm_source=feed">Tracked link</a>'
    b"</main></body></html>"
)

JOB_BODY = (
    b'<html><head><script type="application/ld+json">'
    b'{"@context":"https://schema.org","@type":"JobPosting",'
    b'"title":"Landing page refresh",'
    b'"description":"<p>Build a small landing page with React.</p>",'
    b'"datePosted":"2026-10-05T12:00:00Z",'
    b'"validThrough":"2026-10-06T12:00:00Z",'
    b'"baseSalary":{"currency":"USD","value":{"minValue":50,"maxValue":60}},'
    b'"skills":"React, CSS","deliveryType":"one_off",'
    b'"estimatedEffortHours":4,"requiredMeetings":1}'
    b"</script></head><body><main>"
    b"<p>" + b"Deterministic acceptable extraction content for the job fixture. " * 40 + b"</p>"
    b"</main></body></html>"
)

GOOD_DIMENSIONS: dict[str, Any] = {
    "fit": 90,
    "expected_value": 88,
    "completion_probability": 86,
    "effort_efficiency": 84,
    "time_to_delivery": 82,
    "competition": 20,
    "ambiguity": 15,
    "risk": 10,
    "reason": "Strong fit for a short one-off gig.",
}
EXPECTED_OVERALL = "86.55"


async def healthy_probe() -> None:
    return None


class RecordingPublisher:
    def __init__(self) -> None:
        self.events: list[tuple[UUID, EventEnvelope]] = []

    async def publish(self, user_id: UUID, event: EventEnvelope) -> None:
        self.events.append((user_id, event))


class StageBackend:
    """Deterministic local stage double; counts calls and never touches the network."""

    def __init__(self, body: bytes) -> None:
        self.body = body
        self.calls = 0

    async def acquire(self, request: Any) -> AcquisitionResult:
        self.calls += 1
        return AcquisitionResult(
            FetchResponse(request.target_url, "text/html; charset=utf-8", self.body),
            retry_count=0,
            budget_used={
                "requests": 1,
                "pages": 1,
                "bytes_received": len(self.body),
            },
        )


class StubOpportunityProvider:
    name = "stub"
    model = "stub-opportunity-v1"

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls = 0

    async def evaluate(
        self, request: OpportunityEvaluationRequest, *, repair_error: str | None = None
    ) -> ProviderResponse:
        del request, repair_error
        self.calls += 1
        content = json.dumps(self.payload)
        return ProviderResponse(content, ProviderUsage(10, 20, 30))


@pytest.fixture
async def final_engine() -> AsyncIterator[AsyncEngine]:
    database_url = os.environ["TEST_DATABASE_URL"]
    assert "_test" in database_url.rsplit("/", maxsplit=1)[-1]
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    yield engine
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    await engine.dispose()


async def create_owner(
    engine: AsyncEngine, *, radar_type: RadarType, threshold: int
) -> tuple[UUID, UUID, UUID, UUID]:
    """Create user, radar, source and state; returns (user, radar, source, state ids)."""
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User(
            id=uuid4(),
            email=f"final-{uuid4()}@example.com",
            password_hash="synthetic",  # noqa: S106 - isolated database fixture
            display_name="Final",
        )
        radar = Radar(
            id=uuid4(),
            user_id=user.id,
            name=f"Final {uuid4()}",
            goal="Close the ACQ-1 value loop offline",
            radar_type=radar_type,
            categories=[],
            keywords=["offline"],
            status=ResourceStatus.ACTIVE,
            notification_threshold=threshold,
        )
        source = Source(
            id=uuid4(),
            user_id=user.id,
            name="Final Source",
            source_type=SourceType.URL,
            url=SEED,
            normalized_url=SEED,
            source_family=(
                SourceFamily.OPPORTUNITY
                if radar_type == RadarType.OPPORTUNITY
                else SourceFamily.GENERIC_WEB
            ),
            acquisition_mode=AcquisitionMode.AUTO,
            acquisition_profile=AcquisitionProfileV1().storage_dict(),
        )
        session.add(user)
        await session.flush()
        session.add_all([radar, source])
        await session.flush()
        session.add(RadarSource(radar_id=radar.id, source_id=source.id))
        session.add(SourceAcquisitionState(source_id=source.id))
        await session.commit()
        return user.id, radar.id, source.id, uuid4()


async def queue_and_run(
    engine: AsyncEngine, source_id: UUID, body: bytes
) -> tuple[UUID, StageBackend]:
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
        run_id = run.id
    backend = StageBackend(body)
    repository = SqlAlchemyAcquisitionRunRepository(factory)
    ok = await execute_route_run(
        repository, run_id, backends={BackendName.NATIVE_HTTP: backend}, task_id="final-e2e"
    )
    assert ok is True
    return run_id, backend


class TestRoutedIntelligenceValueLoop:
    @pytest.mark.asyncio
    async def test_routed_intelligence_value_loop(self, final_engine: AsyncEngine) -> None:
        settings = Settings()
        user_id, _radar_id, source_id, _ = await create_owner(
            final_engine, radar_type=RadarType.TECHNOLOGY, threshold=0
        )
        factory = async_sessionmaker(final_engine, expire_on_commit=False)
        async with factory() as session:
            source = await session.get(Source, source_id)
            assert source is not None
            profile = AcquisitionProfileV1()
            profile.resource_budget.max_depth = 1
            profile.resource_budget.max_pages = 3
            source.discovery_mode = DiscoveryMode.SAME_PATH
            source.acquisition_profile = profile.storage_dict()
            await session.commit()

        run_id, backend = await queue_and_run(final_engine, source_id, INTEL_BODY)
        assert backend.calls == 1

        async with factory() as session:
            run = await session.get(CollectionRun, run_id)
            state = await session.get(SourceAcquisitionState, source_id)
            assert run is not None and state is not None
            assert run.status == CollectionRunStatus.SUCCEEDED
            assert run.backend == "native_http"
            assert run.fallback_count == 0
            summary = run.budget_summary
            assert summary["decision_version"] == "router-v1"
            assert summary["accepted_backend"] == "native_http"
            assert summary["fallbacks"] == 0
            assert "://" not in json.dumps(summary["trace"])
            assert summary["discovery"]["scope"] == "same_path"
            # Discovery planned the in-scope links; I2 crawl execution did not happen.
            frontier = state.checkpoint["frontier"]
            assert {entry["url"] for entry in frontier} == {
                "https://example.com/guide/next.html",
                "https://example.com/guide/other.html?utm_source=feed",
            }
            attempt_count = await session.scalar(
                select(func.count()).select_from(AcquisitionAttempt)
            )
            assert attempt_count == 1
            raw_ids = list(
                (
                    await session.scalars(select(RawItem.id).where(RawItem.source_id == source_id))
                ).all()
            )
            assert len(raw_ids) == 1
            artifact = await session.scalar(
                select(SourceArtifact).where(SourceArtifact.source_id == source_id)
            )
            assert artifact is not None
            snapshot_count = await session.scalar(
                select(func.count())
                .select_from(AcquisitionSnapshot)
                .where(AcquisitionSnapshot.artifact_id == artifact.id)
            )
            assert snapshot_count == 1
            event = await session.scalar(
                select(ChangeEvent).where(ChangeEvent.artifact_id == artifact.id)
            )
            assert event is not None and event.change_type == "created"

        cleaned = await clean_raw_item(factory, raw_ids[0])
        assert cleaned.document_id is not None
        assert len(cleaned.analysis_ids) == 1
        analysis_provider = FakeAnalysisProvider(settings.ai_model)
        assert await run_analysis(factory, cleaned.analysis_ids[0], analysis_provider, settings)
        embedding_provider = FakeEmbeddingProvider(settings.embedding_model)
        assert await run_embedding(factory, cleaned.document_id, embedding_provider, settings)
        publisher = RecordingPublisher()
        assert await dispatch_notifications(factory, publisher) == 1
        assert any(event.event_type == "notification.created" for _, event in publisher.events)

        async with factory() as session:
            notification = await session.scalar(select(Notification))
            assert notification is not None
            assert notification.analysis_id == cleaned.analysis_ids[0]
            assert notification.opportunity_score_id is None

        app = create_app(settings, readiness_service=ReadinessService(healthy_probe, healthy_probe))
        app.state.session_factory = factory
        headers = {"Authorization": f"Bearer {create_access_token(user_id, settings)}"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            intelligence = await client.get("/api/v1/intelligence", headers=headers)
            assert intelligence.status_code == 200
            assert intelligence.json()["total"] == 1
            notifications = await client.get("/api/v1/notifications", headers=headers)
            assert notifications.status_code == 200
            entry = notifications.json()["items"][0]
            assert entry["kind"] == "intelligence"
            assert entry["opportunity_id"] is None
            assert entry["analysis_id"] == str(cleaned.analysis_ids[0])


class TestOpportunityValueLoop:
    @pytest.mark.asyncio
    async def test_opportunity_value_loop(self, final_engine: AsyncEngine) -> None:
        settings = Settings()
        user_id, _radar_id, source_id, _ = await create_owner(
            final_engine, radar_type=RadarType.OPPORTUNITY, threshold=75
        )
        factory = async_sessionmaker(final_engine, expire_on_commit=False)

        run_id, backend = await queue_and_run(final_engine, source_id, JOB_BODY)
        assert backend.calls == 1
        async with factory() as session:
            run = await session.get(CollectionRun, run_id)
            assert run is not None
            assert run.status == CollectionRunStatus.SUCCEEDED
            assert run.budget_summary["accepted_backend"] == "native_http"
            item = await session.scalar(
                select(OpportunityItem).where(OpportunityItem.source_id == source_id)
            )
            assert item is not None
            assert item.title == "Landing page refresh"
            assert item.currency == "USD"
            assert float(item.estimated_effort_hours) == 4.0

        provider = StubOpportunityProvider(GOOD_DIMENSIONS)
        completed = await dispatch_pending_opportunities(factory, provider, settings, now=NOW)
        assert completed == 1 and provider.calls == 1

        async with factory() as session:
            score = await session.scalar(select(OpportunityScore))
            assert score is not None
            assert str(score.overall_score) == EXPECTED_OVERALL
            assert score.recommendation == "act_now"
            assert score.hard_filter_passed is True
            notification = await session.scalar(select(Notification))
            assert notification is not None
            assert notification.opportunity_score_id == score.id
            assert notification.analysis_id is None

        app = create_app(settings, readiness_service=ReadinessService(healthy_probe, healthy_probe))
        app.state.session_factory = factory
        headers = {"Authorization": f"Bearer {create_access_token(user_id, settings)}"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            listing = await client.get("/api/v1/opportunities", headers=headers)
            assert listing.status_code == 200
            assert listing.json()["total"] == 1
            entry = listing.json()["items"][0]
            assert entry["score"]["recommendation"] == "act_now"
            opportunity_id = entry["id"]
            payload = await client.get(
                f"/api/v1/opportunities/{opportunity_id}/action-payload", headers=headers
            )
            assert payload.status_code == 200
            document = payload.json()
            assert document["payload"]["requires_human_approval"] is True
            assert document["payload"]["recommended_action"] == "act_now"
            notifications = await client.get("/api/v1/notifications", headers=headers)
            assert notifications.status_code == 200
            notification_entry = notifications.json()["items"][0]
            assert notification_entry["kind"] == "opportunity"
            assert notification_entry["opportunity_id"] == opportunity_id
            assert notification_entry["analysis_id"] is None


class TestDisabledCapabilitiesStayClosed:
    def test_disabled_capabilities_stay_closed(self) -> None:
        assert BROWSER_DYNAMIC_ENABLED is False
        with pytest.raises(CollectionError) as browser:
            select_candidates(
                source_type=SourceType.URL, mode=AcquisitionMode.AUTO, allow_browser=True
            )
        assert browser.value.code == "acquisition_browser_not_admitted"
        with pytest.raises(CollectionError) as dynamic:
            select_candidates(
                source_type=SourceType.URL, mode=AcquisitionMode.DYNAMIC, allow_browser=False
            )
        assert dynamic.value.code == "acquisition_mode_unsupported"
        candidates = select_candidates(
            source_type=SourceType.URL, mode=AcquisitionMode.AUTO, allow_browser=False
        )
        assert {candidate.backend for candidate in candidates}.isdisjoint(
            {BackendName.DYNAMIC_BROWSER, BackendName.ADVANCED_BROWSER}
        )
        # Change I2 (RawItem writer switch) is not admitted: the column must not exist.
        assert "snapshot_id" not in RawItem.__table__.columns
