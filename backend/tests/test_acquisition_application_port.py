from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.domains.acquisition_ports import PublishedEvent, RunClaim, RunCompletion
from app.models.entities import AcquisitionMode, DiscoveryMode, SourceFamily, SourceType
from app.schemas.events import EventEnvelope
from app.schemas.resources import AcquisitionProfileV1
from app.services.acquisition import execute_run
from app.services.acquisition_types import AcquisitionRequest, AcquisitionResult, FetchResponse
from app.services.events import build_event


class FakeBackend:
    def __init__(self) -> None:
        self.requests: list[AcquisitionRequest] = []

    async def acquire(self, request: AcquisitionRequest) -> AcquisitionResult:
        self.requests.append(request)
        return AcquisitionResult(
            FetchResponse(
                request.target_url,
                "text/html",
                b"<html><head><title>Fixture</title></head><body>Offline body</body></html>",
            ),
            retry_count=0,
            budget_used={"requests": 1},
        )


class FakeRunRepository:
    def __init__(self, run_id: UUID) -> None:
        self.run_id = run_id
        self.source_id = uuid4()
        self.user_id = uuid4()
        self.claim = RunClaim(
            run_id,
            SimpleNamespace(
                id=self.source_id,
                normalized_url="https://example.test/article",
                source_type=SourceType.URL,
                source_family=SourceFamily.GENERIC_WEB,
                acquisition_mode=AcquisitionMode.NATIVE,
                discovery_mode=DiscoveryMode.SINGLE_PAGE,
                acquisition_profile=AcquisitionProfileV1().model_dump(mode="json"),
            ),
            uuid4(),
        )
        self.finished = False
        self.failures: list[tuple[str, str]] = []

    async def claim_run(self, run_id: UUID, *, worker_id: str, now: datetime | None = None) -> Any:
        del worker_id, now
        return self.claim if run_id == self.run_id else None

    async def heartbeat(self, run_id: UUID, claim_token: UUID) -> bool:
        del run_id, claim_token
        return True

    async def finish_success(
        self,
        claim: Any,
        *,
        backend_name: str,
        attempt_started_at: datetime,
        result: AcquisitionResult,
        parsed: Any,
        quality_score: Decimal | None,
    ) -> RunCompletion:
        del claim, backend_name, attempt_started_at, result, quality_score
        self.finished = True
        return RunCompletion(
            self.source_id,
            "succeeded",
            parsed.fetched_count,
            len(parsed.candidates),
            0,
            parsed.failed_count,
            (uuid4(),),
        )

    async def finish_failure(self, claim: Any, **kwargs: Any) -> bool:
        del claim
        self.failures.append((kwargs["error_code"], kwargs["safe_error"]))
        return True

    async def event_for(self, run_id: UUID) -> PublishedEvent[EventEnvelope] | None:
        if not self.finished:
            return None
        event = build_event(
            "collection.updated",
            run_id,
            "succeeded",
            {
                "collection_run_id": run_id,
                "source_id": self.source_id,
                "status": "succeeded",
                "fetched_count": 1,
                "created_count": 1,
                "duplicate_count": 0,
                "failed_count": 0,
            },
        )
        return PublishedEvent(self.user_id, event)


class FakePublisher:
    def __init__(self, repository: FakeRunRepository) -> None:
        self.repository = repository
        self.events: list[tuple[UUID, EventEnvelope]] = []

    async def publish(self, user_id: UUID, event: EventEnvelope) -> None:
        assert self.repository.finished
        self.events.append((user_id, event))


@pytest.mark.asyncio
async def test_execute_run_uses_injected_ports_without_infrastructure() -> None:
    run_id = uuid4()
    repository = FakeRunRepository(run_id)
    backend = FakeBackend()
    publisher = FakePublisher(repository)
    dispatched: list[str] = []

    assert await execute_run(
        repository,  # type: ignore[arg-type]
        run_id,
        backend=backend,
        publisher=publisher,
        raw_dispatch=lambda raw_id, _correlation: dispatched.append(raw_id),
    )

    assert len(backend.requests) == 1
    assert backend.requests[0].run_id == run_id
    assert repository.finished
    assert not repository.failures
    assert len(dispatched) == 1
    assert [(user_id, event.event_type) for user_id, event in publisher.events] == [
        (repository.user_id, "collection.updated")
    ]
