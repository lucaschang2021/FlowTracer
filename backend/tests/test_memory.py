from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings
from app.core.errors import AppError
from app.main import create_app
from app.models.entities import (
    AIUsageRecord,
    Analysis,
    AnalysisStatus,
    CollectionRun,
    CollectionRunStatus,
    CollectionTriggerType,
    Document,
    DocumentChunk,
    DocumentStatus,
    Radar,
    RadarType,
    RawItem,
    RawItemStatus,
    Recommendation,
    ResourceStatus,
    Source,
    SourceType,
    User,
)
from app.providers.embedding import (
    EmbeddingError,
    EmbeddingResponse,
    EmbeddingUsage,
    FakeEmbeddingProvider,
)
from app.schemas.memory import MemorySearchRequest
from app.services.chunking import chunk_text
from app.services.memory import (
    create_bookmark,
    delete_bookmark,
    dispatch_embedding_documents,
    run_embedding,
    search_memory,
    update_bookmark,
)
from app.services.readiness import ReadinessService

TABLES = (
    "notifications, ai_usage_records, document_chunks, bookmarks, analyses, documents, "
    "raw_items, radar_sources, collection_runs, sources, radars, refresh_tokens, users"
)


async def healthy_probe() -> None:
    return None


def test_memory_search_dates_normalize_to_utc() -> None:
    request = MemorySearchRequest.model_validate(
        {
            "query": "query",
            "date_from": "2026-08-27T08:00:00+08:00",
            "date_to": "2026-08-27T01:00:00+00:00",
        }
    )
    assert request.date_from == datetime(2026, 8, 27, tzinfo=UTC)
    assert request.date_to == datetime(2026, 8, 27, 1, tzinfo=UTC)


@pytest.fixture
async def memory_engine() -> Any:
    database_url = os.environ["TEST_DATABASE_URL"]
    assert "_test" in database_url.rsplit("/", maxsplit=1)[-1]
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    yield engine
    await engine.dispose()


async def create_user(engine: AsyncEngine, email: str | None = None) -> UUID:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        user = User(
            email=email or f"memory-{uuid4()}@example.com",
            password_hash="synthetic",  # noqa: S106 - inert fixture hash
            display_name="Memory Owner",
            profile={},
        )
        session.add(user)
        await session.commit()
        return user.id


async def create_graph(
    engine: AsyncEngine,
    *,
    user_id: UUID | None = None,
    content: str = "memory content " * 80,
    document_status: DocumentStatus = DocumentStatus.EMBEDDING,
    published_at: datetime | None = None,
) -> tuple[UUID, UUID, UUID, UUID]:
    owner_id = user_id or await create_user(engine)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        source = Source(
            user_id=owner_id,
            name="Memory Source",
            source_type=SourceType.RSS,
            url=f"https://example.com/{uuid4()}",
            normalized_url=f"https://example.com/{uuid4()}",
            poll_interval_minutes=15,
            status=ResourceStatus.ACTIVE,
            config={},
        )
        radar = Radar(
            user_id=owner_id,
            name=f"Memory Radar {uuid4()}",
            goal="Remember useful information",
            radar_type=RadarType.TECHNOLOGY,
            categories=["technology"],
            keywords=["memory"],
            status=ResourceStatus.ACTIVE,
            notification_threshold=75,
        )
        session.add_all([source, radar])
        await session.flush()
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
            title="Memory title",
            published_at=published_at,
            fetched_at=datetime.now(UTC),
            raw_text=content,
            content_hash="a" * 64,
            item_metadata={},
            status=RawItemStatus.CLEANED,
        )
        session.add(raw)
        await session.flush()
        document = Document(
            raw_item_id=raw.id,
            canonical_url=raw.canonical_url,
            title="Memory title",
            content=content,
            word_count=2,
            content_hash=uuid4().hex * 2,
            status=document_status,
        )
        session.add(document)
        await session.flush()
        analysis = Analysis(
            document_id=document.id,
            radar_id=radar.id,
            pipeline_version="alpha-v1",
            prompt_version="intelligence-v1",
            summary="Memory summary",
            category="technology",
            relevance=80,
            importance=80,
            novelty=80,
            impact=80,
            radar_score=Decimal("80.00"),
            recommendation=Recommendation.READ,
            reason="Useful",
            provider="fake",
            model="flowtracer-fake-v1",
            status=AnalysisStatus.COMPLETED,
        )
        session.add(analysis)
        await session.commit()
        return document.id, analysis.id, radar.id, owner_id


@pytest.mark.parametrize(
    ("content", "size", "overlap", "expected"),
    [
        ("", 256, 0, []),
        ("短文本🙂", 256, 0, ["短文本🙂"]),
        ("a" * 256, 256, 0, ["a" * 256]),
        ("a" * 257, 256, 0, ["a" * 256, "a"]),
        ("abcdefgh", 4, 1, None),
    ],
)
def test_deterministic_chunking_boundaries(
    content: str, size: int, overlap: int, expected: list[str] | None
) -> None:
    if size < 256:
        with pytest.raises(ValueError):
            chunk_text(content, size=size, overlap=overlap)
        return
    first = chunk_text(content, size=size, overlap=overlap)
    assert first == chunk_text(content, size=size, overlap=overlap)
    assert [chunk.index for chunk in first] == list(range(len(first)))
    assert [chunk.content for chunk in first] == expected


def test_chunking_overlap_and_invalid_config() -> None:
    content = "0123456789" * 40
    chunks = chunk_text(content, size=256, overlap=16)
    assert chunks[0].content[-16:] == chunks[1].content[:16]
    with pytest.raises(ValueError):
        chunk_text(content, size=4001, overlap=0)
    with pytest.raises(ValueError):
        chunk_text(content, size=256, overlap=256)


@pytest.mark.asyncio
async def test_embedding_pipeline_concurrency_reuse_atomic_replace_and_dispatch(
    memory_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EMBEDDING_CHUNK_SIZE", "256")
    monkeypatch.setenv("EMBEDDING_CHUNK_OVERLAP", "16")
    settings = Settings()
    document_id, _, _, _ = await create_graph(memory_engine)
    factory = async_sessionmaker(memory_engine, expire_on_commit=False)
    provider = FakeEmbeddingProvider(settings.embedding_model)
    results = await asyncio.gather(
        run_embedding(factory, document_id, provider, settings),
        run_embedding(factory, document_id, provider, settings),
    )
    assert sorted(results) == [False, True]
    async with AsyncSession(memory_engine) as session:
        document = await session.get(Document, document_id)
        chunks = list(
            (
                await session.scalars(
                    select(DocumentChunk)
                    .where(DocumentChunk.document_id == document_id)
                    .order_by(DocumentChunk.chunk_index)
                )
            ).all()
        )
        usage_count = await session.scalar(
            select(func.count())
            .select_from(AIUsageRecord)
            .where(AIUsageRecord.task_type == "embedding")
        )
        assert document is not None and document.status == DocumentStatus.READY
        assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
        assert len(chunks) == len(chunk_text(document.content, size=256, overlap=16))
        assert usage_count == 1
        document.status = DocumentStatus.EMBEDDING
        await session.commit()
    assert await run_embedding(factory, document_id, provider, settings)
    async with AsyncSession(memory_engine) as session:
        usage_count = await session.scalar(
            select(func.count())
            .select_from(AIUsageRecord)
            .where(AIUsageRecord.task_type == "embedding")
        )
        assert usage_count == 1
        await session.execute(
            delete(DocumentChunk).where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.chunk_index == 0,
            )
        )
        document = await session.get(Document, document_id)
        assert document is not None
        document.status = DocumentStatus.EMBEDDING
        await session.commit()
    assert await run_embedding(factory, document_id, provider, settings)
    replacement = FakeEmbeddingProvider("replacement-model")
    async with AsyncSession(memory_engine) as session:
        document = await session.get(Document, document_id)
        assert document is not None
        document.status = DocumentStatus.EMBEDDING
        await session.commit()
    assert await run_embedding(factory, document_id, replacement, settings)
    async with AsyncSession(memory_engine) as session:
        models = set(
            (
                await session.scalars(
                    select(DocumentChunk.embedding_model).where(
                        DocumentChunk.document_id == document_id
                    )
                )
            ).all()
        )
        assert models == {"replacement-model"}
    sent: list[str] = []
    async with AsyncSession(memory_engine) as session:
        document = await session.get(Document, document_id)
        assert document is not None
        document.status = DocumentStatus.EMBEDDING
        await session.commit()
    assert await dispatch_embedding_documents(factory, lambda value, _cid: sent.append(value)) == 1
    assert sent == [str(document_id)]


class FailingProvider:
    name = "fake"
    model = "failed-model"

    async def embed(self, _inputs: list[str]) -> EmbeddingResponse:
        raise EmbeddingError(
            "embedding_provider_unavailable", "Embedding provider is unavailable", retryable=False
        )


class SequenceEmbeddingProvider:
    name = "fake"
    model = "sequence-embedding-model"

    def __init__(self, outcomes: list[EmbeddingError | EmbeddingResponse]) -> None:
        self.outcomes = outcomes
        self.calls = 0

    async def embed(self, _inputs: list[str]) -> EmbeddingResponse:
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, EmbeddingError):
            raise outcome
        return outcome


class RecordingEmbeddingProvider:
    name = "fake"
    model = "recording-embedding-model"

    def __init__(self) -> None:
        self.batch_sizes: list[int] = []

    async def embed(self, inputs: list[str]) -> EmbeddingResponse:
        self.batch_sizes.append(len(inputs))
        unit = tuple([1.0] + [0.0] * 1535)
        return EmbeddingResponse(
            tuple(unit for _ in inputs), EmbeddingUsage(len(inputs), len(inputs))
        )


class TransactionInspectingProvider:
    name = "fake"
    model = "transaction-inspection-model"

    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine
        self.lock_holder_states: list[str] = []

    async def embed(self, inputs: list[str]) -> EmbeddingResponse:
        async with AsyncSession(self.engine) as session:
            self.lock_holder_states = list(
                (
                    await session.scalars(
                        text(
                            "SELECT activity.state FROM pg_stat_activity AS activity "
                            "JOIN pg_locks AS locks ON locks.pid = activity.pid "
                            "WHERE locks.locktype = 'advisory' AND locks.granted "
                            "AND activity.datname = current_database()"
                        )
                    )
                ).all()
            )
        unit = tuple([1.0] + [0.0] * 1535)
        return EmbeddingResponse(tuple(unit for _ in inputs), EmbeddingUsage())


@pytest.mark.asyncio
async def test_embedding_failure_has_safe_terminal_state_and_no_partial_chunks(
    memory_engine: AsyncEngine, capsys: pytest.CaptureFixture[str]
) -> None:
    private_body = "private-document-body-sentinel"
    document_id, _, _, _ = await create_graph(memory_engine, content=private_body)
    factory = async_sessionmaker(memory_engine, expire_on_commit=False)
    assert not await run_embedding(factory, document_id, FailingProvider(), Settings())
    async with AsyncSession(memory_engine) as session:
        document = await session.get(Document, document_id)
        chunks = await session.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
        )
        usage = await session.scalar(
            select(AIUsageRecord).where(AIUsageRecord.task_type == "embedding")
        )
        assert document is not None and document.status == DocumentStatus.FAILED
        assert document.error_code == "embedding_provider_unavailable"
        assert chunks == 0
        assert usage is not None and not usage.succeeded
    assert private_body not in capsys.readouterr().out


@pytest.mark.asyncio
async def test_embedding_retry_budget_audits_every_real_call(
    memory_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EMBEDDING_INPUT_COST_PER_MILLION", "1")
    settings = Settings()
    document_id, _, _, _ = await create_graph(memory_engine, content="retry embedding")
    unit = tuple([1.0] + [0.0] * 1535)
    retryable = EmbeddingError(
        "embedding_provider_unavailable", "Embedding provider is unavailable", retryable=True
    )
    provider = SequenceEmbeddingProvider(
        [retryable, retryable, EmbeddingResponse((unit,), EmbeddingUsage(10, 10))]
    )
    sleeps: list[float] = []

    async def no_sleep(delay: float) -> None:
        sleeps.append(delay)

    factory = async_sessionmaker(memory_engine, expire_on_commit=False)
    assert await run_embedding(factory, document_id, provider, settings, sleep=no_sleep)
    assert provider.calls == 3 and sleeps == [2.0, 4.0]
    async with AsyncSession(memory_engine) as session:
        usage = list(
            (
                await session.scalars(
                    select(AIUsageRecord)
                    .where(AIUsageRecord.task_type == "embedding")
                    .order_by(AIUsageRecord.created_at)
                )
            ).all()
        )
        assert [row.succeeded for row in usage] == [False, False, True]
        assert usage[-1].estimated_cost == Decimal("0.000010")


@pytest.mark.asyncio
async def test_embedding_pipeline_batches_at_sixteen_chunks(
    memory_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EMBEDDING_CHUNK_SIZE", "256")
    monkeypatch.setenv("EMBEDDING_CHUNK_OVERLAP", "16")
    settings = Settings()
    document_id, _, _, _ = await create_graph(memory_engine, content="x" * 4000)
    provider = RecordingEmbeddingProvider()
    factory = async_sessionmaker(memory_engine, expire_on_commit=False)
    assert await run_embedding(factory, document_id, provider, settings)
    assert provider.batch_sizes == [16, 1]


@pytest.mark.asyncio
async def test_embedding_provider_runs_outside_database_transaction_and_row_lock(
    memory_engine: AsyncEngine,
) -> None:
    document_id, _, _, _ = await create_graph(memory_engine, content="transaction boundary")
    provider = TransactionInspectingProvider(memory_engine)
    factory = async_sessionmaker(memory_engine, expire_on_commit=False)
    assert await run_embedding(factory, document_id, provider, Settings())
    assert provider.lock_holder_states
    assert set(provider.lock_holder_states) == {"idle"}
    key = int.from_bytes(document_id.bytes[:8], "big", signed=True)
    async with AsyncSession(memory_engine) as session:
        assert await session.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": key})
        assert await session.scalar(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
        await session.commit()


@pytest.mark.asyncio
async def test_concurrent_bookmark_creation_has_one_success_and_one_conflict(
    memory_engine: AsyncEngine,
) -> None:
    document_id, _, _, owner_id = await create_graph(
        memory_engine, document_status=DocumentStatus.READY
    )

    async def create_once() -> object:
        async with AsyncSession(memory_engine) as session:
            try:
                return await create_bookmark(
                    session, user_id=owner_id, document_id=document_id, note=None
                )
            except AppError as exc:
                return exc

    results = await asyncio.gather(create_once(), create_once())
    assert sum(not isinstance(result, AppError) for result in results) == 1
    conflicts = [result for result in results if isinstance(result, AppError)]
    assert len(conflicts) == 1 and conflicts[0].code == "bookmark_exists"


@pytest.mark.asyncio
async def test_bookmark_persistent_authorization_and_sql_owned_search(
    memory_engine: AsyncEngine,
) -> None:
    document_id, _, radar_id, owner_id = await create_graph(memory_engine)
    stranger_id = await create_user(memory_engine)
    factory = async_sessionmaker(memory_engine, expire_on_commit=False)
    provider = FakeEmbeddingProvider(Settings().embedding_model)
    assert await run_embedding(factory, document_id, provider, Settings())
    async with AsyncSession(memory_engine) as session:
        bookmark = await create_bookmark(
            session, user_id=owner_id, document_id=document_id, note="remember"
        )
        bookmark_id = bookmark.id
        with pytest.raises(AppError) as hidden:
            await create_bookmark(session, user_id=stranger_id, document_id=document_id, note=None)
        assert hidden.value.status_code == 404
    owner_results = await search_memory(
        factory,
        user_id=owner_id,
        query="memory content",
        top_k=10,
        radar_id=None,
        date_from=None,
        date_to=None,
        bookmarked_only=True,
        provider=provider,
        settings=Settings(),
    )
    stranger_results = await search_memory(
        factory,
        user_id=stranger_id,
        query="memory content",
        top_k=10,
        radar_id=None,
        date_from=None,
        date_to=None,
        bookmarked_only=False,
        provider=provider,
        settings=Settings(),
    )
    assert len(owner_results) == 1 and owner_results[0]["bookmarked"] is True
    assert stranger_results == []
    async with AsyncSession(memory_engine) as session:
        radar = await session.get(Radar, radar_id)
        assert radar is not None
        radar.deleted_at = datetime.now(UTC)
        await session.commit()
    persisted = await search_memory(
        factory,
        user_id=owner_id,
        query="memory content",
        top_k=1,
        radar_id=None,
        date_from=None,
        date_to=None,
        bookmarked_only=False,
        provider=provider,
        settings=Settings(),
    )
    assert len(persisted) == 1
    with pytest.raises(AppError):
        await search_memory(
            factory,
            user_id=owner_id,
            query="memory content",
            top_k=1,
            radar_id=radar_id,
            date_from=None,
            date_to=None,
            bookmarked_only=False,
            provider=provider,
            settings=Settings(),
        )
    async with AsyncSession(memory_engine) as session:
        updated = await update_bookmark(
            session, user_id=owner_id, bookmark_id=bookmark_id, note=None
        )
        assert updated.note is None
        await delete_bookmark(session, user_id=owner_id, bookmark_id=bookmark_id)
    revoked = await search_memory(
        factory,
        user_id=owner_id,
        query="memory content",
        top_k=1,
        radar_id=None,
        date_from=None,
        date_to=None,
        bookmarked_only=False,
        provider=provider,
        settings=Settings(),
    )
    assert revoked == []


@pytest.mark.asyncio
async def test_memory_search_topk_stable_multi_radar_date_and_similarity_boundaries(
    memory_engine: AsyncEngine,
) -> None:
    occurred_at = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)
    document_id, first_analysis_id, first_radar_id, owner_id = await create_graph(
        memory_engine,
        content="identical-query",
        published_at=occurred_at,
    )
    factory = async_sessionmaker(memory_engine, expire_on_commit=False)
    settings = Settings()
    provider = FakeEmbeddingProvider(settings.embedding_model)
    assert await run_embedding(factory, document_id, provider, settings)
    async with AsyncSession(memory_engine, expire_on_commit=False) as session:
        radar = Radar(
            user_id=owner_id,
            name=f"Second radar {uuid4()}",
            goal="Second view",
            radar_type=RadarType.TECHNOLOGY,
            categories=["technology"],
            keywords=[],
            status=ResourceStatus.ACTIVE,
            notification_threshold=75,
        )
        session.add(radar)
        await session.flush()
        second = Analysis(
            document_id=document_id,
            radar_id=radar.id,
            pipeline_version="alpha-v1",
            prompt_version="intelligence-v1",
            summary="Second summary",
            category="technology",
            radar_score=Decimal("80.00"),
            recommendation=Recommendation.READ,
            status=AnalysisStatus.COMPLETED,
            created_at=datetime.now(UTC) + timedelta(seconds=1),
        )
        session.add(second)
        await session.commit()
        second_analysis_id = second.id

    async def search(**changes: object) -> list[dict[str, Any]]:
        values: dict[str, Any] = {
            "user_id": owner_id,
            "query": "identical-query",
            "top_k": 10,
            "radar_id": None,
            "date_from": None,
            "date_to": None,
            "bookmarked_only": False,
            "provider": provider,
            "settings": settings,
        }
        values.update(changes)
        return await search_memory(factory, **values)

    all_results = await search()
    assert [item["analysis_id"] for item in all_results] == [
        second_analysis_id,
        first_analysis_id,
    ]
    assert all(item["similarity"] == Decimal("1.000000") for item in all_results)
    assert len(await search(top_k=1)) == 1
    radar_results = await search(radar_id=first_radar_id)
    assert [item["analysis_id"] for item in radar_results] == [first_analysis_id]
    assert await search(radar_id=first_radar_id, bookmarked_only=True) == []
    bounded = await search(date_from=occurred_at, date_to=occurred_at)
    assert len(bounded) == 2
    assert await search(bookmarked_only=True) == []
    async with AsyncSession(memory_engine) as session:
        await create_bookmark(session, user_id=owner_id, document_id=document_id, note=None)
    assert len(await search(bookmarked_only=True)) == 2
    combined = await search(radar_id=first_radar_id, bookmarked_only=True)
    assert [item["analysis_id"] for item in combined] == [first_analysis_id]
    with pytest.raises(AppError) as foreign:
        await search(user_id=uuid4(), radar_id=first_radar_id, bookmarked_only=True)
    assert foreign.value.status_code == 404 and foreign.value.code == "resource_not_found"
    query_vector = (await provider.embed(["identical-query"])).vectors[0]
    async with AsyncSession(memory_engine) as session:
        chunks = list(
            (
                await session.scalars(
                    select(DocumentChunk).where(DocumentChunk.document_id == document_id)
                )
            ).all()
        )
        for chunk in chunks:
            chunk.embedding = [-value for value in query_vector]
        await session.commit()
    opposite = await search(top_k=1)
    assert opposite[0]["similarity"] == Decimal("0.000000")


async def register(client: AsyncClient, email: str) -> tuple[dict[str, str], UUID]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "memory-password-安全", "display_name": "Owner"},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['tokens']['access_token']}"}, UUID(
        response.json()["user"]["id"]
    )


@pytest.mark.asyncio
async def test_memory_api_bookmark_lifecycle_filters_and_openapi(
    memory_engine: AsyncEngine, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = Settings()
    factory = async_sessionmaker(memory_engine, expire_on_commit=False)
    app = create_app(settings, readiness_service=ReadinessService(healthy_probe, healthy_probe))
    app.state.session_factory = factory
    app.state.embedding_provider = FakeEmbeddingProvider(settings.embedding_model)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner_headers, owner_id = await register(client, "memory-api-owner@example.com")
        stranger_headers, _ = await register(client, "memory-api-stranger@example.com")
        document_id, analysis_id, radar_id, _ = await create_graph(
            memory_engine,
            user_id=owner_id,
            published_at=datetime.now(UTC) - timedelta(days=1),
        )
        assert await run_embedding(factory, document_id, app.state.embedding_provider, settings)
        created = await client.post(
            "/api/v1/bookmarks",
            headers=owner_headers,
            json={"document_id": str(document_id), "note": "  saved  "},
        )
        assert created.status_code == 201 and created.json()["note"] == "saved"
        bookmark_id = created.json()["id"]
        duplicate = await client.post(
            "/api/v1/bookmarks",
            headers=owner_headers,
            json={"document_id": str(document_id)},
        )
        hidden = await client.post(
            "/api/v1/bookmarks",
            headers=stranger_headers,
            json={"document_id": str(document_id)},
        )
        assert (
            duplicate.status_code == 409 and duplicate.json()["error"]["code"] == "bookmark_exists"
        )
        assert hidden.status_code == 404
        listing = await client.get("/api/v1/bookmarks?page=1&page_size=20", headers=owner_headers)
        assert listing.status_code == 200 and listing.json()["total"] == 1
        patched = await client.patch(
            f"/api/v1/bookmarks/{bookmark_id}", headers=owner_headers, json={"note": None}
        )
        assert patched.status_code == 200 and patched.json()["note"] is None
        empty_patch = await client.patch(
            f"/api/v1/bookmarks/{bookmark_id}", headers=owner_headers, json={}
        )
        assert empty_patch.status_code == 422
        feed = await client.get(f"/api/v1/intelligence/{analysis_id}", headers=owner_headers)
        assert feed.status_code == 200 and feed.json()["bookmarked"] is True
        private_query = "memory content private-query-sentinel"
        searched = await client.post(
            "/api/v1/memory/search",
            headers=owner_headers,
            json={"query": f"  {private_query}  ", "top_k": 50, "bookmarked_only": True},
        )
        assert searched.status_code == 200
        assert searched.json()["query"] == private_query
        assert searched.json()["items"][0]["analysis_id"] == str(analysis_id)
        combined = await client.post(
            "/api/v1/memory/search",
            headers=owner_headers,
            json={
                "query": "memory content",
                "radar_id": str(radar_id),
                "bookmarked_only": True,
            },
        )
        foreign_combined = await client.post(
            "/api/v1/memory/search",
            headers=stranger_headers,
            json={
                "query": "memory content",
                "radar_id": str(radar_id),
                "bookmarked_only": True,
            },
        )
        assert combined.status_code == 200 and len(combined.json()["items"]) == 1
        assert foreign_combined.status_code == 404
        invalid = await client.post(
            "/api/v1/memory/search",
            headers=owner_headers,
            json={"query": "x", "top_k": 51},
        )
        bad_dates = await client.post(
            "/api/v1/memory/search",
            headers=owner_headers,
            json={
                "query": "x",
                "date_from": "2026-08-28T00:00:00Z",
                "date_to": "2026-08-27T00:00:00Z",
            },
        )
        query_at_limit = await client.post(
            "/api/v1/memory/search",
            headers=owner_headers,
            json={"query": f"  {'x' * 4000}  "},
        )
        invalid_queries = [
            await client.post(
                "/api/v1/memory/search",
                headers=owner_headers,
                json={"query": "   "},
            ),
            await client.post(
                "/api/v1/memory/search",
                headers=owner_headers,
                json={"query": f"  {'x' * 4001}  "},
            ),
        ]
        invalid_dates = [
            await client.post(
                "/api/v1/memory/search",
                headers=owner_headers,
                json={"query": "x", "date_from": "2026-08-27T00:00:00"},
            ),
            await client.post(
                "/api/v1/memory/search",
                headers=owner_headers,
                json={
                    "query": "x",
                    "date_from": "2026-08-27T00:00:00",
                    "date_to": "2026-08-28T00:00:00Z",
                },
            ),
        ]
        valid_offset_dates = await client.post(
            "/api/v1/memory/search",
            headers=owner_headers,
            json={
                "query": "x",
                "date_from": "2026-08-27T08:00:00+08:00",
                "date_to": "2026-08-28T00:00:00Z",
            },
        )
        assert query_at_limit.status_code == 200
        assert query_at_limit.json()["query"] == "x" * 4000
        assert valid_offset_dates.status_code == 200
        validation_failures = [invalid, bad_dates, *invalid_queries, *invalid_dates]
        assert all(response.status_code == 422 for response in validation_failures)
        assert all(
            response.json()["error"]["code"] == "invalid_request"
            for response in validation_failures
        )
        deleted = await client.delete(f"/api/v1/bookmarks/{bookmark_id}", headers=owner_headers)
        hidden_delete = await client.delete(
            f"/api/v1/bookmarks/{bookmark_id}", headers=stranger_headers
        )
        assert deleted.status_code == 204 and hidden_delete.status_code == 404
        openapi = (await client.get("/openapi.json")).json()
        assert "/api/v1/bookmarks" in openapi["paths"]
        assert "/api/v1/bookmarks/{bookmark_id}" in openapi["paths"]
        assert "/api/v1/memory/search" in openapi["paths"]
        properties = openapi["components"]["schemas"]["IntelligenceItem"]["properties"]
        assert "bookmarked" in properties and "content" not in properties
        assert private_query not in capsys.readouterr().out
