# FlowTracer Alpha v0.1 BE-2 数据与认证基线

- 状态：Accepted for BE-2 admission
- 适用范围：BE-2 数据模型、迁移、认证与用户
- 变更控制：字段语义、公开 API、Token 生命周期、约束或删除策略变化时，必须先由总控修订本基线或新增 ADR。

## 1. 阶段边界

BE-2 落地全部 Alpha 关系实体、首批业务迁移以及 Auth/User 闭环，但只为后续阶段建立模型，不实现 Radar、Source、采集、AI、Memory 或 Notification 的业务 API、调度与 Pipeline。

## 2. 数据库通用规则

- PostgreSQL 16；主键统一为原生 `uuid`，由应用生成 UUID v4。
- 时间统一为 `timestamptz`、数据库与 API 均使用 UTC；所有表的 `created_at` 非空，标记 `timestamps` 的可变实体同时具有非空 `updated_at`。
- 金额使用 `numeric(12,6)`，禁止浮点；计数使用非负 `integer`，耗时使用非负 `integer` 毫秒。
- 枚举使用 SQLAlchemy/Python 枚举并以字符串值持久化；迁移必须显式创建和删除 PostgreSQL enum type。
- 用户拥有的数据默认软删除，`deleted_at` 可空；认证令牌和不可变运行/审计产物不使用软删除。
- 所有外键列建立索引；所有面向用户的查询必须显式带 `user_id` 所有权条件。
- JSON 字段使用 `jsonb`，默认 `{}` 或 `[]`，不得使用可变 Python 默认值。
- 文本正文不设数据库长度上限；名称、标题、标识符等按本文件长度约束。除明确标记 `null` 的字段外，所列字段均为 `not null`。
- 迁移必须从仅含 `20260824_0001` 的空业务库升级；downgrade 只移除 BE-2 对象，不移除 pgvector 扩展。

## 3. Alpha 关系模型

### 3.1 用户与认证

`users`

| 字段 | 类型与约束 |
| --- | --- |
| `id` | uuid PK |
| `email` | varchar(320) not null；存储 `email-validator` 规范化结果；唯一索引仅覆盖 `deleted_at IS NULL` |
| `password_hash` | varchar(255) not null；仅 Argon2id PHC 字符串 |
| `display_name` | varchar(80) not null |
| `profile` | jsonb not null default `{}` |
| `is_active` | boolean not null default true |
| `created_at`、`updated_at` | timestamptz not null |
| `deleted_at` | timestamptz null |

`refresh_tokens`

| 字段 | 类型与约束 |
| --- | --- |
| `id` | uuid PK；同时作为公开 Token selector |
| `user_id` | uuid FK `users.id` on delete cascade，not null，indexed |
| `token_hash` | char(64) not null unique；SHA-256 lowercase hex |
| `expires_at` | timestamptz not null，indexed |
| `revoked_at` | timestamptz null |
| `replaced_by_token_id` | uuid FK `refresh_tokens.id` on delete set null，null |
| `created_at` | timestamptz not null |

### 3.2 Radar 与来源

`radars`：`id`; `user_id` FK users cascade; `name` varchar(120); `description` text null; `goal` text; `radar_type`; `categories` jsonb list default `[]`; `keywords` jsonb list default `[]`; `status` default `active`; `notification_threshold` smallint default 75 check 0..100; timestamps; `deleted_at`. Active records have unique `(user_id, name)` where `deleted_at IS NULL`.

`sources`：`id`; `user_id` FK users cascade; `name` varchar(160); `source_type`; `url` text; `normalized_url` text; `poll_interval_minutes` integer default 60 check >=15; `status` default `active`; `last_fetched_at`/`next_fetch_at` timestamptz null; `config` jsonb default `{}`; timestamps; `deleted_at`. Active records have unique `(user_id, normalized_url)` where `deleted_at IS NULL`; index `(status, next_fetch_at)`.

`radar_sources`：`radar_id` FK radars cascade + `source_id` FK sources cascade composite PK; `created_at` not null. Service layer must prove both records belong to the same user before insertion.

### 3.3 采集与内容

`collection_runs`：`id`; `source_id` FK sources restrict; `triggered_by_user_id` FK users set null; `trigger_type`; `status`; `idempotency_key` varchar(128) null; `started_at`/`finished_at` null; `fetched_count`/`created_count`/`duplicate_count`/`failed_count` non-negative default 0; `error_code` varchar(80) null; `error_message` varchar(500) null; `created_at`/`updated_at`. Unique `(source_id, idempotency_key)` where key is not null; index `(source_id, created_at desc)`.

`raw_items`：`id`; `source_id` FK sources restrict; `collection_run_id` FK collection_runs cascade; `external_id` varchar(512) null; `canonical_url` text; `title` text null; `published_at` null; `fetched_at` not null; `content_type` varchar(160) null; `raw_text` text; `content_hash` char(64); DB 列 `metadata` jsonb default `{}`（ORM 属性名使用 `item_metadata`，避开 SQLAlchemy 保留名）; `status`; `error_code`/`error_message` nullable safe fields; timestamps. Unique `(source_id, external_id)` where external ID is not null; index `content_hash`.

`documents`：`id`; `raw_item_id` FK raw_items restrict and unique; `canonical_url` text; `title` text; `author` varchar(300) null; `language` varchar(16) null; `content` text; `word_count` non-negative integer; `content_hash` char(64) unique; `status`; `error_code`/`error_message` nullable safe fields; timestamps. Index `(status, created_at)`.

### 3.4 Intelligence、Memory 与通知

`analyses`：`id`; `document_id` FK documents cascade; `radar_id` FK radars cascade; `pipeline_version` varchar(64); `prompt_version` varchar(64); `summary` text null; `category` varchar(120) null; `relevance`/`importance`/`novelty`/`impact` smallint nullable check 0..100; `radar_score` numeric(5,2) nullable check 0..100; `recommendation` nullable; `reason` varchar(1000) null; `provider` varchar(80) null; `model` varchar(160) null; `status`; `error_code`/`error_message` nullable safe fields; timestamps. Unique `(document_id, radar_id, pipeline_version)`; index `(radar_id, status, created_at desc)`.

`document_chunks`：`id`; `document_id` FK documents cascade; `chunk_index` non-negative integer; `content` text; `embedding` vector(1536); `embedding_model` varchar(160); `created_at`. Unique `(document_id, chunk_index, embedding_model)`; BE-6 才建立有实际查询参数依据的向量 ANN 索引。

`bookmarks`：`id`; `user_id` FK users cascade; `document_id` FK documents cascade; `note` text null; timestamps; unique `(user_id, document_id)`.

`notifications`：`id`; `user_id` FK users cascade; `analysis_id` FK analyses cascade; `title` varchar(240); `content` text; `priority`; `reason` varchar(1000); `url` text null; `status` default `unread`; `created_at`; `read_at` null. Unique `(user_id, analysis_id)`; index `(user_id, status, created_at desc)`.

`ai_usage_records`：`id`; `user_id` FK users cascade; `analysis_id` FK analyses set null; `task_type` varchar(80); `provider` varchar(80); `model` varchar(160); `input_tokens`/`output_tokens`/`total_tokens` non-negative integer default 0; `estimated_cost` numeric(12,6) default 0; `duration_ms` non-negative integer; `succeeded` boolean; `error_code` varchar(80) null; `created_at`. Index `(user_id, created_at desc)`.
## 4. 枚举冻结

- `radar_type`: `academic | business | technology | market | policy | competitive | custom`
- Radar/Source `status`: `active | paused | archived`
- `source_type`: `rss | url | api`；BE-3 必须拒绝创建 `api`
- `collection_trigger_type`: `schedule | manual`
- CollectionRun `status`: `queued | running | succeeded | partial | failed`
- RawItem `status`: `fetched | cleaned | duplicate | failed`
- Document `status`: `pending | cleaning | deduplicating | analyzing | embedding | ready | failed`
- Analysis `status`: `pending | running | completed | failed`
- `recommendation`: `must_read | read | monitor | archive`
- Notification `priority`: `normal | high | critical`
- Notification `status`: `unread | read`

## 5. 密码与 Token

- 密码输入 10..128 个 Unicode 字符；禁止静默截断。使用 `argon2-cffi` Argon2id：`time_cost=3`、`memory_cost=65536` KiB、`parallelism=4`、`hash_len=32`、`salt_len=16`，并支持在成功登录后按当前参数 rehash。
- Access Token：JWT `HS256`，有效期 15 分钟；必含 `sub`（user UUID）、`jti`（UUID）、`type=access`、`iat`、`nbf`、`exp`、`iss=flowtracer-api`、`aud=flowtracer-desktop`。
- Refresh Token：非 JWT 的 32-byte CSPRNG URL-safe opaque secret；客户端值格式为 `<token_id>.<secret>`；数据库仅保存完整客户端值的 SHA-256。
- Refresh Token 有效期 30 天；刷新时必须轮换并原子撤销旧 Token，记录 `replaced_by_token_id`；撤销、过期、用户停用或用户软删除均拒绝刷新。
- Logout 使用 Refresh Token 幂等撤销；不存在、已撤销或已过期 Token 不泄露其存在性。
- 新增必需配置：`JWT_SECRET`（至少 32 bytes，SecretStr）、`ACCESS_TOKEN_TTL_MINUTES=15`、`REFRESH_TOKEN_TTL_DAYS=30`、`JWT_ISSUER=flowtracer-api`、`JWT_AUDIENCE=flowtracer-desktop`。Compose 仅提供明确标注的本地示例 Secret；生产值不得提交。
- Token、密码、哈希、Authorization Header 不得进入结构化日志或错误响应。

## 6. Auth/User REST 契约

所有路径位于 `/api/v1`，请求/响应 JSON 使用 `snake_case`。

- `POST /auth/register`：`{email, password, display_name}`；成功 `201` 返回 `{user, tokens}`；重复活动邮箱 `409 email_already_registered`。
- `POST /auth/login`：`{email, password}`；成功 `200` 返回 `{user, tokens}`；凭据错误、用户不存在或不可用统一返回 `401 invalid_credentials`。
- `POST /auth/refresh`：`{refresh_token}`；成功 `200` 返回轮换后的 `{tokens}`；无效/过期/撤销统一返回 `401 invalid_refresh_token`。
- `POST /auth/logout`：`{refresh_token}`；成功或已失效均返回 `204`，响应无 body。
- `GET /users/me`：Bearer Access Token；成功 `200` 返回 User。
- `PATCH /users/me`：Bearer Access Token；允许 `{display_name?, profile?}`，至少一个字段；成功 `200` 返回 User。BE-2 不支持修改邮箱或密码。

User 响应：`{id, email, display_name, profile, is_active, created_at, updated_at}`，不得返回 `password_hash`、删除状态或 Token 记录。

Token 响应：`{access_token, refresh_token, token_type: "bearer", expires_in: 900}`。

受保护接口缺少、错误或过期 Access Token 统一返回 `401 invalid_access_token` 并带 `WWW-Authenticate: Bearer`。请求验证继续使用 `422 invalid_request`；所有错误遵循统一错误 Envelope。

## 7. 事务与并发要求

- 注册依赖数据库唯一约束解决并发重复邮箱；不得只做先查后插。
- Refresh rotation 必须在单事务内锁定旧 Token、撤销旧 Token并创建新 Token；并发刷新至多一个成功。
- Auth 成功路径提交后再返回 Token；失败路径完整回滚。
- 认证查询不得返回软删除或 `is_active=false` 的用户。

## 8. BE-2 验收门槛

- `uv sync --locked`、Ruff、格式、Mypy、完整 Pytest 和覆盖率门禁全部通过。
- 空业务库执行 `upgrade head -> downgrade` 到 BE-1 revision -> `upgrade head` 成功；模型 metadata 与迁移无漂移。
- 测试覆盖全部实体约束、枚举、外键删除策略与唯一索引。
- Auth 覆盖注册、并发/重复邮箱、登录、JWT 过期/篡改、Refresh 轮换/撤销/并发、Logout 幂等、停用用户和 `/users/me`。
- 安全测试证明响应与日志不包含明文密码、Token、Token 哈希、JWT Secret 或连接串。
- OpenAPI 中 Auth/User Schema、Bearer security 和统一错误响应与本文件一致。
- 使用真实 PostgreSQL/Redis 的集成测试不得连接开发数据库；测试数据库名必须包含 `_test`。
