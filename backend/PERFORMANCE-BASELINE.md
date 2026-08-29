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
