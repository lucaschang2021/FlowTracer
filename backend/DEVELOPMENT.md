# Backend development

BE-4 adds RSS/Atom and single-page URL acquisition to the existing Auth/User and Radar/Source
APIs. Document cleaning, AI, embedding, notification, WebSocket, deep crawling, and manual retry
remain out of scope.

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

```powershell
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
uv run celery -A app.tasks.celery_app:celery_app worker --beat --loglevel=INFO
```

Apply and verify migrations:

```powershell
uv run alembic upgrade head
uv run alembic downgrade 20260824_0001
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
