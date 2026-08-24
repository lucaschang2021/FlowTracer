# Backend development

BE-2 adds the complete Alpha relational model plus the Auth/User API. Radar, Source, collection,
AI, embedding, notification, and WebSocket business APIs remain out of scope.

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
uv run celery -A app.tasks.celery_app:celery_app worker --loglevel=INFO
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

Health endpoints and request-ID behavior from BE-1 remain unchanged.
