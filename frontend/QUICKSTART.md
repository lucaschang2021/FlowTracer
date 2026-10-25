# FlowTracer Alpha v0.1 · Windows Quick Start

FlowTracer is a local Windows desktop client backed by the four-service FlowTracer stack. The desktop client uses only the fixed native loopback endpoint `http://127.0.0.1:8000/api/v1`; it does not use a browser proxy.

## Prerequisites

- Windows x64 with Microsoft Edge WebView2 Runtime.
- Docker Desktop with Docker Compose available.
- This repository, including `infra/compose.yaml` and the Backend configuration described in [`backend/ALPHA-OPERATIONS.md`](../backend/ALPHA-OPERATIONS.md).
- Required Backend environment values. The Backend does not load `.env` automatically. Local offline evaluation uses the configured Fake analysis and embedding providers; never reuse example secrets.

## Start the Backend first

From the repository root, run these commands in order. The migration must finish before API and Worker start.

```powershell
docker compose -f infra/compose.yaml config
docker compose -f infra/compose.yaml build api
docker compose -f infra/compose.yaml up -d --wait postgres redis
docker compose -f infra/compose.yaml run --rm api alembic upgrade head
docker compose -f infra/compose.yaml up -d --wait api worker
curl.exe http://127.0.0.1:8000/api/v1/health/live
curl.exe http://127.0.0.1:8000/api/v1/health/ready
docker compose -f infra/compose.yaml exec worker celery -A app.tasks.celery_app:celery_app inspect ping
```

Continue only when `health/live` is `ok`, `health/ready` is `ready` with database and Redis both `ok`, and the Worker replies `pong`. Keep exactly one Worker replica because it embeds the Beat scheduler.

## Install and open the desktop app

Run the x64 NSIS installer listed in [`RELEASE-CANDIDATE.md`](RELEASE-CANDIDATE.md). It installs for the current Windows user and does not require administrator elevation. Start FlowTracer from the installed shortcut while the Backend remains ready.

The installer has not yet received the separate install/start smoke gate. See the release-candidate record before relying on it outside the controlled Alpha environment.

## First local workflow

1. Register a local account, then sign in. Authentication tokens exist only in native process memory; closing and reopening the app requires signing in again.
2. Create a Radar for the topic you want to monitor.
3. Open that Radar's Sources panel, create a supported RSS or static URL Source, and bind it to the Radar. Sources created by the desktop are ordinary sources for the Signals workflow.
4. Start one collection and watch its run status. Collection is queued; the Worker performs the work.
5. Open Signals to filter results, inspect a signal, and add its document to Memory.
6. Use Memory to edit notes or run semantic search. Removing a bookmark updates the currently displayed search result without deleting the underlying document.
7. Open Opportunities to review opportunity facts already produced by a Backend-configured opportunity-family Source and the read-only action payload. Creating an Opportunity Radar does not convert an ordinary desktop-created RSS/URL Source into an opportunity source. FlowTracer does not submit, bid, purchase, message, or otherwise execute that payload.
8. Open Settings to review and mark in-app REST notifications as read.

The clearly labeled Demo uses local fixtures only. It does not register an account, call the Backend, collect sources, or write real data.

## Evidence boundaries and known limits

- Fake Provider and local RSS/HTML fixture results prove the offline pipeline only; they do not prove public-internet collection or a production AI provider.
- Dynamic/Advanced Browser collection is disabled. Use only admitted static RSS/URL paths.
- The desktop Source form creates ordinary sources. Opportunity-family Source configuration is a frozen Backend API/operations task; it is not exposed by this desktop form.
- PLUGIN-1 is deferred until after Alpha v0.1.
- Opportunities and action payloads are read-only. There is no automatic external execution.
- Desktop tokens are memory-only and are not restored after an app restart.

## Stop and troubleshoot

Stop the Backend while preserving the development database and Redis volumes:

```powershell
docker compose -f infra/compose.yaml down
```

Do not add `--volumes` unless you explicitly intend to delete local development data.

If the app reports that the local API is unavailable:

1. Confirm `http://127.0.0.1:8000/api/v1/health/live` and `/health/ready` return the expected healthy responses.
2. Confirm the migration command completed before API/Worker startup.
3. Confirm Docker Desktop is running and the `api`, `worker`, `postgres`, and `redis` services are healthy.
4. Confirm the Worker responds to the Celery ping command above.
5. Restart the desktop app and sign in again; a previous process token cannot be reused.

Keep request IDs shown by the app when reporting an API error. Do not weaken the fixed loopback address, native command allowlist, redirect refusal, or CSP to work around a startup problem.
