"""WP-8 offline performance baseline (docs/25 §15, docs/67 §1).

Component micro-benchmarks over local fixtures plus a small routed-run sample on
the isolated ``*_test`` database. Every input is local: no public network, no
Browser runtime. Dynamic Browser and Browser concurrency are reported as
NOT MEASURED because the capability is disabled (docs/68).

Methodology: sorted samples, median for p50, nearest-rank for p95, maximum for
max; 20 warm-up iterations excluded per component. Run-level peak memory uses
``tracemalloc`` (Python allocations only). These numbers are a reproducibility
reference for this host and fixture set, not an SLA or capacity claim.

Usage: python scripts/benchmark_offline.py
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import sys
import time
import tracemalloc
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from sqlalchemy import delete, select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.adapters.acquisition.static_scrapling import observe_html  # noqa: E402
from app.domains.opportunity_policy import (  # noqa: E402
    Dimensions,
    OpportunityFacts,
    hard_filter,
    overall_score,
    recommendation_for,
)
from app.models.entities import (  # noqa: E402
    AcquisitionAttempt,
    AcquisitionMode,
    BackendName,
    CollectionRun,
    DiscoveryMode,
    RawItem,
    Source,
    SourceAcquisitionState,
    SourceFamily,
    SourceType,
    User,
)
from app.models.evidence import (  # noqa: E402
    AcquisitionSnapshot,
    ChangeEvent,
    SourceArtifact,
)
from app.schemas.resources import AcquisitionProfileV1  # noqa: E402
from app.services.acquisition_parsers import parse_feed, parse_html  # noqa: E402
from app.services.acquisition_route import execute_route_run  # noqa: E402
from app.services.acquisition_router import select_candidates  # noqa: E402
from app.services.acquisition_run_repository import (  # noqa: E402
    SqlAlchemyAcquisitionRunRepository,
)
from app.services.acquisition_types import AcquisitionResult, FetchResponse  # noqa: E402
from app.services.extraction import attach_extraction_observations  # noqa: E402
from app.services.version_evidence import (  # noqa: E402
    content_fingerprint,
    metadata_fingerprint,
    metadata_values,
    normalize_content,
    structure_fingerprint,
    structure_summary,
)

COMPONENT_ITERATIONS = 200
ROUTER_ITERATIONS = 2000
WARMUP_ITERATIONS = 20
RUN_SAMPLES = 10
NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)

HTML_BODY = (
    b"<html><head><title>Baseline fixture</title></head><body><main>"
    + b"Deterministic offline extraction baseline content. " * 60
    + b"</main></body></html>"
)
FEED_BODY = (
    b"<?xml version='1.0'?><rss version='2.0'><channel><title>Baseline</title>"
    b"<item><title>Entry</title><link>https://fixtures.invalid/entry</link>"
    b"<description>" + b"Deterministic entry content. " * 30 + b"</description>"
    b"</item></channel></rss>"
)


def _percentiles(samples: list[float]) -> dict[str, float]:
    ordered = sorted(samples)
    index = min(len(ordered) - 1, math.ceil(0.95 * len(ordered)) - 1)
    return {
        "samples": len(ordered),
        "p50_ms": round(ordered[len(ordered) // 2], 3),
        "p95_ms": round(ordered[index], 3),
        "max_ms": round(ordered[-1], 3),
    }


def _measure(operation: Callable[[], object], iterations: int) -> dict[str, float]:
    for _ in range(WARMUP_ITERATIONS):
        operation()
    samples: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter()
        operation()
        samples.append((time.perf_counter() - started) * 1000)
    return _percentiles(samples)


def _component_results() -> dict[str, dict[str, float]]:
    html_response = FetchResponse(
        "https://fixtures.invalid/page", "text/html; charset=utf-8", HTML_BODY
    )
    feed_response = FetchResponse(
        "https://fixtures.invalid/feed.xml", "application/rss+xml", FEED_BODY
    )
    parsed_html = parse_html(html_response, "https://fixtures.invalid/page")
    parsed_feed = parse_feed(feed_response)
    result = AcquisitionResult(html_response, retry_count=0, budget_used={})
    text = HTML_BODY.decode("utf-8")
    normalized = normalize_content(text)
    values = metadata_values(
        title="Baseline", author=None, published_at=NOW, content_type="text/html"
    )
    summary = structure_summary(
        body=HTML_BODY, content_type="text/html", normalized_content=normalized
    )
    facts = OpportunityFacts(
        title="Landing page refresh",
        description="Build a small landing page with React.",
        source_url="https://fixtures.invalid/gig",
        platform="fixtures.invalid",
        budget_min=Decimal("50.00"),
        budget_max=Decimal("60.00"),
        currency="USD",
        skills=("React",),
        deadline=NOW,
        published_at=NOW,
        estimated_effort_hours=Decimal("4.00"),
        delivery_type="one_off",
        required_meetings=1,
        maintenance_required=False,
    )
    dimensions = Dimensions(90, 88, 86, 84, 82, 20, 15, 10)
    return {
        "native_parse_html": _measure(
            lambda: parse_html(html_response, "https://fixtures.invalid/page"),
            COMPONENT_ITERATIONS,
        ),
        "native_parse_feed": _measure(lambda: parse_feed(feed_response), COMPONENT_ITERATIONS),
        "scrapling_static_observe": _measure(
            lambda: observe_html(html_response, SourceFamily.GENERIC_WEB, "generic"),
            COMPONENT_ITERATIONS,
        ),
        "extraction_attach": _measure(
            lambda: attach_extraction_observations(
                result,
                family=SourceFamily.GENERIC_WEB,
                content_profile="generic",
                source_type=SourceType.URL,
                parsed=parsed_html,
            ),
            COMPONENT_ITERATIONS,
        ),
        "version_evidence_trio": _measure(
            lambda: (
                content_fingerprint(normalized),
                metadata_fingerprint(values),
                structure_fingerprint(summary),
            ),
            COMPONENT_ITERATIONS,
        ),
        "opportunity_policy": _measure(
            lambda: (
                hard_filter(facts),
                recommendation_for(overall_score(dimensions)),
            ),
            COMPONENT_ITERATIONS,
        ),
        "router_select_candidates": _measure(
            lambda: select_candidates(
                source_type=SourceType.URL, mode=AcquisitionMode.AUTO, allow_browser=False
            ),
            ROUTER_ITERATIONS,
        ),
        "extraction_feed_attach": _measure(
            lambda: attach_extraction_observations(
                AcquisitionResult(feed_response, retry_count=0, budget_used={}),
                family=SourceFamily.GENERIC_WEB,
                content_profile="generic",
                source_type=SourceType.RSS,
                parsed=parsed_feed,
            ),
            COMPONENT_ITERATIONS,
        ),
    }


class StubBackend:
    """Deterministic local stage double for run-level sampling; no network."""

    async def acquire(self, request: Any) -> AcquisitionResult:
        return AcquisitionResult(
            FetchResponse(request.target_url, "text/html; charset=utf-8", HTML_BODY),
            retry_count=0,
            budget_used={
                "requests": 1,
                "pages": 1,
                "bytes_received": len(HTML_BODY),
            },
        )


async def _run_level_results(database_url: str) -> dict[str, object]:
    if "_test" not in database_url.rsplit("/", maxsplit=1)[-1]:
        raise SystemExit("refusing to run: database name must contain _test")
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    user_id = uuid.uuid4()
    durations: list[float] = []
    peaks: list[int] = []
    budgets: list[dict[str, Any]] = []
    fallbacks: list[int] = []
    try:
        async with factory() as session:
            user = User(
                id=user_id,
                email=f"perf-{uuid.uuid4()}@example.com",
                password_hash="synthetic",  # noqa: S106 - isolated database fixture
                display_name="Perf",
            )
            source = Source(
                id=uuid.uuid4(),
                user_id=user_id,
                name="Perf Source",
                source_type=SourceType.URL,
                url="https://fixtures.invalid/perf",
                normalized_url="https://fixtures.invalid/perf",
                acquisition_mode=AcquisitionMode.AUTO,
                discovery_mode=DiscoveryMode.SINGLE_PAGE,
                acquisition_profile=AcquisitionProfileV1().storage_dict(),
            )
            session.add(user)
            await session.flush()
            session.add(source)
            await session.flush()
            session.add(SourceAcquisitionState(source_id=source.id))
            await session.commit()
            source_id = source.id
        repository = SqlAlchemyAcquisitionRunRepository(factory)
        # One warm-up run is excluded from the samples, matching the component methodology.
        for index in range(RUN_SAMPLES + 1):
            async with factory() as session:
                run = CollectionRun(
                    id=uuid.uuid4(),
                    source_id=source_id,
                    trigger_type="manual",
                    status="queued",
                )
                session.add(run)
                await session.commit()
                run_id = run.id
            tracemalloc.start()
            started = time.perf_counter()
            ok = await execute_route_run(
                repository,
                run_id,
                backends={BackendName.NATIVE_HTTP: StubBackend()},
                task_id=f"perf-{index}",
            )
            duration = (time.perf_counter() - started) * 1000
            peak = tracemalloc.get_traced_memory()[1]
            tracemalloc.stop()
            if not ok:
                raise SystemExit("routed run failed during sampling")
            if index == 0:
                continue
            durations.append(duration)
            peaks.append(peak)
            async with factory() as session:
                stored = await session.get(CollectionRun, run_id)
                if stored is None:
                    raise SystemExit("sampled run disappeared")
                budgets.append(dict(stored.budget_summary or {}))
                fallbacks.append(int(stored.fallback_count or 0))
    finally:
        async with factory() as session:
            source_ids = select(Source.id).where(Source.user_id == user_id)
            run_ids = select(CollectionRun.id).where(CollectionRun.source_id.in_(source_ids))
            artifact_ids = select(SourceArtifact.id).where(SourceArtifact.source_id.in_(source_ids))
            await session.execute(
                delete(ChangeEvent).where(ChangeEvent.artifact_id.in_(artifact_ids))
            )
            await session.execute(
                delete(AcquisitionSnapshot).where(AcquisitionSnapshot.artifact_id.in_(artifact_ids))
            )
            await session.execute(
                delete(SourceArtifact).where(SourceArtifact.source_id.in_(source_ids))
            )
            await session.execute(
                delete(AcquisitionAttempt).where(AcquisitionAttempt.source_id.in_(source_ids))
            )
            await session.execute(delete(RawItem).where(RawItem.source_id.in_(source_ids)))
            await session.execute(delete(CollectionRun).where(CollectionRun.id.in_(run_ids)))
            await session.execute(
                delete(SourceAcquisitionState).where(
                    SourceAcquisitionState.source_id.in_(source_ids)
                )
            )
            await session.execute(delete(Source).where(Source.id.in_(source_ids)))
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
        await engine.dispose()
    return {
        "runs": _percentiles(durations),
        "peak_memory_bytes_max": max(peaks),
        "fallback_count": fallbacks,
        "budget_summary": budgets[0] if budgets else {},
        "browser": "NOT MEASURED (capability disabled)",
    }


def main() -> None:
    database_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if database_url is None:
        print(json.dumps({"status": "failed", "message": "TEST_DATABASE_URL is required"}))
        raise SystemExit(1)
    report = {
        "host_note": "local Windows host, isolated fixture, providers=deterministic stubs",
        "components": _component_results(),
        "routed_run": asyncio.run(_run_level_results(database_url)),
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print("BENCHMARK COMPLETE")


if __name__ == "__main__":
    main()
