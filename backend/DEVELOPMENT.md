# Backend development

BE-6 extends intelligence with deterministic Document chunking, independent embedding providers,
1536-dimensional pgvector storage, Bookmark CRUD, and SQL-scoped Memory Search. Notification,
WebSocket, external knowledge-base sync, and BE-7+ remain out of scope.

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
