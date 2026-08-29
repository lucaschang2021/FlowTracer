# FlowTracer Alpha backend frontend handoff

This document and `openapi/flowtracer-alpha-v0.1.json` are the frozen Alpha backend contract.
Frontend consumers must not infer fields from database models. When this document and the generated
schema disagree, stop integration and report a contract defect.

## Contract artifacts

- Base URL: `http://localhost:8000/api/v1`
- Frozen OpenAPI: `openapi/flowtracer-alpha-v0.1.json`
- Interactive development schema: `GET /openapi.json`
- WebSocket: `ws://localhost:8000/api/v1/ws`
- Generate: `uv run python scripts/export_openapi.py`
- Verify: `uv run python scripts/export_openapi.py --check`

OpenAPI is serialized as UTF-8 JSON with sorted keys and a trailing newline. CI or integration
checks should use `--check`; a changed snapshot requires Backend contract review.

## Authentication and request conventions

- Registration and login return an HS256 Access Token and an opaque Refresh Token.
- Access Token lifetime is 15 minutes. Send it only as `Authorization: Bearer <access-token>`.
- Refresh Token lifetime is 30 days. Refresh rotates the token; concurrent reuse of the old token
  is rejected. Logout is idempotent and revokes the presented Refresh Token.
- WebSocket accepts the Access Token only in the handshake Authorization header. Query-string and
  cookie tokens are rejected.
- All API request and response fields use `snake_case`.
- Send `Content-Type: application/json` for JSON bodies.
- A valid UUID `X-Request-ID` may be supplied; otherwise the API creates one. The response echoes
  the accepted/generated value.
- Unknown JSON fields and empty PATCH bodies are rejected with HTTP 422.

Error responses always use:

```json
{
  "error": {
    "code": "resource_not_found",
    "message": "Resource not found",
    "details": {},
    "request_id": "00000000-0000-4000-8000-000000000000"
  }
}
```

Treat `error.code` as the stable machine value. Messages are safe display text, not localization
keys. Common HTTP mappings are 401 authentication, 404 missing or cross-user resource, 409 state or
uniqueness conflict, 422 request validation, 502 invalid provider output, and 503 dependency/queue
unavailability. Stable client-visible codes include:

- `invalid_request`, `invalid_access_token`, `invalid_credentials`,
  `invalid_refresh_token`, `email_already_registered`
- `resource_not_found`, `invalid_resource_state`, `radar_name_conflict`,
  `source_url_conflict`, `source_not_active`, `unsupported_source_type`
- `collection_run_not_retryable`, `analysis_not_retryable`, `bookmark_exists`
- `collection_queue_unavailable`, `analysis_queue_unavailable`, `service_not_ready`
- `ai_invalid_output`, `ai_timeout`, `ai_rate_limited`, `ai_provider_unavailable`,
  `ai_auth_failed`
- `embedding_invalid_output`, `embedding_timeout`, `embedding_rate_limited`,
  `embedding_provider_unavailable`, `embedding_auth_failed`
- `internal_error` (show a generic retry/error UI and retain the request ID for diagnostics)

## Pagination and ordering

List endpoints accept `page` (default 1) and `page_size` (default 20, maximum 100) and return:

```json
{"items": [], "page": 1, "page_size": 20, "total": 0}
```

Ordering is stable and server-defined. Do not reimplement cursor assumptions from UUIDs or
timestamps. Filters and exact request/response schemas are defined in OpenAPI.

## REST endpoint inventory

| Area | Methods and paths |
| --- | --- |
| Health | `GET /health/live`, `GET /health/ready` |
| Auth/User | `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `GET/PATCH /users/me` |
| Radar | `GET/POST /radars`, `GET/PATCH/DELETE /radars/{radar_id}`, `POST /radars/{radar_id}/pause`, `POST /radars/{radar_id}/resume` |
| Radar sources | `GET /radars/{radar_id}/sources`, `POST/DELETE /radars/{radar_id}/sources/{source_id}` |
| Source | `GET/POST /sources`, `GET/PATCH/DELETE /sources/{source_id}`, `POST /sources/{source_id}/pause`, `POST /sources/{source_id}/resume` |
| Acquisition | `POST /sources/{source_id}/collect`, `GET /sources/{source_id}/runs`, `GET /collection-runs/{run_id}`, `GET /collection-runs/{run_id}/items`, `POST /collection-runs/{run_id}/retry` |
| Intelligence | `GET /intelligence`, `GET /intelligence/{analysis_id}`, `POST /analyses/{analysis_id}/retry` |
| Memory | `GET/POST /bookmarks`, `PATCH/DELETE /bookmarks/{bookmark_id}`, `POST /memory/search` |
| Notification | `GET /notifications`, `POST /notifications/{notification_id}/read`, `POST /notifications/read-all` |

Manual collection and retry return HTTP 202. Collection responses include `Location`; clients
poll the referenced CollectionRun. `Idempotency-Key` on manual collection is optional, printable
ASCII after trimming, and at most 128 characters.

## Frozen enums

| Enum | Values |
| --- | --- |
| `RadarType` | `academic`, `business`, `technology`, `market`, `policy`, `competitive`, `custom` |
| `ResourceStatus` | `active`, `paused`, `archived` |
| `SourceType` | `rss`, `url`, `api` (Alpha create accepts only `rss` and `url`) |
| `CollectionRunStatus` | `queued`, `running`, `succeeded`, `partial`, `failed` |
| `CollectionTriggerType` | `schedule`, `manual` |
| `RawItemStatus` | `fetched`, `cleaned`, `duplicate`, `failed` |
| `AnalysisStatus` | `pending`, `running`, `completed`, `failed` |
| `Recommendation` | `must_read`, `read`, `monitor`, `archive` |
| `NotificationPriority` | `normal`, `high`, `critical` |
| `NotificationStatus` | `unread`, `read` |

## Representative payloads

Register:

```json
{
  "email": "person@example.com",
  "password": "<user-entered-password>",
  "display_name": "Person"
}
```

Create and bind resources:

```json
{
  "name": "Technology radar",
  "description": "Optional context",
  "goal": "Track material technology changes",
  "radar_type": "technology",
  "categories": ["platforms"],
  "keywords": ["runtime", "database"],
  "notification_threshold": 75
}
```

```json
{
  "name": "Example feed",
  "source_type": "rss",
  "url": "https://example.com/feed.xml",
  "poll_interval_minutes": 60,
  "config": {}
}
```

Memory search:

```json
{
  "query": "reliable background processing",
  "top_k": 10,
  "radar_id": null,
  "date_from": "2026-01-01T00:00:00Z",
  "date_to": "2026-12-31T23:59:59Z",
  "bookmarked_only": false
}
```

Date filters require a UTC offset and are normalized to UTC. Search query validation happens after
trimming; `top_k` is 1..50.

## WebSocket contract and recovery

Connect with:

```text
Authorization: Bearer <access-token>
```

Every event has:

```json
{
  "event_id": "00000000-0000-4000-8000-000000000000",
  "event_type": "notification.created",
  "occurred_at": "2026-08-28T00:00:00Z",
  "data": {
    "notification_id": "00000000-0000-4000-8000-000000000001",
    "analysis_id": "00000000-0000-4000-8000-000000000002",
    "priority": "high"
  }
}
```

The three frozen events and their `data` fields are:

- `collection.updated`: `collection_run_id`, `source_id`, `status`, `fetched_count`,
  `created_count`, `duplicate_count`, `failed_count`
- `analysis.completed`: `analysis_id`, `document_id`, `radar_id`, `radar_score`,
  `recommendation`
- `notification.created`: `notification_id`, `analysis_id`, `priority`

Deduplicate by `event_id`. Multiple connections for one user are supported, but delivery is best
effort and globally unordered. Close 4401 means the Access Token is invalid, the user is inactive or
deleted, or the token expired while connected. Close 1013 means Redis or the bounded connection queue
is unavailable; reconnect with backoff.

After every reconnect, foreground resume, 1013, or suspected event gap, recover facts through REST:

- collection: `GET /sources/{source_id}/runs` and `GET /collection-runs/{run_id}`
- analysis: `GET /intelligence` or `GET /intelligence/{analysis_id}`
- notifications: `GET /notifications?status=unread`

## Known Alpha limits

- RSS and a single HTML page are supported; no authenticated browsing or deep crawl.
- WebSocket is an online hint, not a durable queue. REST/PostgreSQL is the fact source.
- One configured Analysis Provider and one Embedding Provider are used; there is no router/fallback.
- Compose embeds Beat in one worker service. Do not scale that service above one replica.
- No teams/RBAC, external push/email, native desktop notification implementation, external knowledge
  synchronization, production deployment, or SLA is included in the backend Alpha.
