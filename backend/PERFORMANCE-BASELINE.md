# FlowTracer Alpha lightweight performance baseline

Measured 2026-08-28 on the local Windows host with Docker Desktop Linux containers. The official
four-service Compose stack was warm and healthy, API and worker used the same image, PostgreSQL and
Redis were local, and requests were sequential over loopback with no competing synthetic load.
Providers were configured as Fake. Three warm-up requests per endpoint were excluded.

| Endpoint | Samples | p50 | p95 | Maximum |
| --- | ---: | ---: | ---: | ---: |
| `GET /api/v1/health/live` | 100 | 3.89 ms | 23.41 ms | 27.89 ms |
| `GET /api/v1/health/ready` | 50 | 6.53 ms | 22.42 ms | 32.45 ms |
| `GET /openapi.json` | 20 | 5.16 ms | 7.45 ms | 21.61 ms |

The measurement used Python `urllib.request`, `time.perf_counter()`, sorted samples, median for
p50, and the nearest observed 95th-percentile sample. Readiness includes one PostgreSQL and one Redis
probe; liveness does not access dependencies.

This is a reproducibility and regression reference, not a capacity result, SLA, concurrency claim,
or production sizing recommendation. No optimization was made from this small sample. Future
performance work must specify hardware, dataset size, concurrency, warm-up, provider/network mode,
and percentile method before comparing results.

## ACQ-1 offline baseline (WP-8, 2026-10-05)

Measured with `python scripts/benchmark_offline.py` on the local Windows host against the isolated
test database. All inputs are local fixtures; providers and stage backends are deterministic stubs;
no public network and no Browser runtime. Methodology: sorted samples, median for p50, nearest-rank
for p95, maximum for max, 20 warm-up iterations excluded per component, and one warm-up routed run
excluded from the ten run samples. This is a reproducibility reference for this host and fixture
set only.

Component micro-benchmarks (200 samples each; Router 2000):

| Component | p50 | p95 | Max |
| --- | ---: | ---: | ---: |
| Native HTML parse (`parse_html`, ~2.8 KB fixture) | 0.062 ms | 0.094 ms | 0.278 ms |
| Native feed parse (`parse_feed`) | 0.118 ms | 0.212 ms | 0.346 ms |
| Scrapling static observation (`observe_html`) | 1.665 ms | 2.413 ms | 3.656 ms |
| Extraction attach (URL/HTML) | 1.587 ms | 1.960 ms | 2.838 ms |
| Extraction attach (RSS) | 0.814 ms | 1.150 ms | 38.773 ms |
| Version evidence trio (normalize + 3 fingerprints) | 0.010 ms | 0.010 ms | 0.022 ms |
| Opportunity policy (hard filter + score) | 0.014 ms | 0.015 ms | 0.114 ms |
| Router candidate selection | 0.002 ms | 0.002 ms | 0.048 ms |

Routed run sample (`execute_route_run`, single static stage, isolated PostgreSQL, N=10 after one
warm-up run): p50 **81.9 ms**, p95/max **126.6 ms**; peak Python-traced memory (tracemalloc)
**≈ 124 KB** per run; fallback frequency **0/10**; per-source budget for the fixture
(`budget_summary`): requests 1, pages 1, bytes_received 3143, accepted backend `native_http`,
decision version `router-v1`.

Dynamic Browser latency and Browser concurrency: **NOT MEASURED — capability disabled**
(`BROWSER_DYNAMIC_ENABLED=False`, WP-3 not admitted). No number is reported, estimated, or implied
for browser paths.
