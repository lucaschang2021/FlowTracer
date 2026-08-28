# Backend development

BE-7 extends intelligence with threshold-qualified Notification facts, best-effort user-isolated
Redis WebSocket events, and idempotent CollectionRun retry/recovery. Native desktop notifications,
external push, durable event buses, and BE-8+ remain out of scope.

## Requirements

- CPython 3.13
- uv
- Docker Desktop with Linux containers for full local validation

Run quality checks from `backend/`:

```powershell
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest
```

Export the variables in `backend/.env.example` before starting host processes. Configuration is
fail-fast and does not load `.env` implicitly. `JWT_SECRET` must contain at least 32 bytes; the
checked-in value is only a local example.

`AI_PROVIDER=fake` is deterministic and offline for local development and tests. The
`openai_compatible` provider additionally requires `AI_BASE_URL` and `AI_API_KEY`; non-test URLs
must use HTTPS without userinfo, query, fragment, or redirects. `AI_MODEL` and both non-negative
per-million token rates are always explicit. Provider credentials, prompts, document content, and
raw model responses must never be logged.

`EMBEDDING_PROVIDER=fake` is deterministic, L2-normalized, and offline. Remote embedding requires
`EMBEDDING_BASE_URL` and `EMBEDDING_API_KEY`, uses identity/raw streaming with a 2 MiB hard limit,
and accepts no redirects. Chunk size defaults to 1200 Unicode code points with 200 overlap. Query
text, chunk content, vectors, keys, tokens, and connection strings must never be logged.

```powershell
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
uv run celery -A app.tasks.celery_app:celery_app worker --beat --loglevel=INFO
```

Apply and verify migrations:

```powershell
uv run alembic upgrade head
uv run alembic downgrade 20260824_0002
uv run alembic upgrade head
uv run alembic check
```

Integration tests require a real PostgreSQL database whose name contains `_test`. Set
`TEST_DATABASE_URL` explicitly; tests refuse a URL without that suffix. Never point it at the
development database.

Auth/User endpoints:

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/users/me`
- `PATCH /api/v1/users/me`

Acquisition endpoints:

- `POST /api/v1/sources/{source_id}/collect`
- `GET /api/v1/sources/{source_id}/runs`
- `GET /api/v1/collection-runs/{run_id}`
- `GET /api/v1/collection-runs/{run_id}/items`
- `POST /api/v1/collection-runs/{run_id}/retry`

Intelligence endpoints:

- `GET /api/v1/intelligence`
- `GET /api/v1/intelligence/{analysis_id}`
- `POST /api/v1/analyses/{analysis_id}/retry`

Memory endpoints:

- `POST /api/v1/bookmarks`
- `GET /api/v1/bookmarks`
- `PATCH /api/v1/bookmarks/{bookmark_id}`
- `DELETE /api/v1/bookmarks/{bookmark_id}`
- `POST /api/v1/memory/search`

Notification and online-event endpoints:

- `GET /api/v1/notifications`
- `POST /api/v1/notifications/{notification_id}/read`
- `POST /api/v1/notifications/read-all`
- `WS /api/v1/ws`

The WebSocket accepts an Access Token only through the handshake `Authorization: Bearer` header.
It uses a Redis channel scoped to the authenticated user, closes with 4401 on authentication or
token expiry, and closes with 1013 on Redis failure or per-connection queue backpressure. Events
are best effort; reconnecting clients recover facts through REST.

The optional `Idempotency-Key` header on manual collection is printable ASCII, trimmed, and
limited to 128 characters. The API commits a queued run before broker dispatch; the periodic
dispatcher recovers queued runs after transient broker failures.

All acquisition requests go through the controlled fetcher: only HTTP(S) ports 80/443 are
allowed, every redirect is DNS/IP revalidated, the validated IP is bound to the connection, and
responses enforce fixed time and post-decompression size limits. Tests inject resolvers and
transports and never access public networks. Source config, credentials, URL query strings, and
response bodies must never be logged.

BE-4 does not add a database migration. Health endpoints and request-ID behavior from BE-1 remain
unchanged.

BE-6 adds a 60-second dispatcher for Documents left in `embedding`. A session advisory lock
serializes each Document, while short transactions bracket remote calls. Chunk replacement and
the `embedding -> ready` transition commit atomically; failures store only stable safe errors.
Migration `20260827_0003` adds only the cosine HNSW index (`m=16`, `ef_construction=64`).

BE-7 adds no migration. A 60-second Notification dispatcher recovers eligible completed analyses,
and the existing queued-run dispatcher recovers retry children retained after broker failures.
Notification and online events are published only after database commit; Redis publication failure
does not roll back facts. Event payloads never contain document body, Prompt, vectors, Source config,
credentials, tokens, connection strings, or cost records.

The official Compose worker embeds one Beat process and stores its schedule at
`/tmp/flowtracer-celerybeat-schedule`, which is writable by the non-root UID 10001 and remains
container-local. Recreating the worker removes that schedule file; a normal restart may reuse it.
Do not scale the Compose worker above one replica while it embeds Beat, because multiple Beat
instances would enqueue the same periodic tasks.
