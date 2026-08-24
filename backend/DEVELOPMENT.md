# Backend development

BE-1 contains infrastructure only; no business models or CRUD are implemented.

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
fail-fast and does not load `.env` implicitly.

```powershell
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
uv run celery -A app.tasks.celery_app:celery_app worker --loglevel=INFO
```

The initial migration enables pgvector and creates no business tables:

```powershell
uv run alembic upgrade head
uv run alembic downgrade base
uv run alembic upgrade head
```

Health endpoints:

- `GET /api/v1/health/live` never accesses dependencies.
- `GET /api/v1/health/ready` checks PostgreSQL and Redis concurrently.

Every HTTP response includes a validated UUID `X-Request-ID`.
