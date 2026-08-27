from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings
from app.main import create_app
from app.models.entities import (
    AIUsageRecord,
    Analysis,
    AnalysisStatus,
    CollectionRun,
    CollectionRunStatus,
    CollectionTriggerType,
    Document,
    DocumentStatus,
    Radar,
    RadarSource,
    RadarType,
    RawItem,
    RawItemStatus,
    Recommendation,
    ResourceStatus,
    Source,
    SourceType,
    User,
)
from app.providers.analysis import AnalysisRequest, ProviderError, ProviderResponse, ProviderUsage
from app.services.cleaning import (
    MAX_CLEANED_CONTENT_BYTES,
    clean_raw_item,
    clean_text,
    count_words,
    dispatch_fetched_raw_items,
)
from app.services.intelligence import (
    calculate_cost,
    calculate_score,
    dispatch_pending_analyses,
    qualifies_for_notification,
    recommendation_for,
    recover_stale_analyses,
    retry_analysis,
    run_analysis,
    validate_output,
)
from app.services.readiness import ReadinessService

TABLES = (
    "notifications, ai_usage_records, document_chunks, bookmarks, analyses, documents, "
    "raw_items, radar_sources, collection_runs, sources, radars, refresh_tokens, users"
)


async def healthy_probe() -> None:
    return None


@pytest.fixture
async def intelligence_engine() -> Any:
    database_url = os.environ["TEST_DATABASE_URL"]
    assert "_test" in database_url.rsplit("/", maxsplit=1)[-1]
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    yield engine
    await engine.dispose()


async def create_raw(
    engine: AsyncEngine,
    *,
    raw_text: str,
    email: str | None = None,
    radar_status: ResourceStatus = ResourceStatus.ACTIVE,
    bind: bool = True,
) -> tuple[UUID, UUID, UUID]:
    async with AsyncSession(engine) as session:
        user = User(
            email=email or f"owner-{uuid4()}@example.com",
            password_hash="hash",  # noqa: S106 - inert fixture value, never used for login
            display_name="Owner",
            profile={},
        )
        session.add(user)
        await session.flush()
        source = Source(
            user_id=user.id,
            name="Source",
            source_type=SourceType.RSS,
            url=f"https://example.com/{uuid4()}",
            normalized_url=f"https://example.com/{uuid4()}",
            poll_interval_minutes=15,
            status=ResourceStatus.ACTIVE,
            config={},
        )
        radar = Radar(
            user_id=user.id,
            name=f"Radar {uuid4()}",
            goal="Track this",
            radar_type=RadarType.TECHNOLOGY,
            categories=["technology"],
            keywords=["python"],
            status=radar_status,
            notification_threshold=75,
        )
        session.add_all([source, radar])
        await session.flush()
        if bind:
            session.add(RadarSource(radar_id=radar.id, source_id=source.id))
        run = CollectionRun(
            source_id=source.id,
            trigger_type=CollectionTriggerType.MANUAL,
            status=CollectionRunStatus.SUCCEEDED,
        )
        session.add(run)
        await session.flush()
        raw = RawItem(
            source_id=source.id,
            collection_run_id=run.id,
            canonical_url=source.normalized_url,
            title="  A\u0301 title  ",
            fetched_at=datetime.now(UTC),
            raw_text=raw_text,
            content_hash="0" * 64,
            item_metadata={"author": "  Author\u0085 Name  ", "private": "do-not-forward"},
            status=RawItemStatus.FETCHED,
        )
        session.add(raw)
        await session.flush()
        result = (raw.id, radar.id, user.id)
        await session.commit()
        return result


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Cafe\u0301\r\n\rline\u0000\t  value  ", "Café\n\nline value"),
        ("one\n\n\n\n two", "one\n\ntwo"),
        ("\u0085safe\u007f", "safe"),
    ],
)
def test_clean_text_table(raw: str, expected: str) -> None:
    assert clean_text(raw) == expected


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("hello world 123", 3),
        ("中文测试", 4),
        ("Python 与 AI 2026!", 4),
        ("𠀀𠀁 data", 3),
        ("...", 0),
    ],
)
def test_word_count_table(content: str, expected: int) -> None:
    assert count_words(content) == expected


@pytest.mark.asyncio
async def test_cleaning_boundary_duplicate_concurrency_and_radar_expansion(
    intelligence_engine: AsyncEngine,
) -> None:
    factory = async_sessionmaker(intelligence_engine, expire_on_commit=False)
    exact_id, _, _ = await create_raw(intelligence_engine, raw_text="a" * MAX_CLEANED_CONTENT_BYTES)
    exact = await clean_raw_item(factory, exact_id)
    assert exact.document_id is not None and len(exact.analysis_ids) == 1

    too_large_id, _, _ = await create_raw(
        intelligence_engine, raw_text="b" * (MAX_CLEANED_CONTENT_BYTES + 1)
    )
    failed = await clean_raw_item(factory, too_large_id)
    assert failed.document_id is None

    empty_id, _, _ = await create_raw(intelligence_engine, raw_text="\u0085 \n\t")
    await clean_raw_item(factory, empty_id)

    first_id, _, _ = await create_raw(intelligence_engine, raw_text="globally identical")
    second_id, _, _ = await create_raw(intelligence_engine, raw_text="globally identical")
    results = await asyncio.gather(
        clean_raw_item(factory, first_id), clean_raw_item(factory, second_id)
    )
    assert results[0].document_id == results[1].document_id
    async with AsyncSession(intelligence_engine) as session:
        assert await session.scalar(select(func.count()).select_from(Document)) == 2
        statuses = set(
            (
                await session.scalars(
                    select(RawItem.status).where(RawItem.id.in_([first_id, second_id]))
                )
            ).all()
        )
        assert statuses == {RawItemStatus.CLEANED, RawItemStatus.DUPLICATE}
        too_large = await session.get(RawItem, too_large_id)
        empty = await session.get(RawItem, empty_id)
        assert too_large is not None and too_large.error_code == "cleaned_content_too_large"
        assert empty is not None and empty.error_code == "empty_content"
        assert "b" * 100 not in (too_large.error_message or "")

    paused_id, _, _ = await create_raw(
        intelligence_engine,
        raw_text="No active target",
        radar_status=ResourceStatus.PAUSED,
    )
    paused_result = await clean_raw_item(factory, paused_id)
    assert paused_result.analysis_ids == ()
    async with AsyncSession(intelligence_engine) as session:
        document = await session.get(Document, paused_result.document_id)
        assert document is not None and document.status == DocumentStatus.EMBEDDING
        assert document.title == "Á title"
        assert document.author == "Author Name"


class SequenceProvider:
    name = "fake"
    model = "sequence-model"

    def __init__(self, outcomes: list[ProviderResponse | ProviderError]) -> None:
        self.outcomes = outcomes
        self.requests: list[tuple[AnalysisRequest, str | None]] = []

    async def analyze(
        self, request: AnalysisRequest, *, repair_error: str | None = None
    ) -> ProviderResponse:
        self.requests.append((request, repair_error))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, ProviderError):
            raise outcome
        return outcome


def valid_response(**changes: object) -> ProviderResponse:
    payload: dict[str, object] = {
        "summary": "Summary",
        "category": "technology",
        "relevance": 90,
        "importance": 80,
        "novelty": 70,
        "impact": 60,
        "reason": "Useful",
    }
    payload.update(changes)
    return ProviderResponse(json.dumps(payload), ProviderUsage(100, 20, 120))


@pytest.mark.asyncio
async def test_analysis_pipeline_usage_idempotency_repair_and_document_terminal(
    intelligence_engine: AsyncEngine,
) -> None:
    raw_id, _, _ = await create_raw(intelligence_engine, raw_text="Analyze me")
    factory = async_sessionmaker(intelligence_engine, expire_on_commit=False)
    cleaned = await clean_raw_item(factory, raw_id)
    analysis_id = cleaned.analysis_ids[0]
    provider = SequenceProvider(
        [ProviderResponse('{"summary":"bad"}', ProviderUsage(3, 2, 5)), valid_response()]
    )
    settings = Settings()
    assert await run_analysis(factory, analysis_id, provider, settings)
    assert provider.requests[0][1] is None and provider.requests[1][1] is not None
    assert not await run_analysis(factory, analysis_id, provider, settings)
    async with AsyncSession(intelligence_engine) as session:
        analysis = await session.get(Analysis, analysis_id)
        document = await session.get(Document, cleaned.document_id)
        usage = list(
            (await session.scalars(select(AIUsageRecord).order_by(AIUsageRecord.created_at))).all()
        )
        assert analysis is not None and analysis.status == AnalysisStatus.COMPLETED
        assert analysis.radar_score == Decimal("79.00")
        assert analysis.recommendation == Recommendation.READ
        assert document is not None and document.status == DocumentStatus.EMBEDDING
        assert len(usage) == 2
        assert [item.succeeded for item in usage] == [False, True]
        assert usage[0].error_code == "ai_invalid_output"
        assert all(item.estimated_cost == 0 for item in usage)


@pytest.mark.asyncio
async def test_analysis_retry_limits_failure_dispatch_and_stale_recovery(
    intelligence_engine: AsyncEngine,
) -> None:
    raw_id, _, _ = await create_raw(intelligence_engine, raw_text="Retry me")
    factory = async_sessionmaker(intelligence_engine, expire_on_commit=False)
    cleaned = await clean_raw_item(factory, raw_id)
    analysis_id = cleaned.analysis_ids[0]
    unavailable = ProviderError("ai_provider_unavailable", "Provider unavailable", retryable=True)
    provider = SequenceProvider([unavailable, unavailable, unavailable])
    sleeps: list[float] = []

    async def no_sleep(delay: float) -> None:
        sleeps.append(delay)

    assert not await run_analysis(factory, analysis_id, provider, Settings(), sleep=no_sleep)
    assert sleeps == [2.0, 4.0]
    assert len(provider.requests) == 3
    async with AsyncSession(intelligence_engine) as session:
        analysis = await session.get(Analysis, analysis_id)
        assert analysis is not None and analysis.status == AnalysisStatus.FAILED
        analysis.status = AnalysisStatus.RUNNING
        analysis.updated_at = datetime.now(UTC) - timedelta(minutes=11)
        await session.commit()
    assert await recover_stale_analyses(factory) == 1
    sent: list[str] = []
    assert await dispatch_pending_analyses(factory, lambda value, _cid: sent.append(value)) == 1
    assert sent == [str(analysis_id)]

    raw_pending, _, _ = await create_raw(intelligence_engine, raw_text="Pending dispatch")
    sent_raw: list[str] = []
    assert (
        await dispatch_fetched_raw_items(factory, lambda value, _cid: sent_raw.append(value)) == 1
    )
    assert sent_raw == [str(raw_pending)]


@pytest.mark.asyncio
async def test_concurrent_analysis_claim_calls_provider_once_and_all_failed_document(
    intelligence_engine: AsyncEngine,
) -> None:
    raw_id, _, _ = await create_raw(intelligence_engine, raw_text="Claim once")
    factory = async_sessionmaker(intelligence_engine, expire_on_commit=False)
    cleaned = await clean_raw_item(factory, raw_id)
    analysis_id = cleaned.analysis_ids[0]
    provider = SequenceProvider([valid_response()])
    outcomes = await asyncio.gather(
        run_analysis(factory, analysis_id, provider, Settings()),
        run_analysis(factory, analysis_id, provider, Settings()),
    )
    assert sorted(outcomes) == [False, True]
    assert len(provider.requests) == 1

    failed_raw_id, _, _ = await create_raw(intelligence_engine, raw_text="Fail once")
    failed_clean = await clean_raw_item(factory, failed_raw_id)
    failed_provider = SequenceProvider(
        [ProviderError("ai_auth_failed", "AI authentication failed", retryable=False)]
    )
    assert not await run_analysis(
        factory, failed_clean.analysis_ids[0], failed_provider, Settings()
    )
    async with AsyncSession(intelligence_engine) as session:
        document = await session.get(Document, failed_clean.document_id)
        usage = await session.scalar(
            select(AIUsageRecord).where(AIUsageRecord.analysis_id == failed_clean.analysis_ids[0])
        )
        assert document is not None and document.status == DocumentStatus.FAILED
        assert usage is not None and not usage.succeeded and usage.error_code == "ai_auth_failed"
    assert await recover_stale_analyses(factory) == 0

    failures: list[str] = []
    assert (
        await dispatch_pending_analyses(
            factory,
            lambda value, _cid: (_ for _ in ()).throw(ConnectionError(value)),
        )
        == 0
    )
    assert failures == []


@pytest.mark.asyncio
async def test_retry_restores_document_for_failed_pending_running_and_concurrency(
    intelligence_engine: AsyncEngine,
) -> None:
    raw_id, _, user_id = await create_raw(intelligence_engine, raw_text="Retry state machine")
    factory = async_sessionmaker(intelligence_engine, expire_on_commit=False)
    cleaned = await clean_raw_item(factory, raw_id)
    analysis_id = cleaned.analysis_ids[0]

    async def force_state(status: AnalysisStatus) -> None:
        async with AsyncSession(intelligence_engine) as session:
            analysis = await session.get(Analysis, analysis_id)
            document = await session.get(Document, cleaned.document_id)
            assert analysis is not None and document is not None
            analysis.status = status
            analysis.error_code = "ai_timeout"
            analysis.error_message = "AI request timed out"
            document.status = DocumentStatus.FAILED
            document.error_code = "internal_analysis_error"
            document.error_message = "All analyses failed"
            await session.commit()

    async def retry_once() -> AnalysisStatus:
        async with AsyncSession(intelligence_engine) as session:
            result = await retry_analysis(session, user_id=user_id, analysis_id=analysis_id)
            return result.status

    await force_state(AnalysisStatus.FAILED)
    assert await asyncio.gather(retry_once(), retry_once()) == [
        AnalysisStatus.PENDING,
        AnalysisStatus.PENDING,
    ]
    async with AsyncSession(intelligence_engine) as session:
        analysis = await session.get(Analysis, analysis_id)
        document = await session.get(Document, cleaned.document_id)
        assert analysis is not None and analysis.status == AnalysisStatus.PENDING
        assert analysis.error_code is None and analysis.error_message is None
        assert document is not None and document.status == DocumentStatus.ANALYZING
        assert document.error_code is None and document.error_message is None

    for replay_status in (AnalysisStatus.PENDING, AnalysisStatus.RUNNING):
        await force_state(replay_status)
        assert await retry_once() == replay_status
        async with AsyncSession(intelligence_engine) as session:
            document = await session.get(Document, cleaned.document_id)
            assert document is not None and document.status == DocumentStatus.ANALYZING
            assert document.error_code is None and document.error_message is None


@pytest.mark.parametrize(
    "content",
    [
        "```json\n{}\n```",
        '{"summary":"x","category":"technology","relevance":true,"importance":1,"novelty":1,"impact":1,"reason":"x"}',
        '{"summary":"x","category":"technology","relevance":1.5,"importance":1,"novelty":1,"impact":1,"reason":"x"}',
        '{"summary":"x","category":"technology","relevance":NaN,"importance":1,"novelty":1,"impact":1,"reason":"x"}',
        '{"summary":"x","category":"unknown","relevance":1,"importance":1,"novelty":1,"impact":1,"reason":"x"}',
        '{"summary":"x","category":"technology","relevance":1,"importance":1,"novelty":1,"impact":1,"reason":"x","extra":1}',
        '{"summary":"x\\ud800","category":"technology","relevance":1,"importance":1,"novelty":1,"impact":1,"reason":"x"}',
        '{"summary":"x\\u0001","category":"technology","relevance":1,"importance":1,"novelty":1,"impact":1,"reason":"x"}',
        '{"summary":"\\ntrimmed","category":"technology","relevance":1,"importance":1,"novelty":1,"impact":1,"reason":"x"}',
    ],
)
def test_strict_output_rejects_non_contract_json(content: str) -> None:
    with pytest.raises(ProviderError) as raised:
        validate_output(content, ("technology",))
    assert raised.value.code == "ai_invalid_output"


@pytest.mark.parametrize(
    ("score", "recommendation"),
    [
        (Decimal("0"), Recommendation.ARCHIVE),
        (Decimal("49.99"), Recommendation.ARCHIVE),
        (Decimal("50"), Recommendation.MONITOR),
        (Decimal("69.99"), Recommendation.MONITOR),
        (Decimal("70"), Recommendation.READ),
        (Decimal("84.99"), Recommendation.READ),
        (Decimal("85"), Recommendation.MUST_READ),
        (Decimal("100"), Recommendation.MUST_READ),
    ],
)
def test_score_recommendation_notification_and_cost_boundaries(
    score: Decimal, recommendation: Recommendation, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert recommendation_for(score) == recommendation
    assert qualifies_for_notification(score, 50) is (score >= 50)
    assert calculate_score(100, 0, 0, 0) == Decimal("40.00")
    monkeypatch.setenv("AI_INPUT_COST_PER_MILLION", "1.234567")
    monkeypatch.setenv("AI_OUTPUT_COST_PER_MILLION", "2.345678")
    assert calculate_cost(10, 20, Settings()) == Decimal("0.000059")


@pytest.fixture
async def intelligence_client(
    intelligence_engine: AsyncEngine,
) -> Any:
    app = create_app(Settings(), readiness_service=ReadinessService(healthy_probe, healthy_probe))
    app.state.session_factory = async_sessionmaker(intelligence_engine, expire_on_commit=False)
    dispatched: list[str] = []
    app.state.analysis_dispatcher = lambda value, _cid: dispatched.append(value)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, dispatched


async def register(client: AsyncClient, email: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "intelligence-password-安全", "display_name": "Owner"},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['tokens']['access_token']}"}


@pytest.mark.asyncio
async def test_intelligence_api_ownership_filters_retry_and_openapi(
    intelligence_client: tuple[AsyncClient, list[str]], intelligence_engine: AsyncEngine
) -> None:
    client, dispatched = intelligence_client
    owner = await register(client, "intel-owner@example.com")
    stranger = await register(client, "intel-stranger@example.com")
    async with AsyncSession(intelligence_engine) as session:
        owner_id = await session.scalar(
            select(User.id).where(User.email == "intel-owner@example.com")
        )
    assert owner_id is not None
    raw_id, _, _ = await create_raw(
        intelligence_engine, raw_text="API intelligence content", email="graph-owner@example.com"
    )
    factory = async_sessionmaker(intelligence_engine, expire_on_commit=False)
    cleaned = await clean_raw_item(factory, raw_id)
    analysis_id = cleaned.analysis_ids[0]
    async with AsyncSession(intelligence_engine) as session:
        analysis = await session.get(Analysis, analysis_id)
        radar = await session.get(Radar, analysis.radar_id if analysis else uuid4())
        assert analysis is not None and radar is not None
        radar.user_id = owner_id
        analysis.status = AnalysisStatus.FAILED
        analysis.error_code = "ai_timeout"
        analysis.error_message = "AI request timed out"
        await session.commit()

    listing = await client.get(
        "/api/v1/intelligence?page=1&page_size=20&status=failed", headers=owner
    )
    assert listing.status_code == 200 and listing.json()["total"] == 1
    detail = await client.get(f"/api/v1/intelligence/{analysis_id}", headers=owner)
    assert detail.status_code == 200
    assert detail.json()["content"] == "API intelligence content"
    assert "raw_text" not in detail.text and "estimated_cost" not in detail.text
    hidden = await client.get(f"/api/v1/intelligence/{analysis_id}", headers=stranger)
    missing = await client.get(f"/api/v1/intelligence/{uuid4()}", headers=stranger)
    assert hidden.status_code == missing.status_code == 404
    assert hidden.json()["error"]["code"] == missing.json()["error"]["code"]

    retried = await client.post(f"/api/v1/analyses/{analysis_id}/retry", headers=owner)
    replay = await client.post(f"/api/v1/analyses/{analysis_id}/retry", headers=owner)
    assert retried.status_code == replay.status_code == 202
    assert retried.json()["status"] == "pending"
    assert dispatched == [str(analysis_id), str(analysis_id)]
    async with AsyncSession(intelligence_engine) as session:
        analysis = await session.get(Analysis, analysis_id)
        assert analysis is not None
        analysis.status = AnalysisStatus.COMPLETED
        await session.commit()
    conflict = await client.post(f"/api/v1/analyses/{analysis_id}/retry", headers=owner)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "analysis_not_retryable"

    async with AsyncSession(intelligence_engine) as session:
        analysis = await session.get(Analysis, analysis_id)
        assert analysis is not None
        analysis.status = AnalysisStatus.FAILED
        await session.commit()
    client._transport.app.state.analysis_dispatcher = (  # type: ignore[attr-defined]
        lambda _value, _cid: (_ for _ in ()).throw(ConnectionError("private broker"))
    )
    unavailable = await client.post(f"/api/v1/analyses/{analysis_id}/retry", headers=owner)
    assert unavailable.status_code == 503
    assert unavailable.json()["error"]["code"] == "analysis_queue_unavailable"
    assert "private" not in unavailable.text
    async with AsyncSession(intelligence_engine) as session:
        analysis = await session.get(Analysis, analysis_id)
        assert analysis is not None and analysis.status == AnalysisStatus.PENDING

    invalid = await client.get("/api/v1/intelligence?min_score=101", headers=owner)
    assert invalid.status_code == 422
    openapi = (await client.get("/openapi.json")).json()
    assert "/api/v1/intelligence" in openapi["paths"]
    assert "/api/v1/intelligence/{analysis_id}" in openapi["paths"]
    assert "/api/v1/analyses/{analysis_id}/retry" in openapi["paths"]
    properties = openapi["components"]["schemas"]["IntelligenceDetail"]["properties"]
    assert "content" in properties and "raw_text" not in properties
