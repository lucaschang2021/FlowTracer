"""ACQ-1 closure Phase 4 acceptance matrix (docs/71 §Phase 4, docs/65 §0 I2, ADR-041).

WP-7 opportunity closure:

4.1 real inputs — ChangeEvent-driven ingestion (content changes refresh the item in
    place) and crawl-page outputs feed opportunity items through the production path;
4.2 lifecycle — removed / expired transitions, re-evaluation with a new
    ``evaluation_version`` score + payload + notification, unchanged items stay scored;
4.3 contract — REST surface, notification facts and the human-approval boundary stay
    frozen (payload key set, requires_human_approval);
4.4 prohibitions — no FX conversion (non-USD disqualifies without any lookup), no
    execution surfaces anywhere in the payload or the schema.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.core.security import create_access_token
from app.domains.opportunity_policy import (
    PAYLOAD_VERSION,
    PROFILE_VERSION,
    SCORE_VERSION,
)
from app.domains.provider_ports import (
    OpportunityEvaluationRequest,
    ProviderResponse,
    ProviderUsage,
)
from app.main import create_app
from app.models.entities import (
    AcquisitionMode,
    AIUsageRecord,
    BackendName,
    CollectionRun,
    CollectionRunStatus,
    CollectionTriggerType,
    DiscoveryMode,
    Radar,
    RadarSource,
    RadarType,
    ResourceStatus,
    Source,
    SourceAcquisitionState,
    SourceFamily,
    SourceType,
    User,
)
from app.models.notification import Notification
from app.models.opportunity import (
    OpportunityActionPayload,
    OpportunityItem,
    OpportunityScore,
)
from app.schemas.resources import AcquisitionProfileV1
from app.services.acquisition_route import execute_route_run
from app.services.acquisition_run_repository import SqlAlchemyAcquisitionRunRepository
from app.services.acquisition_types import ParseResult, RawCandidate
from app.services.change_tracking import EvidenceResult, EvidenceWrite, record_version_evidence
from app.services.native_acquisition import NativeAcquisitionBackend, SafeCrawlTransport
from app.services.opportunity_evaluation import (
    dispatch_pending_opportunities,
    evaluate_opportunity,
)
from app.services.opportunity_ingest import record_opportunity_items
from app.services.readiness import ReadinessService
from app.services.safe_fetcher import SafeFetcher, WireResponse

TABLES = (
    "notifications, ai_usage_records, opportunity_action_payloads, opportunity_scores, "
    "opportunities, change_events, acquisition_snapshots, source_artifacts, "
    "acquisition_attempts, source_acquisition_states, document_chunks, bookmarks, analyses, "
    "documents, raw_items, radar_sources, collection_runs, sources, radars, refresh_tokens, users"
)
PUBLIC_IP = "93.184.216.34"
NOW = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)
JOB_URL = "https://jobs.example.com/gig-1"

GOOD_DIMS: dict[str, Any] = {
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
EXPECTED_OVERALL = Decimal("86.55")

SALARY_JSONLD = b'"baseSalary":{"currency":"USD","value":{"minValue":50,"maxValue":60}},'

JOB_HTML = (
    b'<html><head><script type="application/ld+json">'
    b'{"@context":"https://schema.org","@type":"JobPosting",'
    b'"title":"Landing page refresh",'
    b'"description":"<p>Build a small landing page with React.</p>",'
    b'"datePosted":"2026-10-05T12:00:00Z",'
    b'"validThrough":"2026-10-07T12:00:00Z",'
    + SALARY_JSONLD
    + b'"skills":"React, CSS","deliveryType":"one_off",'
    b'"estimatedEffortHours":4,"requiredMeetings":1}'
    b"</script></head><body>Job fixture body</body></html>"
)

# Same artifact, changed content: refreshed budget/description/deadline.
JOB_HTML_V2 = (
    b'<html><head><script type="application/ld+json">'
    b'{"@context":"https://schema.org","@type":"JobPosting",'
    b'"title":"Landing page refresh (updated)",'
    b'"description":"<p>Build a small landing page with React and Tailwind.</p>",'
    b'"datePosted":"2026-10-05T12:00:00Z",'
    b'"validThrough":"2026-10-07T12:00:00Z",'
    b'"baseSalary":{"currency":"USD","value":{"minValue":55,"maxValue":65}},'
    b'"skills":"React, Tailwind","deliveryType":"one_off",'
    b'"estimatedEffortHours":5,"requiredMeetings":1}'
    b"</script></head><body>Job fixture body updated</body></html>"
)

CANDIDATE = RawCandidate(
    external_id="gig-1",
    canonical_url=JOB_URL,
    raw_text="Landing page refresh Build a small landing page with React.",
    content_type="text/html; charset=utf-8",
    title="Landing page refresh",
)
CANDIDATE_V2 = RawCandidate(
    external_id="gig-1",
    canonical_url=JOB_URL,
    raw_text="Landing page refresh (updated) Build a small landing page with React and Tailwind.",
    content_type="text/html; charset=utf-8",
    title="Landing page refresh (updated)",
)


async def public_resolver(_hostname: str) -> list[str]:
    return [PUBLIC_IP]


class ScriptedOpportunityProvider:
    """Per-call script: a dict is a payload, an Exception is raised."""

    name = "scripted"
    model = "scripted-opportunity-v1"

    def __init__(self, script: list[Any]) -> None:
        self.script = script
        self.calls = 0

    async def evaluate(
        self, request: OpportunityEvaluationRequest, *, repair_error: str | None = None
    ) -> ProviderResponse:
        del request, repair_error
        index = min(self.calls, len(self.script) - 1)
        entry = self.script[index]
        self.calls += 1
        if isinstance(entry, Exception):
            raise entry
        return ProviderResponse(json.dumps(entry), ProviderUsage(10, 20, 30))


class SiteTransport:
    """Deterministic crawl transport for the JSON-LD pages (robots 404 = respect)."""

    def __init__(self, pages: dict[str, tuple[str, bytes]]) -> None:
        self.pages = pages
        self.requests: list[str] = []

    async def __call__(self, *, url: str, **_kwargs: Any) -> WireResponse:
        self.requests.append(url)
        path = url.split("jobs.example.com", 1)[-1] or "/"
        if path == "/robots.txt":
            return WireResponse(404, {"content-type": "text/plain"}, b"")
        entry = self.pages.get(path)
        if entry is None:
            return WireResponse(404, {"content-type": "text/html"}, b"")
        content_type, body = entry
        return WireResponse(200, {"content-type": content_type}, body)


@pytest.fixture
async def closure_p4_engine() -> AsyncIterator[AsyncEngine]:
    database_url = os.environ["TEST_DATABASE_URL"]
    assert "_test" in database_url.rsplit("/", maxsplit=1)[-1]
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    yield engine
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    await engine.dispose()


async def create_context(
    engine: AsyncEngine,
    *,
    threshold: int = 75,
    url: str = JOB_URL,
    discovery_mode: DiscoveryMode = DiscoveryMode.SINGLE_PAGE,
    max_pages: int = 1,
) -> tuple[UUID, UUID, UUID]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User(
            id=uuid4(),
            email=f"closure-p4-{uuid4()}@example.com",
            password_hash="synthetic",  # noqa: S106 - isolated database fixture
            display_name="Closure P4",
        )
        radar = Radar(
            id=uuid4(),
            user_id=user.id,
            name=f"Freelance {uuid4()}",
            goal="Find short freelance gigs",
            radar_type=RadarType.OPPORTUNITY,
            categories=[],
            keywords=["react"],
            status=ResourceStatus.ACTIVE,
            notification_threshold=threshold,
        )
        profile = AcquisitionProfileV1()
        profile.resource_budget.max_pages = max_pages
        profile.resource_budget.max_depth = 1
        source = Source(
            id=uuid4(),
            user_id=user.id,
            name="Jobs Board",
            source_type=SourceType.URL,
            url=url,
            normalized_url=url,
            source_family=SourceFamily.OPPORTUNITY,
            acquisition_mode=AcquisitionMode.AUTO,
            discovery_mode=discovery_mode,
            acquisition_profile=profile.storage_dict(),
        )
        session.add(user)
        await session.flush()
        session.add_all([radar, source])
        await session.flush()
        session.add(RadarSource(radar_id=radar.id, source_id=source.id))
        session.add(SourceAcquisitionState(source_id=source.id))
        await session.commit()
        return user.id, radar.id, source.id


async def observe(
    engine: AsyncEngine,
    *,
    source_id: UUID,
    body: bytes = JOB_HTML,
    candidate: RawCandidate = CANDIDATE,
    fetched_at: datetime = NOW,
) -> EvidenceResult:
    """Mirror one acquisition success: evidence + opportunity ingest in one transaction."""
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        source = await session.get(Source, source_id)
        assert source is not None
        run = CollectionRun(
            id=uuid4(),
            source_id=source.id,
            trigger_type=CollectionTriggerType.MANUAL,
            status=CollectionRunStatus.RUNNING,
            claim_token=uuid4(),
            worker_id="closure-p4",
            lease_expires_at=fetched_at + timedelta(minutes=10),
        )
        session.add(run)
        await session.flush()
        evidence = await record_version_evidence(
            session,
            run=run,
            parsed=ParseResult(candidates=[candidate]),
            body=body,
            quality_score=Decimal("0.8000"),
            fetched_at=fetched_at,
        )
        await record_opportunity_items(session, source=source, evidence=evidence, body=body)
        await session.commit()
        return evidence


async def dispatch(
    engine: AsyncEngine,
    provider: ScriptedOpportunityProvider | None = None,
    *,
    now: datetime = NOW,
) -> int:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return await dispatch_pending_opportunities(
        factory, provider or ScriptedOpportunityProvider([GOOD_DIMS]), Settings(), now=now
    )


async def only_item(engine: AsyncEngine) -> OpportunityItem:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        item = await session.scalar(select(OpportunityItem))
        assert item is not None
        return item


async def count_rows(engine: AsyncEngine, model: type[Any]) -> int:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        return int(await session.scalar(select(func.count()).select_from(model)) or 0)


async def scores_for(engine: AsyncEngine, opportunity_id: UUID) -> list[OpportunityScore]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        return list(
            (
                await session.scalars(
                    select(OpportunityScore)
                    .where(OpportunityScore.opportunity_id == opportunity_id)
                    .order_by(OpportunityScore.evaluation_version.asc())
                )
            ).all()
        )


class TestChangeDrivenLifecycle:
    @pytest.mark.asyncio
    async def test_content_change_refreshes_item_and_reevaluates(
        self, closure_p4_engine: AsyncEngine
    ) -> None:
        user_id, radar_id, source_id = await create_context(closure_p4_engine)
        await observe(closure_p4_engine, source_id=source_id)
        first_item = await only_item(closure_p4_engine)
        assert await dispatch(closure_p4_engine, now=NOW) == 1
        scores = await scores_for(closure_p4_engine, first_item.id)
        assert [score.evaluation_version for score in scores] == [1]
        assert scores[0].score_version == SCORE_VERSION

        # A changed observation refreshes the same item and re-enters the queue.
        await observe(
            closure_p4_engine,
            source_id=source_id,
            body=JOB_HTML_V2,
            candidate=CANDIDATE_V2,
            fetched_at=NOW + timedelta(minutes=30),
        )
        refreshed = await only_item(closure_p4_engine)
        assert refreshed.id == first_item.id  # one item per artifact, updated in place
        assert refreshed.title == "Landing page refresh (updated)"
        assert refreshed.budget_max == Decimal("65.00")
        assert refreshed.updated_at > first_item.updated_at
        assert await dispatch(closure_p4_engine, now=NOW + timedelta(minutes=30)) == 1
        scores = await scores_for(closure_p4_engine, refreshed.id)
        assert [score.evaluation_version for score in scores] == [1, 2]
        assert await count_rows(closure_p4_engine, OpportunityItem) == 1
        assert await count_rows(closure_p4_engine, OpportunityActionPayload) == 2
        assert await count_rows(closure_p4_engine, Notification) == 2
        assert user_id and radar_id and PROFILE_VERSION

    @pytest.mark.asyncio
    async def test_unchanged_observation_stays_scored(self, closure_p4_engine: AsyncEngine) -> None:
        _user_id, _radar_id, source_id = await create_context(closure_p4_engine)
        await observe(closure_p4_engine, source_id=source_id)
        assert await dispatch(closure_p4_engine, now=NOW) == 1
        await observe(
            closure_p4_engine,
            source_id=source_id,
            fetched_at=NOW + timedelta(minutes=30),
        )
        assert await dispatch(closure_p4_engine, now=NOW + timedelta(minutes=30)) == 0
        item = await only_item(closure_p4_engine)
        assert len(await scores_for(closure_p4_engine, item.id)) == 1

    @pytest.mark.asyncio
    async def test_removed_then_reappearance_reactivates(
        self, closure_p4_engine: AsyncEngine
    ) -> None:
        _user_id, _radar_id, source_id = await create_context(closure_p4_engine)
        await observe(closure_p4_engine, source_id=source_id)
        item = await only_item(closure_p4_engine)
        assert await dispatch(closure_p4_engine, now=NOW) == 1

        # A removed observation marks the item; the queue skips it.
        factory = async_sessionmaker(closure_p4_engine, expire_on_commit=False)
        async with factory() as session:
            source = await session.get(Source, source_id)
            assert source is not None
            await record_opportunity_items(
                session,
                source=source,
                evidence=EvidenceResult(
                    events=1,
                    writes=(
                        EvidenceWrite(
                            artifact_id=item.artifact_id,
                            snapshot_id=item.snapshot_id,
                            change_type="removed",
                            candidate=CANDIDATE,
                        ),
                    ),
                ),
                body=None,
            )
            await session.commit()
        assert (await only_item(closure_p4_engine)).status == "removed"
        assert await dispatch(closure_p4_engine, now=NOW + timedelta(minutes=45)) == 0

        # A content change after reappearance reactivates and re-evaluates.
        await observe(
            closure_p4_engine,
            source_id=source_id,
            body=JOB_HTML_V2,
            candidate=CANDIDATE_V2,
            fetched_at=NOW + timedelta(hours=1),
        )
        reactivated = await only_item(closure_p4_engine)
        assert reactivated.status == "active"
        assert await dispatch(closure_p4_engine, now=NOW + timedelta(hours=1)) == 1
        assert [s.evaluation_version for s in await scores_for(closure_p4_engine, item.id)] == [
            1,
            2,
        ]

    @pytest.mark.asyncio
    async def test_expired_items_leave_the_queue(self, closure_p4_engine: AsyncEngine) -> None:
        past_deadline_job = (
            b'<html><head><script type="application/ld+json">'
            b'{"@context":"https://schema.org","@type":"JobPosting",'
            b'"title":"Expired gig",'
            b'"description":"<p>Old gig.</p>",'
            b'"datePosted":"2026-10-01T12:00:00Z",'
            b'"validThrough":"2026-10-05T12:00:00Z",'
            b'"baseSalary":{"currency":"USD","value":{"minValue":50,"maxValue":60}},'
            b'"skills":"React","deliveryType":"one_off"}'
            b"</script></head><body>Old job fixture body</body></html>"
        )
        _user_id, _radar_id, source_id = await create_context(closure_p4_engine)
        await observe(
            closure_p4_engine,
            source_id=source_id,
            body=past_deadline_job,
            candidate=RawCandidate(
                external_id="gig-old",
                canonical_url=JOB_URL,
                raw_text="Expired gig Old gig.",
                content_type="text/html; charset=utf-8",
                title="Expired gig",
            ),
        )
        assert await dispatch(closure_p4_engine) == 0
        item = await only_item(closure_p4_engine)
        assert item.status == "expired"
        assert await count_rows(closure_p4_engine, OpportunityScore) == 0
        assert await count_rows(closure_p4_engine, Notification) == 0
        assert (
            await evaluate_opportunity(
                async_sessionmaker(closure_p4_engine, expire_on_commit=False),
                opportunity_id=item.id,
                radar_id=(await _radar_for(closure_p4_engine, item)),
                provider=ScriptedOpportunityProvider([GOOD_DIMS]),
                settings=Settings(),
            )
            == "skipped"
        )


async def _radar_for(engine: AsyncEngine, item: OpportunityItem) -> UUID:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        radar_id = await session.scalar(
            select(RadarSource.radar_id).where(RadarSource.source_id == item.source_id)
        )
        assert radar_id is not None
        return radar_id


class TestCrawlInputs:
    @pytest.mark.asyncio
    async def test_crawl_pages_feed_opportunity_items(self, closure_p4_engine: AsyncEngine) -> None:
        seed_page = (
            b"<html><head><title>Board index</title></head><body><main>"
            + b"Job board index listing the newest gigs. " * 30
            + b'<a href="/gig-2.html">Open the newest gig</a>'
            + b"</main></body></html>"
        )
        child_page = (
            b'<html><head><script type="application/ld+json">'
            b'{"@context":"https://schema.org","@type":"JobPosting",'
            b'"title":"CSS cleanup",'
            b'"description":"<p>Tidy a small CSS codebase.</p>",'
            b'"datePosted":"2026-10-05T12:00:00Z",'
            b'"validThrough":"2026-10-07T12:00:00Z",'
            b'"baseSalary":{"currency":"USD","value":{"minValue":45,"maxValue":55}},'
            b'"skills":"CSS","deliveryType":"one_off","estimatedEffortHours":3}'
            b"</script></head><body>"
            + b"Crawl child opportunity body content. " * 30
            + b"</body></html>"
        )
        _user_id, _radar_id, source_id = await create_context(
            closure_p4_engine,
            discovery_mode=DiscoveryMode.SAME_DOMAIN,
            max_pages=3,
        )
        transport = SiteTransport(
            {
                "/gig-1": ("text/html; charset=utf-8", seed_page),
                "/gig-2.html": ("text/html; charset=utf-8", child_page),
            }
        )
        factory = async_sessionmaker(closure_p4_engine, expire_on_commit=False)
        run_id = await _queue_run(closure_p4_engine, source_id)
        ok = await execute_route_run(
            SqlAlchemyAcquisitionRunRepository(factory),
            run_id,
            backends={
                BackendName.NATIVE_HTTP: NativeAcquisitionBackend(
                    SafeFetcher(resolver=public_resolver, transport=transport)
                )
            },
            task_id="closure-p4-crawl",
            discovery_transport=SafeCrawlTransport(
                SafeFetcher(resolver=public_resolver, transport=transport)
            ),
        )
        assert ok is True
        # The seed page contributes a title-only item and the crawled page's JSON-LD
        # becomes a fully extractable opportunity item through the crawl path.
        items = await _all_items(closure_p4_engine)
        by_title = {item.title: item for item in items}
        assert set(by_title) == {"Board index", "CSS cleanup"}
        assert by_title["CSS cleanup"].source_url == "https://jobs.example.com/gig-2.html"
        # Dispatch scores both pairs (the title-only seed dismisses on insufficient data).
        assert await dispatch(closure_p4_engine) == 2
        assert await count_rows(closure_p4_engine, OpportunityActionPayload) == 1


async def _item_for_source(engine: AsyncEngine, source_id: UUID) -> OpportunityItem:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        item = await session.scalar(
            select(OpportunityItem).where(OpportunityItem.source_id == source_id)
        )
        assert item is not None
        return item


async def _queue_run(engine: AsyncEngine, source_id: UUID) -> UUID:
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


async def _all_items(engine: AsyncEngine) -> list[OpportunityItem]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        return list((await session.scalars(select(OpportunityItem))).all())


class TestContractAndProhibitions:
    async def _app(self, engine: AsyncEngine) -> Any:
        factory = async_sessionmaker(engine, expire_on_commit=False)

        async def healthy() -> None:
            return None

        app = create_app(Settings(), readiness_service=ReadinessService(healthy, healthy))
        app.state.session_factory = factory
        return app

    @pytest.mark.asyncio
    async def test_rest_status_filters_payload_boundary_and_ownership(
        self, closure_p4_engine: AsyncEngine
    ) -> None:
        user_id, radar_id, source_id = await create_context(closure_p4_engine)
        await observe(closure_p4_engine, source_id=source_id)
        assert await dispatch(closure_p4_engine, now=NOW) == 1
        item = await only_item(closure_p4_engine)
        app = await self._app(closure_p4_engine)
        settings = Settings()
        headers = {"Authorization": f"Bearer {create_access_token(user_id, settings)}"}
        stranger = await create_context(closure_p4_engine)
        stranger_headers = {"Authorization": f"Bearer {create_access_token(stranger[0], settings)}"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            active = await client.get(
                f"/api/v1/opportunities?radar_id={radar_id}&status=active", headers=headers
            )
            assert active.status_code == 200
            assert active.json()["total"] == 1
            entry = active.json()["items"][0]
            assert Decimal(str(entry["score"]["overall_score"])) == EXPECTED_OVERALL
            assert "raw_text" not in entry and "</html>" not in active.text

            detail = await client.get(f"/api/v1/opportunities/{item.id}", headers=headers)
            assert detail.status_code == 200

            payload = await client.get(
                f"/api/v1/opportunities/{item.id}/action-payload", headers=headers
            )
            assert payload.status_code == 200
            body = payload.json()
            assert body["payload_version"] == PAYLOAD_VERSION
            assert body["payload"]["requires_human_approval"] is True
            # Frozen key set: no execution, bidding, quoting or payment surfaces.
            assert set(body["payload"]) == {
                "payload_version",
                "opportunity_id",
                "source",
                "title",
                "description",
                "budget",
                "skills",
                "deadline",
                "score",
                "risk",
                "source_url",
                "recommended_action",
                "requires_human_approval",
                "context",
                "generated_at",
            }
            serialized = json.dumps(body["payload"]).lower()
            for forbidden in ("submit", "bid", "quote", "payment", "credentials"):
                assert forbidden not in serialized

            # Removal flips the status filter view without dropping history.
            factory = async_sessionmaker(closure_p4_engine, expire_on_commit=False)
            async with factory() as session:
                source = await session.get(Source, source_id)
                assert source is not None
                await record_opportunity_items(
                    session,
                    source=source,
                    evidence=EvidenceResult(
                        events=1,
                        writes=(
                            EvidenceWrite(
                                artifact_id=item.artifact_id,
                                snapshot_id=item.snapshot_id,
                                change_type="removed",
                                candidate=CANDIDATE,
                            ),
                        ),
                    ),
                    body=None,
                )
                await session.commit()
            removed = await client.get("/api/v1/opportunities?status=removed", headers=headers)
            assert removed.status_code == 200 and removed.json()["total"] == 1

            # Ownership: strangers see nothing (404), and payload absence is explicit.
            assert (
                await client.get(f"/api/v1/opportunities/{item.id}", headers=stranger_headers)
            ).status_code == 404

            # A second owner with an unscored item exposes the payload-absence 404.
            other_user, _other_radar, other_source = await create_context(closure_p4_engine)
            await observe(closure_p4_engine, source_id=other_source)
            other_item = await _item_for_source(closure_p4_engine, other_source)
            other_headers = {"Authorization": f"Bearer {create_access_token(other_user, settings)}"}
            unavailable = await client.get(
                f"/api/v1/opportunities/{other_item.id}/action-payload", headers=other_headers
            )
            assert unavailable.status_code == 404

    @pytest.mark.asyncio
    async def test_non_usd_never_converts_and_no_fx_surface(
        self, closure_p4_engine: AsyncEngine
    ) -> None:
        eur_job = (
            b'<html><head><script type="application/ld+json">'
            b'{"@context":"https://schema.org","@type":"JobPosting",'
            b'"title":"Euro gig",'
            b'"description":"<p>Euro priced gig.</p>",'
            b'"datePosted":"2026-10-05T12:00:00Z",'
            b'"validThrough":"2026-10-08T12:00:00Z",'
            b'"baseSalary":{"currency":"EUR","value":{"minValue":50,"maxValue":60}},'
            b'"skills":"React","deliveryType":"one_off"}'
            b"</script></head><body>Euro job fixture body</body></html>"
        )
        _user_id, radar_id, source_id = await create_context(closure_p4_engine)
        await observe(
            closure_p4_engine,
            source_id=source_id,
            body=eur_job,
            candidate=RawCandidate(
                external_id="gig-eur",
                canonical_url=JOB_URL,
                raw_text="Euro gig Euro priced gig.",
                content_type="text/html; charset=utf-8",
                title="Euro gig",
            ),
        )
        provider = ScriptedOpportunityProvider([GOOD_DIMS])
        assert await dispatch(closure_p4_engine, provider) == 1  # dismissed counts as handled
        assert provider.calls == 0  # no FX lookup, no conversion, no AI call
        item = await only_item(closure_p4_engine)
        score = (await scores_for(closure_p4_engine, item.id))[0]
        assert score.hard_filter_passed is False
        assert "currency_unsupported" in score.disqualifiers
        assert score.recommendation == "dismiss"
        assert await count_rows(closure_p4_engine, AIUsageRecord) == 0
        assert await count_rows(closure_p4_engine, OpportunityActionPayload) == 0
        assert radar_id  # context sanity

        # No FX table/profile fields exist on the source profile schema.
        fields = set(type(AcquisitionProfileV1()).model_fields)
        assert not any("fx" in name for name in fields)
