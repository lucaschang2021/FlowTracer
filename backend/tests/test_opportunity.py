"""WP-7 acceptance matrix: Opportunity Radar (docs/24, ADR-025, ADR-037).

Covers the pure freelance-v1 hard filter boundaries, score v1 formula and
recommendation bands, strict evaluation parsing with missing-value defaults,
notification qualification, the local job pipeline (extraction -> item -> hard
filter -> score -> action payload -> notification), provider retry/repair
semantics, idempotency/concurrency, the REST surface and the migration cycle with
its irreversible-data downgrade guards.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.core.security import create_access_token
from app.domains.opportunity_policy import (
    Dimensions,
    EvaluationOutputError,
    OpportunityFacts,
    hard_filter,
    notification_qualified,
    overall_score,
    parse_evaluation,
    recommendation_for,
)
from app.domains.provider_ports import (
    OpportunityEvaluationRequest,
    ProviderError,
    ProviderResponse,
    ProviderUsage,
)
from app.main import create_app
from app.models.entities import (
    AcquisitionMode,
    AIUsageRecord,
    CollectionRun,
    CollectionRunStatus,
    CollectionTriggerType,
    Radar,
    RadarSource,
    RadarType,
    ResourceStatus,
    Source,
    SourceFamily,
    SourceType,
    User,
)
from app.models.evidence import AcquisitionSnapshot
from app.models.notification import Notification, NotificationStatus
from app.models.opportunity import (
    OpportunityActionPayload,
    OpportunityItem,
    OpportunityScore,
)
from app.models.raw_item import RawItem, RawItemStatus
from app.schemas.resources import AcquisitionProfileV1
from app.services.acquisition_types import ParseResult, RawCandidate
from app.services.change_tracking import record_version_evidence
from app.services.opportunity_evaluation import (
    dispatch_pending_opportunities,
    evaluate_opportunity,
)
from app.services.opportunity_ingest import record_opportunity_items
from app.services.readiness import ReadinessService

BACKEND = Path(__file__).resolve().parents[1]
TABLES = "users"
NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)
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
    b'"validThrough":"2026-10-06T12:00:00Z",'
    + SALARY_JSONLD
    + b'"skills":"React, CSS","deliveryType":"one_off",'
    b'"estimatedEffortHours":4,"requiredMeetings":1}'
    b"</script></head><body>Job fixture body</body></html>"
)

CANDIDATE = RawCandidate(
    external_id="gig-1",
    canonical_url="https://jobs.example.com/gig-1",
    raw_text="Landing page refresh Build a small landing page with React.",
    content_type="text/html; charset=utf-8",
    title="Landing page refresh",
)


def facts(**overrides: Any) -> OpportunityFacts:
    base: dict[str, Any] = {
        "title": "Landing page refresh",
        "description": "Build a small landing page with React.",
        "source_url": "https://jobs.example.com/gig-1",
        "platform": "jobs.example.com",
        "budget_min": Decimal("50.00"),
        "budget_max": Decimal("60.00"),
        "currency": "USD",
        "skills": ("React",),
        "deadline": NOW + timedelta(days=1),
        "published_at": NOW,
        "estimated_effort_hours": Decimal("4.00"),
        "delivery_type": "one_off",
        "required_meetings": 1,
        "maintenance_required": False,
    }
    base.update(overrides)
    return OpportunityFacts(**base)


class ScriptedOpportunityProvider:
    """Per-call script: a dict is a payload, an Exception is raised."""

    name = "scripted"
    model = "scripted-opportunity-v1"

    def __init__(self, script: list[Any]) -> None:
        self.script = script
        self.calls = 0
        self.repairs: list[str | None] = []

    async def evaluate(
        self, request: OpportunityEvaluationRequest, *, repair_error: str | None = None
    ) -> ProviderResponse:
        del request
        index = min(self.calls, len(self.script) - 1)
        entry = self.script[index]
        self.calls += 1
        self.repairs.append(repair_error)
        if isinstance(entry, Exception):
            raise entry
        content = json.dumps(entry)
        return ProviderResponse(content, ProviderUsage(10, 20, 30))


class TestHardFilterBoundaries:
    def test_required_fields_missing_is_insufficient_data(self) -> None:
        for missing in ("title", "description", "source_url", "currency"):
            outcome = hard_filter(facts(**{missing: None}))
            assert not outcome.passed
            assert outcome.disqualifiers == ("insufficient_data",)
        both_bounds = hard_filter(facts(budget_min=None, budget_max=None))
        assert both_bounds.disqualifiers == ("insufficient_data",)

    def test_budget_boundaries_and_one_sided_bounds(self) -> None:
        assert hard_filter(facts(budget_min=Decimal("10.00"), budget_max=Decimal("80.00"))).passed
        low = hard_filter(facts(budget_min=Decimal("9.99"), budget_max=Decimal("9.99")))
        assert low.disqualifiers == ("budget_out_of_profile",)
        high = hard_filter(facts(budget_min=Decimal("80.01"), budget_max=Decimal("90.00")))
        assert high.disqualifiers == ("budget_out_of_profile",)
        assert hard_filter(facts(budget_min=None, budget_max=Decimal("80.00"))).passed
        assert hard_filter(facts(budget_min=Decimal("10.00"), budget_max=None)).passed
        assert not hard_filter(facts(budget_min=None, budget_max=Decimal("9.99"))).passed
        assert not hard_filter(facts(budget_min=Decimal("80.01"), budget_max=None)).passed

    def test_currency_effort_delivery_meetings_maintenance_boundaries(self) -> None:
        assert hard_filter(facts(currency="EUR")).disqualifiers == ("currency_unsupported",)
        assert hard_filter(facts(estimated_effort_hours=Decimal("8.00"))).passed
        assert hard_filter(facts(estimated_effort_hours=Decimal("8.01"))).disqualifiers == (
            "effort_over_profile",
        )
        assert hard_filter(facts(delivery_type="one_off")).passed
        assert hard_filter(facts(delivery_type=None)).passed
        assert hard_filter(facts(delivery_type="ongoing")).disqualifiers == (
            "delivery_unsupported",
        )
        assert hard_filter(facts(required_meetings=1)).passed
        assert hard_filter(facts(required_meetings=2)).disqualifiers == ("meetings_over_profile",)
        assert hard_filter(facts(maintenance_required=None)).passed
        assert hard_filter(facts(maintenance_required=True)).disqualifiers == (
            "maintenance_required",
        )

    def test_delivery_window_boundary(self) -> None:
        exact = facts(deadline=NOW + timedelta(days=2), published_at=NOW)
        assert hard_filter(exact).passed
        beyond = facts(deadline=NOW + timedelta(days=2, seconds=1), published_at=NOW)
        assert hard_filter(beyond).disqualifiers == ("delivery_window_out_of_profile",)
        assert hard_filter(facts(deadline=None)).passed
        assert hard_filter(facts(published_at=None)).passed

    def test_prohibited_content_rejected(self) -> None:
        risky = facts(description="Please wire transfer the deposit to our payment account.")
        assert risky is not None
        assert hard_filter(risky).disqualifiers == ("prohibited_content",)
        assert hard_filter(facts(description="Build a dashboard with charts.")).passed

    def test_multiple_violations_reported_in_fixed_order(self) -> None:
        outcome = hard_filter(
            facts(
                currency="EUR",
                budget_min=Decimal("100.00"),
                budget_max=Decimal("200.00"),
                estimated_effort_hours=Decimal("12"),
                delivery_type="ongoing",
                required_meetings=3,
                maintenance_required=True,
            )
        )
        assert outcome.disqualifiers == (
            "currency_unsupported",
            "budget_out_of_profile",
            "effort_over_profile",
            "delivery_unsupported",
            "meetings_over_profile",
            "maintenance_required",
        )


class TestScoreAndRecommendation:
    def test_overall_formula_exact_values(self) -> None:
        assert overall_score(Dimensions(100, 100, 100, 100, 100, 0, 0, 0)) == Decimal("100.00")
        assert overall_score(Dimensions(0, 0, 0, 0, 0, 100, 100, 100)) == Decimal("0.00")
        dims = Dimensions(
            fit=90,
            expected_value=88,
            completion_probability=86,
            effort_efficiency=84,
            time_to_delivery=82,
            competition=20,
            ambiguity=15,
            risk=10,
        )
        assert overall_score(dims) == EXPECTED_OVERALL

    def test_recommendation_boundaries(self) -> None:
        assert recommendation_for(Decimal("100")) == "act_now"
        assert recommendation_for(Decimal("85")) == "act_now"
        assert recommendation_for(Decimal("84.99")) == "review"
        assert recommendation_for(Decimal("70")) == "review"
        assert recommendation_for(Decimal("69.99")) == "watch"
        assert recommendation_for(Decimal("50")) == "watch"
        assert recommendation_for(Decimal("49.99")) == "dismiss"

    def test_parse_evaluation_defaults_missing_dimensions(self) -> None:
        output = parse_evaluation({"fit": 90, "reason": "Partial evidence"})
        assert output.dimensions.fit == 90
        assert output.dimensions.expected_value == 0
        assert output.dimensions.competition == 100
        assert output.dimensions.risk == 100
        assert "missing dimensions defaulted" in output.reason
        assert set(output.missing) == {
            "expected_value",
            "completion_probability",
            "effort_efficiency",
            "time_to_delivery",
            "competition",
            "ambiguity",
            "risk",
        }

    def test_parse_evaluation_rejects_non_strict_values(self) -> None:
        for bad in (True, 80.5, "80", 101, -1, None):
            raw = {**GOOD_DIMS, "fit": bad}
            with pytest.raises(EvaluationOutputError):
                parse_evaluation(raw)
        with pytest.raises(EvaluationOutputError):
            parse_evaluation({**GOOD_DIMS, "unexpected": 1})
        with pytest.raises(EvaluationOutputError):
            parse_evaluation({**GOOD_DIMS, "reason": ""})

    def test_notification_qualification_matrix(self) -> None:
        base: dict[str, Any] = {
            "hard_filter_passed": True,
            "overall": Decimal("90"),
            "risk": 20,
            "ambiguity": 20,
            "opportunity_status": "active",
            "deadline": NOW + timedelta(days=1),
            "radar_threshold": 75,
            "now": NOW,
        }
        assert notification_qualified(**base)
        assert not notification_qualified(**{**base, "hard_filter_passed": False})
        assert not notification_qualified(**{**base, "overall": Decimal("84.99")})
        assert notification_qualified(**{**base, "overall": Decimal("85"), "radar_threshold": 0})
        assert not notification_qualified(**{**base, "radar_threshold": 95})
        assert not notification_qualified(**{**base, "risk": 31})
        assert notification_qualified(**{**base, "risk": 30})
        assert not notification_qualified(**{**base, "ambiguity": 41})
        assert notification_qualified(**{**base, "ambiguity": 40})
        assert not notification_qualified(**{**base, "opportunity_status": "expired"})
        assert not notification_qualified(**{**base, "deadline": NOW})
        assert not notification_qualified(**{**base, "deadline": None, "radar_active": False})
        assert not notification_qualified(**{**base, "overall": None})
        assert not notification_qualified(**{**base, "radar_active": False})


async def create_user(engine: AsyncEngine, label: str) -> UUID:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User(
            id=uuid4(),
            email=f"{label}-{uuid4()}@example.com",
            password_hash="synthetic",  # noqa: S106 - isolated database fixture
            display_name=label,
        )
        session.add(user)
        await session.commit()
        return user.id


async def create_pipeline_context(
    engine: AsyncEngine, *, threshold: int = 75
) -> tuple[UUID, UUID, UUID]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User(
            id=uuid4(),
            email=f"opportunity-{uuid4()}@example.com",
            password_hash="synthetic",  # noqa: S106 - isolated database fixture
            display_name="Opportunity",
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
        source = Source(
            id=uuid4(),
            user_id=user.id,
            name="Jobs Board",
            source_type=SourceType.URL,
            url="https://jobs.example.com/gig-1",
            normalized_url="https://jobs.example.com/gig-1",
            source_family=SourceFamily.OPPORTUNITY,
            acquisition_mode=AcquisitionMode.AUTO,
            acquisition_profile=AcquisitionProfileV1().storage_dict(),
        )
        session.add(user)
        await session.flush()
        session.add_all([radar, source])
        await session.flush()
        session.add(RadarSource(radar_id=radar.id, source_id=source.id))
        await session.commit()
        return user.id, radar.id, source.id


async def run_acquisition(
    engine: AsyncEngine,
    *,
    source_id: UUID,
    body: bytes = JOB_HTML,
    candidate: RawCandidate = CANDIDATE,
    fetched_at: datetime = NOW,
) -> None:
    """Mirror the acquisition success path for one run: evidence + opportunity ingest."""
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
            worker_id="opportunity-test",
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


@pytest.fixture
async def opportunity_engine() -> AsyncEngine:
    database_url = os.environ["TEST_DATABASE_URL"]
    assert "_test" in database_url.rsplit("/", maxsplit=1)[-1]
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    yield engine
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    await engine.dispose()


async def count_rows(engine: AsyncEngine, model: type[Any]) -> int:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        return int(await session.scalar(select(func.count()).select_from(model)) or 0)


async def evaluate(
    engine: AsyncEngine,
    *,
    opportunity_id: UUID,
    radar_id: UUID,
    provider: ScriptedOpportunityProvider,
    sleeps: list[float] | None = None,
) -> str:
    recorded = sleeps if sleeps is not None else []

    async def sleep(delay: float) -> None:
        recorded.append(delay)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    return await evaluate_opportunity(
        factory,
        opportunity_id=opportunity_id,
        radar_id=radar_id,
        provider=provider,
        settings=Settings(),
        sleep=sleep,
        now=NOW,
    )


async def only_item_id(engine: AsyncEngine) -> UUID:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        item_id = await session.scalar(select(OpportunityItem.id))
        assert item_id is not None
        return item_id


class TestLocalJobPipeline:
    @pytest.mark.asyncio
    async def test_full_pipeline_creates_item_score_payload_notification(
        self, opportunity_engine: AsyncEngine
    ) -> None:
        user_id, radar_id, source_id = await create_pipeline_context(opportunity_engine)
        await run_acquisition(opportunity_engine, source_id=source_id)
        factory = async_sessionmaker(opportunity_engine, expire_on_commit=False)
        async with factory() as session:
            item = await session.scalar(select(OpportunityItem))
            assert item is not None
            assert item.title == "Landing page refresh"
            assert item.platform == "jobs.example.com"
            assert item.budget_min == Decimal("50.00")
            assert item.budget_max == Decimal("60.00")
            assert item.currency == "USD"
            assert list(item.skills) == ["React", "CSS"]
            assert item.estimated_effort_hours == Decimal("4.00")
            assert item.delivery_type == "one_off"
            assert item.client_metadata.get("required_meetings") == 1
            assert item.status == "active"
            assert "React" in item.description
        provider = ScriptedOpportunityProvider([GOOD_DIMS])
        outcome = await evaluate(
            opportunity_engine, opportunity_id=item.id, radar_id=radar_id, provider=provider
        )
        assert outcome == "scored"
        assert provider.calls == 1
        async with factory() as session:
            score = await session.scalar(select(OpportunityScore))
            assert score is not None
            assert score.hard_filter_passed is True
            assert score.overall_score == EXPECTED_OVERALL
            assert score.recommendation == "act_now"
            assert score.risk == 10
            payload = await session.scalar(select(OpportunityActionPayload))
            assert payload is not None
            assert payload.payload["requires_human_approval"] is True
            assert payload.payload["recommended_action"] == "act_now"
            assert payload.payload["budget"]["currency"] == "USD"
            assert payload.payload["score"]["overall"] == "86.55"
            canonical = json.dumps(
                payload.payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            assert payload.payload_hash == hashlib.sha256(canonical.encode()).hexdigest()
            notification = await session.scalar(select(Notification))
            assert notification is not None
            assert notification.opportunity_score_id == score.id
            assert notification.analysis_id is None
            assert notification.status == NotificationStatus.UNREAD
            assert pg_priority(notification) == "high"
        await self._assert_usage(opportunity_engine, expected=1, succeeded=True)
        # Replay is a no-op: one score, one payload, one notification.
        replay = await evaluate(
            opportunity_engine,
            opportunity_id=item.id,
            radar_id=radar_id,
            provider=ScriptedOpportunityProvider([GOOD_DIMS]),
        )
        assert replay == "skipped"
        assert await count_rows(opportunity_engine, OpportunityScore) == 1
        assert await count_rows(opportunity_engine, OpportunityActionPayload) == 1
        assert await count_rows(opportunity_engine, Notification) == 1
        assert await count_rows(opportunity_engine, AIUsageRecord) == 1
        assert user_id is not None and source_id is not None

    async def _assert_usage(self, engine: AsyncEngine, *, expected: int, succeeded: bool) -> None:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            records = list((await session.scalars(select(AIUsageRecord))).all())
            assert len(records) == expected
            for record in records:
                assert record.task_type == "opportunity_evaluation"
                assert record.analysis_id is None
                assert record.succeeded is succeeded

    @pytest.mark.asyncio
    async def test_dispatch_task_path_scores_pending_pairs(
        self, opportunity_engine: AsyncEngine
    ) -> None:
        _user_id, _radar_id, source_id = await create_pipeline_context(opportunity_engine)
        await run_acquisition(opportunity_engine, source_id=source_id)
        factory = async_sessionmaker(opportunity_engine, expire_on_commit=False)
        provider = ScriptedOpportunityProvider([GOOD_DIMS])
        completed = await dispatch_pending_opportunities(factory, provider, Settings(), now=NOW)
        assert completed == 1
        assert provider.calls == 1


def pg_priority(notification: Notification) -> str:
    value = notification.priority
    return value.value if hasattr(value, "value") else str(value)


class TestHardFilterRejection:
    @pytest.mark.asyncio
    async def test_missing_budget_dismisses_without_ai_calls(
        self, opportunity_engine: AsyncEngine
    ) -> None:
        html = JOB_HTML.replace(SALARY_JSONLD, b"")
        _user_id, radar_id, source_id = await create_pipeline_context(opportunity_engine)
        await run_acquisition(opportunity_engine, source_id=source_id, body=html)
        item_id = await only_item_id(opportunity_engine)
        provider = ScriptedOpportunityProvider([GOOD_DIMS])
        outcome = await evaluate(
            opportunity_engine, opportunity_id=item_id, radar_id=radar_id, provider=provider
        )
        assert outcome == "dismissed"
        assert provider.calls == 0
        assert await count_rows(opportunity_engine, AIUsageRecord) == 0
        assert await count_rows(opportunity_engine, OpportunityActionPayload) == 0
        assert await count_rows(opportunity_engine, Notification) == 0
        factory = async_sessionmaker(opportunity_engine, expire_on_commit=False)
        async with factory() as session:
            score = await session.scalar(select(OpportunityScore))
            assert score is not None
            assert score.hard_filter_passed is False
            assert list(score.disqualifiers) == ["insufficient_data"]
            assert score.recommendation == "dismiss"
            assert score.overall_score is None
            assert score.fit is None


class TestProviderSemantics:
    @pytest.mark.asyncio
    async def test_repair_retries_once_then_succeeds(self, opportunity_engine: AsyncEngine) -> None:
        _user_id, radar_id, source_id = await create_pipeline_context(opportunity_engine)
        await run_acquisition(opportunity_engine, source_id=source_id)
        item_id = await only_item_id(opportunity_engine)
        provider = ScriptedOpportunityProvider([{**GOOD_DIMS, "fit": "90"}, GOOD_DIMS])
        outcome = await evaluate(
            opportunity_engine, opportunity_id=item_id, radar_id=radar_id, provider=provider
        )
        assert outcome == "scored"
        assert provider.calls == 2
        assert provider.repairs == [None, "response did not match the required strict JSON schema"]

    @pytest.mark.asyncio
    async def test_repair_is_shared_with_the_call_budget(
        self, opportunity_engine: AsyncEngine
    ) -> None:
        _user_id, radar_id, source_id = await create_pipeline_context(opportunity_engine)
        await run_acquisition(opportunity_engine, source_id=source_id)
        item_id = await only_item_id(opportunity_engine)
        invalid = {**GOOD_DIMS, "fit": "high"}
        provider = ScriptedOpportunityProvider([invalid, invalid, invalid])
        outcome = await evaluate(
            opportunity_engine, opportunity_id=item_id, radar_id=radar_id, provider=provider
        )
        assert outcome == "failed"
        assert provider.calls == 2
        assert await count_rows(opportunity_engine, OpportunityScore) == 0
        assert await count_rows(opportunity_engine, AIUsageRecord) == 2

    @pytest.mark.asyncio
    async def test_retryable_errors_backoff_then_fail(
        self, opportunity_engine: AsyncEngine
    ) -> None:
        _user_id, radar_id, source_id = await create_pipeline_context(opportunity_engine)
        await run_acquisition(opportunity_engine, source_id=source_id)
        item_id = await only_item_id(opportunity_engine)
        error = ProviderError("ai_rate_limited", "AI provider rate limited", retryable=True)
        provider = ScriptedOpportunityProvider([error, error, error])
        sleeps: list[float] = []
        outcome = await evaluate(
            opportunity_engine,
            opportunity_id=item_id,
            radar_id=radar_id,
            provider=provider,
            sleeps=sleeps,
        )
        assert outcome == "failed"
        assert provider.calls == 3
        assert sleeps == [2.0, 4.0]
        assert await count_rows(opportunity_engine, OpportunityScore) == 0
        factory = async_sessionmaker(opportunity_engine, expire_on_commit=False)
        async with factory() as session:
            records = list((await session.scalars(select(AIUsageRecord))).all())
            assert len(records) == 3
            assert all(record.succeeded is False for record in records)
            assert all(record.error_code == "ai_rate_limited" for record in records)


class TestEligibilityAndConcurrency:
    @pytest.mark.asyncio
    async def test_high_risk_scores_without_notification(
        self, opportunity_engine: AsyncEngine
    ) -> None:
        _user_id, radar_id, source_id = await create_pipeline_context(opportunity_engine)
        await run_acquisition(opportunity_engine, source_id=source_id)
        item_id = await only_item_id(opportunity_engine)
        risky = {**GOOD_DIMS, "risk": 31}
        provider = ScriptedOpportunityProvider([risky])
        outcome = await evaluate(
            opportunity_engine, opportunity_id=item_id, radar_id=radar_id, provider=provider
        )
        assert outcome == "scored"
        assert await count_rows(opportunity_engine, OpportunityScore) == 1
        assert await count_rows(opportunity_engine, OpportunityActionPayload) == 1
        assert await count_rows(opportunity_engine, Notification) == 0

    @pytest.mark.asyncio
    async def test_paused_radar_is_not_dispatched(self, opportunity_engine: AsyncEngine) -> None:
        _user_id, radar_id, source_id = await create_pipeline_context(opportunity_engine)
        await run_acquisition(opportunity_engine, source_id=source_id)
        factory = async_sessionmaker(opportunity_engine, expire_on_commit=False)
        async with factory() as session:
            radar = await session.get(Radar, radar_id)
            assert radar is not None
            radar.status = ResourceStatus.PAUSED
            await session.commit()
        provider = ScriptedOpportunityProvider([GOOD_DIMS])
        completed = await dispatch_pending_opportunities(factory, provider, Settings(), now=NOW)
        assert completed == 0
        assert provider.calls == 0
        item_id = await only_item_id(opportunity_engine)
        skipped = await evaluate(
            opportunity_engine, opportunity_id=item_id, radar_id=radar_id, provider=provider
        )
        assert skipped == "skipped"
        assert provider.calls == 0

    @pytest.mark.asyncio
    async def test_concurrent_evaluations_are_idempotent(
        self, opportunity_engine: AsyncEngine
    ) -> None:
        _user_id, radar_id, source_id = await create_pipeline_context(opportunity_engine)
        await run_acquisition(opportunity_engine, source_id=source_id)
        item_id = await only_item_id(opportunity_engine)
        first = ScriptedOpportunityProvider([GOOD_DIMS])
        second = ScriptedOpportunityProvider([GOOD_DIMS])
        outcomes = await asyncio.gather(
            evaluate(opportunity_engine, opportunity_id=item_id, radar_id=radar_id, provider=first),
            evaluate(
                opportunity_engine, opportunity_id=item_id, radar_id=radar_id, provider=second
            ),
        )
        assert sorted(outcomes) == ["scored", "skipped"]
        assert await count_rows(opportunity_engine, OpportunityScore) == 1
        assert await count_rows(opportunity_engine, OpportunityActionPayload) == 1
        assert await count_rows(opportunity_engine, Notification) == 1


class TestNotificationXor:
    @pytest.mark.asyncio
    async def test_exactly_one_fact_target_is_enforced(
        self, opportunity_engine: AsyncEngine
    ) -> None:
        user_id, radar_id, source_id = await create_pipeline_context(opportunity_engine)
        await run_acquisition(opportunity_engine, source_id=source_id)
        item_id = await only_item_id(opportunity_engine)
        await evaluate(
            opportunity_engine,
            opportunity_id=item_id,
            radar_id=radar_id,
            provider=ScriptedOpportunityProvider([GOOD_DIMS]),
        )
        factory = async_sessionmaker(opportunity_engine, expire_on_commit=False)
        async with factory() as session:
            score = await session.scalar(select(OpportunityScore))
            assert score is not None
            session.add(
                Notification(
                    id=uuid4(),
                    user_id=user_id,
                    analysis_id=None,
                    opportunity_score_id=None,
                    title="x",
                    content="x",
                    priority="normal",
                    reason="x",
                    status=NotificationStatus.UNREAD,
                )
            )
            with pytest.raises(IntegrityError):
                await session.commit()
            await session.rollback()
        # A second opportunity notification for the same score is a no-op.
        async with factory() as session:
            score_id = await session.scalar(select(OpportunityScore.id))
            assert score_id is not None
            result = await session.execute(
                text(
                    "INSERT INTO notifications (id, user_id, opportunity_score_id, title, "
                    "content, priority, reason, status) VALUES "
                    "(:id, :user, :score, 'dup', 'dup', 'normal', 'dup', 'unread') "
                    "ON CONFLICT (user_id, opportunity_score_id) "
                    "WHERE opportunity_score_id IS NOT NULL DO NOTHING"
                ).bindparams(id=uuid4(), user=user_id, score=score_id)
            )
            assert getattr(result, "rowcount", 0) == 0
            await session.rollback()
        assert await count_rows(opportunity_engine, Notification) == 1


class TestRestSurface:
    async def build_app(self, engine: AsyncEngine) -> tuple[Any, async_sessionmaker[Any]]:
        factory = async_sessionmaker(engine, expire_on_commit=False)

        async def healthy() -> None:
            return None

        settings = Settings()
        app = create_app(settings, readiness_service=ReadinessService(healthy, healthy))
        app.state.session_factory = factory
        return app, factory

    @pytest.mark.asyncio
    async def test_list_detail_payload_ownership_and_filters(
        self, opportunity_engine: AsyncEngine
    ) -> None:
        user_id, radar_id, source_id = await create_pipeline_context(opportunity_engine)
        await run_acquisition(opportunity_engine, source_id=source_id)
        item_id = await only_item_id(opportunity_engine)
        await evaluate(
            opportunity_engine,
            opportunity_id=item_id,
            radar_id=radar_id,
            provider=ScriptedOpportunityProvider([GOOD_DIMS]),
        )
        app, _factory = await self.build_app(opportunity_engine)
        settings = Settings()
        stranger_id = await create_user(opportunity_engine, "stranger")
        headers = {"Authorization": f"Bearer {create_access_token(user_id, settings)}"}
        stranger = {"Authorization": f"Bearer {create_access_token(stranger_id, settings)}"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            listing = await client.get(
                "/api/v1/opportunities?status=active&recommendation=act_now&min_score=80"
                "&currency=USD",
                headers=headers,
            )
            assert listing.status_code == 200
            body = listing.json()
            assert body["total"] == 1
            entry = body["items"][0]
            assert entry["title"] == "Landing page refresh"
            assert entry["score"]["recommendation"] == "act_now"
            assert Decimal(str(entry["score"]["overall_score"])) == EXPECTED_OVERALL
            assert "raw_text" not in entry and "</html>" not in listing.text
            filtered_out = await client.get(
                "/api/v1/opportunities?recommendation=dismiss", headers=headers
            )
            assert filtered_out.json()["total"] == 0
            deadline_miss = await client.get(
                "/api/v1/opportunities?deadline=2026-10-05T13:00:00Z", headers=headers
            )
            assert deadline_miss.json()["total"] == 0
            detail = await client.get(f"/api/v1/opportunities/{item_id}", headers=headers)
            assert detail.status_code == 200
            assert detail.json()["id"] == str(item_id)
            hidden = await client.get(f"/api/v1/opportunities/{item_id}", headers=stranger)
            assert hidden.status_code == 404
            payload = await client.get(
                f"/api/v1/opportunities/{item_id}/action-payload", headers=headers
            )
            assert payload.status_code == 200
            document = payload.json()
            assert document["payload"]["requires_human_approval"] is True
            assert document["payload_hash"]
            assert "cookie" not in payload.text.casefold()
            hidden_payload = await client.get(
                f"/api/v1/opportunities/{item_id}/action-payload", headers=stranger
            )
            assert hidden_payload.status_code == 404
            missing = await client.get(f"/api/v1/opportunities/{uuid4()}", headers=headers)
            assert missing.status_code == 404
            assert missing.json()["error"]["code"] == "opportunity_not_found"

    @pytest.mark.asyncio
    async def test_dismissed_opportunity_has_no_payload(
        self, opportunity_engine: AsyncEngine
    ) -> None:
        user_id, radar_id, source_id = await create_pipeline_context(opportunity_engine)
        html = JOB_HTML.replace(SALARY_JSONLD, b"")
        await run_acquisition(opportunity_engine, source_id=source_id, body=html)
        item_id = await only_item_id(opportunity_engine)
        await evaluate(
            opportunity_engine,
            opportunity_id=item_id,
            radar_id=radar_id,
            provider=ScriptedOpportunityProvider([GOOD_DIMS]),
        )
        app, _factory = await self.build_app(opportunity_engine)
        headers = {"Authorization": f"Bearer {create_access_token(user_id, Settings())}"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                f"/api/v1/opportunities/{item_id}/action-payload", headers=headers
            )
            assert response.status_code == 404
            assert response.json()["error"]["code"] == "action_payload_unavailable"
            listing = await client.get("/api/v1/opportunities", headers=headers)
            assert listing.json()["items"][0]["score"]["hard_filter_passed"] is False

    @pytest.mark.asyncio
    async def test_notifications_expose_opportunity_kind(
        self, opportunity_engine: AsyncEngine
    ) -> None:
        user_id, radar_id, source_id = await create_pipeline_context(opportunity_engine)
        await run_acquisition(opportunity_engine, source_id=source_id)
        item_id = await only_item_id(opportunity_engine)
        await evaluate(
            opportunity_engine,
            opportunity_id=item_id,
            radar_id=radar_id,
            provider=ScriptedOpportunityProvider([GOOD_DIMS]),
        )
        app, _factory = await self.build_app(opportunity_engine)
        headers = {"Authorization": f"Bearer {create_access_token(user_id, Settings())}"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            listing = await client.get("/api/v1/notifications", headers=headers)
            assert listing.status_code == 200
            item = listing.json()["items"][0]
            assert item["kind"] == "opportunity"
            assert item["opportunity_id"] == str(item_id)
            assert item["analysis_id"] is None
            read = await client.post(f"/api/v1/notifications/{item['id']}/read", headers=headers)
            assert read.status_code == 200
            assert read.json()["kind"] == "opportunity"
            openapi = (await client.get("/openapi.json")).json()
            assert "/api/v1/opportunities" in openapi["paths"]
            assert "opportunity" in openapi["components"]["schemas"]["RadarType"]["enum"]


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
    async def test_cycle_with_irreversible_data_guards(
        self, opportunity_engine: AsyncEngine
    ) -> None:
        downgraded = self.run_alembic("downgrade", "20261006_0007")
        assert downgraded.returncode == 0, downgraded.stderr
        upgraded = self.run_alembic("upgrade", "head")
        assert upgraded.returncode == 0, upgraded.stderr

        # The enum rebuild is refused while any radar still uses 'opportunity'.
        _user_id, _radar_id, source_id = await create_pipeline_context(opportunity_engine)
        enum_guarded = self.run_alembic("downgrade", "20261005_0005")
        assert enum_guarded.returncode != 0
        assert "refusing to rebuild radar_type" in enum_guarded.stderr
        # Revisions above the refused guard may already have been downgraded and
        # committed; restore head so the schema matches the running code again.
        assert self.run_alembic("upgrade", "head").returncode == 0

        # The evaluation-version guard (0009) refuses once a re-evaluation exists.
        await run_acquisition(opportunity_engine, source_id=source_id)
        factory = async_sessionmaker(opportunity_engine, expire_on_commit=False)
        async with factory() as session:
            item_row = await session.scalar(select(OpportunityItem))
            radar_row = await session.scalar(select(Radar))
            assert item_row is not None and radar_row is not None
            session.add(
                OpportunityScore(
                    id=uuid4(),
                    opportunity_id=item_row.id,
                    radar_id=radar_row.id,
                    score_version="opportunity-score-v1",
                    evaluation_version=1,
                    hard_filter_passed=False,
                    disqualifiers=["insufficient_data"],
                    recommendation="dismiss",
                    reason="guard fixture",
                    scored_at=NOW,
                )
            )
            await session.commit()
            await session.execute(text("UPDATE opportunity_scores SET evaluation_version = 2"))
            await session.commit()
        version_guarded = self.run_alembic("downgrade", "20261006_0008")
        assert version_guarded.returncode != 0
        assert "refusing to drop opportunity_scores.evaluation_version" in version_guarded.stderr

        # With opportunity facts present, dropping the opportunity layer is refused.
        async with factory() as session:
            await session.execute(text("DELETE FROM opportunity_scores"))
            radar_row = await session.scalar(select(Radar))
            assert radar_row is not None
            await session.execute(text("DELETE FROM radars"))
            await session.commit()
        data_guarded = self.run_alembic("downgrade", "20261005_0005")
        assert data_guarded.returncode != 0
        assert "refusing to drop opportunity table" in data_guarded.stderr

        # The snapshot-identity guard (0008) separately refuses while any RawItem is
        # snapshot-linked: the legacy constraint cannot express the new rows.
        assert self.run_alembic("upgrade", "head").returncode == 0
        async with factory() as session:
            snapshot = await session.scalar(select(AcquisitionSnapshot))
            run_row = await session.scalar(select(CollectionRun))
            assert snapshot is not None and run_row is not None
            session.add(
                RawItem(
                    source_id=run_row.source_id,
                    collection_run_id=run_row.id,
                    snapshot_id=snapshot.id,
                    external_id="guard-item",
                    canonical_url="https://example.com/guard-item",
                    fetched_at=NOW,
                    content_type="text/html",
                    raw_text="Snapshot guard body",
                    content_hash="0" * 64,
                    item_metadata={},
                    status=RawItemStatus.FETCHED,
                )
            )
            await session.commit()
        snapshot_guarded = self.run_alembic("downgrade", "20261006_0007")
        assert snapshot_guarded.returncode != 0
        assert "refusing to drop raw_items.snapshot_id" in snapshot_guarded.stderr

        # Emptying every ACQ-1G fact lets the downgrade round-trip safely.
        async with opportunity_engine.begin() as connection:
            await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
        clean = self.run_alembic("downgrade", "20261005_0005")
        assert clean.returncode == 0, clean.stderr
        current = self.run_alembic("current")
        assert "20261005_0005" in current.stdout
        restored = self.run_alembic("upgrade", "head")
        assert restored.returncode == 0, restored.stderr
        after = self.run_alembic("current")
        assert "20261006_0009" in after.stdout


def test_opportunity_task_and_beat_schedule(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.tasks import opportunity

    async def return_two() -> int:
        return 2

    monkeypatch.setattr(opportunity, "_dispatch", return_two)
    result = opportunity.dispatch_opportunity_evaluations.apply()
    assert result.successful() and result.get() == 2
    from app.tasks.celery_app import celery_app

    schedule = celery_app.conf.beat_schedule["dispatch-opportunity-evaluations"]
    assert schedule["task"] == "flowtracer.tasks.opportunity.dispatch_opportunity_evaluations"
    assert schedule["schedule"] == 60.0


class TestFactsExtraction:
    def test_jsonld_jobposting_fields_are_extracted_deterministically(self) -> None:
        from app.services.opportunity_facts import extract_opportunity_facts

        extracted = extract_opportunity_facts(CANDIDATE, JOB_HTML)
        assert extracted is not None
        facts = extracted.facts
        assert facts.title == "Landing page refresh"
        assert facts.budget_min == Decimal("50.00")
        assert facts.budget_max == Decimal("60.00")
        assert facts.currency == "USD"
        assert facts.skills == ("React", "CSS")
        assert facts.delivery_type == "one_off"
        assert facts.estimated_effort_hours == Decimal("4.00")
        assert facts.required_meetings == 1
        assert facts.deadline == datetime(2026, 10, 6, 12, 0, tzinfo=UTC)
        assert extracted.client_metadata == {"required_meetings": 1}

    def test_missing_jsonld_falls_back_to_candidate_without_guessing(self) -> None:
        from app.services.opportunity_facts import extract_opportunity_facts

        extracted = extract_opportunity_facts(CANDIDATE, b"<html><body>plain</body></html>")
        assert extracted is not None
        assert extracted.facts.budget_min is None
        assert extracted.facts.currency is None
        assert extracted.facts.deadline is None
        assert extracted.facts.delivery_type is None
        assert extracted.facts.description.startswith("Landing page refresh")
        assert extracted.client_metadata == {}

    def test_invalid_jsonld_and_missing_title_are_ignored(self) -> None:
        from app.services.opportunity_facts import extract_opportunity_facts

        broken = JOB_HTML.replace(b'"@type":"JobPosting"', b'"@type":"Broken"')
        extracted = extract_opportunity_facts(CANDIDATE, broken)
        assert extracted is not None
        assert extracted.facts.currency is None
        untitled = RawCandidate(
            external_id="gig-2",
            canonical_url="https://jobs.example.com/gig-2",
            raw_text="Body only",
            content_type="text/html",
            title=None,
        )
        assert extract_opportunity_facts(untitled, None) is None

    def test_scalar_salary_and_list_skills_and_client_metadata(self) -> None:
        from app.services.opportunity_facts import extract_opportunity_facts

        html = (
            b'<html><script type="application/ld+json">'
            b'{"@type":["JobPosting"],"title":"Fix widget","description":"Short task",'
            b'"baseSalary":75.5,"skills":["a","a","b"],'
            b'"hiringOrganization":{"name":"Acme"},'
            b'"clientRating":4.5,"clientReviewCount":12,"maintenanceRequired":true}'
            b"</script></html>"
        )
        extracted = extract_opportunity_facts(CANDIDATE, html)
        assert extracted is not None
        assert extracted.facts.budget_min is None
        assert extracted.facts.budget_max == Decimal("75.50")
        assert extracted.facts.currency is None
        assert extracted.facts.skills == ("a", "b")
        assert extracted.facts.maintenance_required is True
        assert extracted.client_metadata["client_name"] == "Acme"
        assert extracted.client_metadata["client_rating"] == 4.5
        assert extracted.client_metadata["client_review_count"] == 12
        assert extracted.client_metadata["maintenance_required"] is True


class TestProviderSubstitution:
    def test_fake_provider_is_deterministic_and_buildable(self) -> None:
        from app.core.composition import build_opportunity_dependency

        provider = build_opportunity_dependency(Settings())
        assert provider.name == "fake"
        request = OpportunityEvaluationRequest(
            title="Gig",
            description="Short",
            platform=None,
            budget_min=None,
            budget_max=None,
            currency=None,
            skills=(),
            deadline=None,
            published_at=None,
            estimated_effort_hours=None,
            delivery_type=None,
            radar_name="R",
            radar_goal="G",
            radar_keywords=(),
        )

        async def run() -> tuple[Any, Any]:
            return await provider.evaluate(request), await provider.evaluate(request)

        first, second = asyncio.run(run())
        assert first == second

    @pytest.mark.asyncio
    async def test_openai_compatible_rejects_invalid_output_and_excludes_secrets(
        self,
    ) -> None:
        import httpx
        from pydantic import SecretStr

        from app.providers.opportunity import OpenAICompatibleOpportunityProvider

        class OneChunkStream(httpx.AsyncByteStream):
            def __init__(self, content: bytes) -> None:
                self.content = content

            async def __aiter__(self) -> Any:
                yield self.content

            async def aclose(self) -> None:
                return None

        settings = Settings().model_copy(
            update={
                "ai_provider": "openai_compatible",
                "ai_base_url": "https://analysis.example.test/v1",
                "ai_api_key": SecretStr("test-only"),
            }
        )
        seen_bodies: list[str] = []

        def invalid_usage(request: httpx.Request) -> httpx.Response:
            seen_bodies.append(request.content.decode())
            content = json.dumps(
                {"choices": [{"message": {"content": "{}"}}], "usage": {"prompt_tokens": -1}}
            ).encode()
            return httpx.Response(200, stream=OneChunkStream(content))

        valid_dims = dict(GOOD_DIMS)

        def valid_response(request: httpx.Request) -> httpx.Response:
            seen_bodies.append(request.content.decode())
            content = json.dumps(
                {
                    "choices": [{"message": {"content": json.dumps(valid_dims)}}],
                    "usage": {"prompt_tokens": 5, "completion_tokens": 6, "total_tokens": 11},
                }
            ).encode()
            return httpx.Response(200, stream=OneChunkStream(content))

        request = OpportunityEvaluationRequest(
            title="Gig",
            description="Short",
            platform="jobs.example.com",
            budget_min=Decimal("50.00"),
            budget_max=Decimal("60.00"),
            currency="USD",
            skills=("React",),
            deadline=NOW + timedelta(days=1),
            published_at=NOW,
            estimated_effort_hours=Decimal("4.00"),
            delivery_type="one_off",
            radar_name="R",
            radar_goal="G",
            radar_keywords=("react",),
        )
        async with httpx.AsyncClient(transport=httpx.MockTransport(invalid_usage)) as client:
            provider = OpenAICompatibleOpportunityProvider(settings, client)
            with pytest.raises(ProviderError, match="invalid output"):
                await provider.evaluate(request)
        async with httpx.AsyncClient(transport=httpx.MockTransport(valid_response)) as client:
            provider = OpenAICompatibleOpportunityProvider(settings, client)
            response = await provider.evaluate(request, repair_error="schema mismatch")
            assert json.loads(response.content)["fit"] == 90
            assert response.usage.total_tokens == 11
        for body in seen_bodies:
            assert "test-only" not in body
            assert "cookie" not in body.casefold()
            assert "api_key" not in body.casefold()
            assert "authorization" not in body.casefold()
