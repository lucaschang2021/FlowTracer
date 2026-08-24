# BE-1 local infrastructure runbook

`compose.yaml` runs API, Worker, PostgreSQL 16 with pgvector 0.8.6, and Redis 7.4.11. API and Worker
use the same backend image.

From the repository root:

```powershell
docker compose -f infra/compose.yaml config
docker compose -f infra/compose.yaml up --build -d
docker compose -f infra/compose.yaml ps
docker compose -f infra/compose.yaml exec api alembic upgrade head
```

Verify the API and Worker:

```powershell
curl.exe http://localhost:8000/api/v1/health/live
curl.exe http://localhost:8000/api/v1/health/ready
docker compose -f infra/compose.yaml exec worker celery -A app.tasks.celery_app:celery_app call flowtracer.tasks.health.ping
```

Stop services with `docker compose -f infra/compose.yaml down`. Named database and Redis volumes are
retained unless explicitly removed.
