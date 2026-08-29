# FlowTracer Alpha backend operations

This runbook covers reproducible local development and handoff validation. It is not a production
deployment guide.

## Quick Start

From the repository root:

```powershell
docker compose -f infra/compose.yaml config
docker compose -f infra/compose.yaml build api
docker compose -f infra/compose.yaml up -d --wait postgres redis
docker compose -f infra/compose.yaml run --rm api alembic upgrade head
docker compose -f infra/compose.yaml up -d --wait api worker
curl.exe http://localhost:8000/api/v1/health/live
curl.exe http://localhost:8000/api/v1/health/ready
docker compose -f infra/compose.yaml exec worker celery -A app.tasks.celery_app:celery_app inspect ping
```

This order is intentional: only PostgreSQL and Redis start before the migration. The
one-off `run --rm api` container applies the schema without starting the API server or
the worker's embedded Beat process. API and Worker start only after Alembic reaches
`head`. The validated Compose CLI supports waiting for both services in one command;
this procedure does not remove or recreate named volumes.

Expected services are exactly `api`, `worker`, `postgres`, and `redis`. API and worker use the
same image and run as non-root UID 10001. The worker embeds one Beat process and writes its
container-local schedule to `/tmp/flowtracer-celerybeat-schedule`.

Stop without damaging the development database/Redis volumes:

```powershell
docker compose -f infra/compose.yaml down
```

Do not add `--volumes` unless deletion of the named development data is explicitly intended.

## Environment matrix

The application is fail-fast and does not load `.env` implicitly. Values shown in
`.env.example` are local examples, never shared credentials.

| Variable | Required | Local/Fake guidance |
| --- | --- | --- |
| `FLOWTRACER_ENV` | yes | `development`; tests use `test` |
| `FLOWTRACER_LOG_LEVEL` | yes | `INFO`; standard Python levels only |
| `FLOWTRACER_APP_VERSION` | yes | `0.1.0` for Alpha |
| `FLOWTRACER_API_HOST`, `FLOWTRACER_API_PORT` | yes | `0.0.0.0`, `8000` in Compose |
| `DATABASE_URL` | yes | PostgreSQL asyncpg URL; never log or return it |
| `TEST_DATABASE_URL` | tests | Database name must contain `_test`; destructive tests refuse other names |
| `REDIS_URL` | yes | App readiness and WebSocket Pub/Sub |
| `CELERY_BROKER_URL` | yes | Celery broker; may share Redis server with a distinct logical DB |
| `CELERY_RESULT_BACKEND` | yes | Celery results; use a distinct logical DB |
| `JWT_SECRET` | yes | At least 32 bytes; rotate outside source control |
| `ACCESS_TOKEN_TTL_MINUTES` | yes | Frozen Alpha value `15` |
| `REFRESH_TOKEN_TTL_DAYS` | yes | Frozen Alpha value `30` |
| `JWT_ISSUER`, `JWT_AUDIENCE` | yes | `flowtracer-api`, `flowtracer-desktop` |
| `AI_PROVIDER`, `AI_MODEL` | yes | Offline: `fake`, `flowtracer-fake-v1` |
| `AI_INPUT_COST_PER_MILLION`, `AI_OUTPUT_COST_PER_MILLION` | yes | Non-negative finite Decimal; Fake uses `0` |
| `AI_BASE_URL`, `AI_API_KEY` | conditional | Required only for `openai_compatible`; HTTPS outside loopback tests |
| `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL` | yes | Offline: `fake`, `flowtracer-fake-embedding-v1` |
| `EMBEDDING_INPUT_COST_PER_MILLION` | yes | Non-negative finite Decimal; Fake uses `0` |
| `EMBEDDING_CHUNK_SIZE`, `EMBEDDING_CHUNK_OVERLAP` | yes | Frozen defaults `1200`, `200`; overlap must be smaller |
| `EMBEDDING_BASE_URL`, `EMBEDDING_API_KEY` | conditional | Required only for `openai_compatible`; HTTPS outside loopback tests |

## Migrations and test isolation

Development migration:

```powershell
uv run alembic upgrade head
uv run alembic check
```

BE-8 acceptance uses a uniquely named temporary PostgreSQL database, never the development
`flowtracer` database:

```powershell
# Set DATABASE_URL to an isolated PostgreSQL asyncpg URL whose database is:
# flowtracer_be8_<unique>_test
uv run alembic upgrade head
uv run alembic downgrade base
uv run alembic upgrade head
uv run alembic check
```

Drop only that exact verified `*_test` database after validation. Never run truncation or downgrade
against a URL whose database name does not contain `_test`.

## Tests and frozen OpenAPI

From `backend/`:

```powershell
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest
uv run python scripts/export_openapi.py --check
```

The complete offline closure is `tests/test_alpha_e2e.py`. It uses local RSS/HTML fixtures, Fake
Analysis/Embedding Providers, an isolated PostgreSQL database, and isolated Redis logical databases.
It must never access public networks.

To intentionally regenerate the reviewed schema:

```powershell
uv run python scripts/export_openapi.py
git diff -- openapi/flowtracer-alpha-v0.1.json
```

Any diff is a contract change and requires Backend/controller review.

## Worker, Beat, and recovery

- One Compose worker embeds Beat; do not scale it above one replica.
- Beat schedule is ephemeral and owned by UID 10001. A normal restart can reuse it; recreating the
  worker removes it without leaving a volume.
- Beat dispatches due-source scheduling and queued-run, fetched-item, pending-analysis,
  stale-analysis, embedding, and notification compensation every 60 seconds.
- Queue publication failures do not erase committed facts. Dispatchers recover queued/pending facts.
- WebSocket/Redis failure does not roll back database facts. Clients recover through REST.
- A failed/partial CollectionRun can create one idempotent retry child; a failed Analysis can return
  to pending through its existing retry endpoint.

Troubleshooting order:

1. `docker compose -f infra/compose.yaml ps`
2. `GET /api/v1/health/live` then `GET /api/v1/health/ready`
3. Celery `inspect ping`
4. worker logs for safe event/error codes (never copy secrets or full payloads)
5. verify worker UID, Beat schedule ownership, Redis/PostgreSQL health, and migration head
6. use REST to inspect persisted runs, Intelligence, and Notifications

## Security and cleanup

- Never log or paste passwords, Access/Refresh Tokens, API keys, Authorization headers, connection
  strings, full Source config, document body, Prompt/model output, query text, or vectors.
- Acquisition blocks local/private/link-local/metadata destinations and revalidates every redirect.
- Tests use `.invalid` URLs plus injected fetchers/transports; they do not resolve or fetch them.
- Use unique temporary databases/Redis logical DBs for acceptance. Confirm exact names before cleanup.
- Preserve the named development volumes unless deletion is explicitly authorized.

See `FRONTEND-HANDOFF.md` for API/WebSocket behavior and `PERFORMANCE-BASELINE.md` for the bounded
local measurement.
