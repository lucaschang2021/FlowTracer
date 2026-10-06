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
- `opportunity_not_found` (missing or cross-user opportunity), `action_payload_unavailable`
  (opportunity exists but has no scored, human-approved action payload yet)
- `resource_not_found` for missing/cross-user sources or artifacts on the change-history endpoints
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
| Opportunity | `GET /opportunities`, `GET /opportunities/{opportunity_id}`, `GET /opportunities/{opportunity_id}/action-payload` |
| Change history | `GET /sources/{source_id}/changes`, `GET /sources/{source_id}/artifacts/{artifact_id}/changes` |

Manual collection and retry return HTTP 202. Collection responses include `Location`; clients
poll the referenced CollectionRun. `Idempotency-Key` on manual collection is optional, printable
ASCII after trimming, and at most 128 characters.

## Frozen enums

| Enum | Values |
| --- | --- |
| `RadarType` | `academic`, `business`, `technology`, `market`, `policy`, `competitive`, `custom`, `opportunity` |
| `ResourceStatus` | `active`, `paused`, `archived` |
| `SourceType` | `rss`, `url`, `api` (Alpha create accepts only `rss` and `url`) |
| `CollectionRunStatus` | `queued`, `running`, `succeeded`, `partial`, `failed` |
| `CollectionTriggerType` | `schedule`, `manual` |
| `RawItemStatus` | `fetched`, `cleaned`, `duplicate`, `failed` |
| `AnalysisStatus` | `pending`, `running`, `completed`, `failed` |
| `Recommendation` | `must_read`, `read`, `monitor`, `archive` |
| `NotificationPriority` | `normal`, `high`, `critical` |
| `NotificationStatus` | `unread`, `read` |
| `NotificationKind` | `intelligence`, `opportunity` |
| `OpportunityStatus` | `active`, `expired`, `removed`, `rejected` |
| `OpportunityRecommendation` | `act_now`, `review`, `watch`, `dismiss` |

`RadarType.opportunity` is the ACQ-1 compatibility change for generated clients: regenerate client
types. Creating an opportunity radar pairs with opportunity-family sources; its notifications use
`kind=opportunity`.

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
- opportunities: `GET /opportunities` and `GET /opportunities/{opportunity_id}/action-payload`

## Change history endpoints

`GET /sources/{source_id}/changes` lists version-evidence change events for a source; the
per-artifact variant `GET /sources/{source_id}/artifacts/{artifact_id}/changes` scopes the same
event stream to one artifact. Both use the standard pagination envelope and accept
`change_type` (`created`, `unchanged`, `content_changed`, `metadata_changed`,
`structure_changed`, `removed`); the source-level endpoint also accepts `artifact_id`.

Each item carries bounded display evidence only: the change `change_type`, `materiality`
(0..1), `field_diff` (bounded old/new values, at most 200 characters per value), the artifact
identity (`artifact_id`, `artifact_key`, `canonical_url`), `occurred_at`, `detector_version`,
and `previous`/`current` snapshot references (`id`, `version`, `title`, `content_hash`,
`quality_score`, `fetched_at`). Raw page content, prompts, and internal traces are never
returned. `created` events have no `previous`; `removed` events have no `current`.

## Opportunity notifications and action payloads

`NotificationResponse` carries `kind` and nullable fact targets: `analysis_id` is set only for
`kind=intelligence`, `opportunity_id` is set only for `kind=opportunity` (exactly one is non-null).
Opportunity notifications do **not** produce WebSocket events (the three frozen events above are
unchanged); recover them through `GET /notifications`.

Opportunity list filters: `radar_id`, `status`, `recommendation`, `min_score`, `currency`
(ISO-4217 uppercase), `deadline` (returns opportunities whose deadline is not after the value).
The detail response embeds the latest score; a changed observation re-enters the evaluator and produces a new scored version (latest by `scored_at` wins). Items flip to `expired` when their deadline passes and to `removed` when the source page disappears; a reappearing page reactivates the item. The action payload endpoint returns the immutable,
non-executable projection (`payload`, `payload_version`, `payload_hash`, `generated_at`); the
payload always contains `requires_human_approval=true` and never carries credentials, proposal
text, or any execution capability. Treat the payload as read-only display data.

## Known Alpha limits

- RSS and HTML URL sources are supported; Dynamic/Advanced Browser stays disabled and is not
  admitted (R3 BLOCKED) — sources must stay on the static paths.
- Controlled Discovery consumes its frontier through the same SafeFetcher pipeline (robots policy,
  per-hop scope/SSRF re-checks, cross-page budgets). Targets are consumed once per artifact:
  completed pages are not re-crawled on later runs, and discovery-side removal detection is not
  performed (feed/single-page sources keep the two-miss removal rule).
- Change Intelligence drives the write path: qualifying snapshots (`created`, `content_changed`)
  produce new RawItems (snapshot-identity linked); metadata/structure-only changes stay events.
  Non-qualifying observations count as duplicates, so `duplicate_count` now means "already-covered
  content", not "identical raw text".
- Opportunity Radar covers first-seen and changed listings: changed pages refresh the item in
  place, re-evaluation produces a new scored version (and a new notification when it qualifies),
  and `expired`/`removed` transitions follow deadline and disappearance. Platform-side access
  authorization workflows, semantic-change classification, and multi-currency FX are **not** part
  of this Alpha (non-USD listings are rejected as `currency_unsupported`; no exchange-rate lookup
  exists). Action payloads are read-only and require a human to act outside this product.
- WebSocket is an online hint, not a durable queue. REST/PostgreSQL is the fact source.
- One configured Analysis Provider and one Embedding Provider are used; there is no router/fallback.
- Compose embeds Beat in one worker service. Do not scale that service above one replica.
- No teams/RBAC, external push/email, native desktop notification implementation, external knowledge
  synchronization, production deployment, or SLA is included in the backend Alpha.
