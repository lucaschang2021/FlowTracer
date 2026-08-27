from __future__ import annotations

from uuid import uuid4

import pytest

from app.tasks import acquisition, intelligence
from app.tasks.health import ping


def test_celery_health_task() -> None:
    correlation_id = str(uuid4())
    result = ping.apply(kwargs={"correlation_id": correlation_id})

    assert result.successful()
    assert result.get() == {"status": "ok", "correlation_id": correlation_id}


def test_acquisition_task_wrappers_and_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[tuple[list[str], dict[str, str]]] = []
    monkeypatch.setattr(
        acquisition.collect_source,
        "apply_async",
        lambda args, kwargs: sent.append((args, kwargs)),
    )
    run_id = str(uuid4())
    acquisition.enqueue_collection(run_id, "correlation")
    assert sent == [([run_id], {"correlation_id": "correlation"})]

    async def return_two(_operation: object) -> int:
        return 2

    monkeypatch.setattr(acquisition, "_with_database", return_two)
    scheduled = acquisition.schedule_sources.apply()
    dispatched = acquisition.dispatch_runs.apply()
    collected = acquisition.collect_source.apply(
        args=[run_id], kwargs={"correlation_id": "task-correlation"}
    )
    assert scheduled.successful() and scheduled.get() == 2
    assert dispatched.successful() and dispatched.get() == 2
    assert collected.successful() and collected.get() is True


@pytest.mark.asyncio
async def test_acquisition_database_wrapper_always_disposes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Engine:
        disposed = False

        async def dispose(self) -> None:
            self.disposed = True

    engine = Engine()
    factory = object()
    monkeypatch.setattr(acquisition, "create_database_engine", lambda _settings: engine)
    monkeypatch.setattr(acquisition, "create_session_factory", lambda _engine: factory)

    async def operation(value: object) -> str:
        assert value is factory
        return "ok"

    assert await acquisition._with_database(operation) == "ok"
    assert engine.disposed


def test_intelligence_task_wrappers_and_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    raw_sent: list[tuple[list[str], dict[str, str]]] = []
    analysis_sent: list[tuple[list[str], dict[str, str]]] = []
    embedding_sent: list[tuple[list[str], dict[str, str]]] = []
    monkeypatch.setattr(
        intelligence.process_raw_item,
        "apply_async",
        lambda args, kwargs: raw_sent.append((args, kwargs)),
    )
    monkeypatch.setattr(
        intelligence.analyze_document,
        "apply_async",
        lambda args, kwargs: analysis_sent.append((args, kwargs)),
    )
    monkeypatch.setattr(
        intelligence.embed_document,
        "apply_async",
        lambda args, kwargs: embedding_sent.append((args, kwargs)),
    )
    item_id = str(uuid4())
    analysis_id = str(uuid4())
    document_id = str(uuid4())
    intelligence.enqueue_raw_item(item_id, "raw-correlation")
    intelligence.enqueue_analysis(analysis_id, "analysis-correlation")
    intelligence.enqueue_embedding(document_id, "embedding-correlation")
    assert raw_sent == [([item_id], {"correlation_id": "raw-correlation"})]
    assert analysis_sent == [([analysis_id], {"correlation_id": "analysis-correlation"})]
    assert embedding_sent == [([document_id], {"correlation_id": "embedding-correlation"})]

    async def return_one(_operation: object) -> int:
        return 1

    monkeypatch.setattr(intelligence, "_with_database", return_one)
    assert intelligence.process_raw_item.apply(args=[item_id]).get() is True
    assert intelligence.analyze_document.apply(args=[analysis_id]).get() is True
    assert intelligence.embed_document.apply(args=[document_id]).get() is True
    assert intelligence.dispatch_raw_items.apply().get() == 1
    assert intelligence.dispatch_analyses.apply().get() == 1
    assert intelligence.recover_analyses.apply().get() == 1
    assert intelligence.dispatch_embeddings.apply().get() == 1


@pytest.mark.asyncio
async def test_intelligence_database_wrapper_always_disposes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Engine:
        disposed = False

        async def dispose(self) -> None:
            self.disposed = True

    engine = Engine()
    factory = object()
    monkeypatch.setattr(intelligence, "create_database_engine", lambda _settings: engine)
    monkeypatch.setattr(intelligence, "create_session_factory", lambda _engine: factory)

    async def operation(value: object) -> str:
        assert value is factory
        return "ok"

    assert await intelligence._with_database(operation) == "ok"
    assert engine.disposed
