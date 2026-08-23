# FlowTracer Alpha v0.1 后端契约基线

## 1. 统一约定

- API Base URL：`/api/v1`。
- 主键：UUID v4；数据库时间使用 UTC；API 时间使用带时区 ISO 8601。
- JSON 字段使用 `snake_case`。
- 分页参数：`page` 默认 1；`page_size` 默认 20、最大 100。
- 分页响应：`{items, page, page_size, total}`。
- 错误响应：`{error: {code, message, details, request_id}}`。
- 业务对象默认软删除；所有用户数据查询必须显式包含 `user_id`。
- 后台任务使用业务幂等键；手动采集支持 `Idempotency-Key`。

## 2. Alpha 核心实体

### User 与认证

- `User`：`id`、唯一规范化 `email`、`password_hash`、`display_name`、`profile` JSON、`is_active`、时间戳。
- `RefreshToken`：`id`、`user_id`、`token_hash`、`expires_at`、`revoked_at`、`created_at`。只保存 Token 哈希。

### Radar 与 Source

- `Radar`：`id`、`user_id`、`name`、`description`、`goal`、`radar_type`、`categories`、`keywords`、`status`、`notification_threshold`、时间戳、`deleted_at`。
- `radar_type`：`academic | business | technology | market | policy | competitive | custom`。
- `status`：`active | paused | archived`；通知阈值范围 0–100，默认 75。
- `Source`：`id`、`user_id`、`name`、`source_type`、`url`、`normalized_url`、`poll_interval_minutes`、`status`、`last_fetched_at`、`next_fetch_at`、`config`、时间戳、`deleted_at`。
- Alpha 可创建的 `source_type` 为 `rss | url`；`api` 只保留枚举。
- `poll_interval_minutes` 默认 60、最小 15；`user_id + normalized_url` 唯一。
- `RadarSource`：`radar_id + source_id` 联合唯一，多对多关联。

### 采集与内容

- `CollectionRun`：来源、触发用户、`schedule | manual` 触发类型、运行状态、开始/结束时间、各类计数和安全化错误。
- 运行状态：`queued | running | succeeded | partial | failed`。
- `RawItem`：来源、运行、外部 ID、Canonical URL、标题、发布时间、抓取时间、Content-Type、原始文本、内容哈希和元数据。
- RawItem 状态：`fetched | cleaned | duplicate | failed`。
- `Document`：RawItem、Canonical URL、标题、作者、语言、标准化正文、字数、内容哈希、处理状态和时间戳；`content_hash` 唯一。

### AI、Memory 与通知

- `Analysis`：`document_id`、`radar_id`、Pipeline/Prompt 版本、摘要、分类、四维评分、综合分、Recommendation、原因、Provider/Model、状态和时间戳。
- `document_id + radar_id + pipeline_version` 唯一。
- Analysis 状态：`pending | running | completed | failed`。
- `DocumentChunk`：文档、顺序、内容、pgvector `vector(1536)`、Embedding Model；文档、顺序、模型联合唯一。
- `Bookmark`：用户、文档、笔记和时间；`user_id + document_id` 唯一。
- `Notification`：用户、Analysis、标题、内容、`normal | high | critical` 优先级、原因、URL、`unread | read` 状态和时间。
- `AIUsageRecord`：用户、Analysis、任务类型、Provider/Model、Token、估算成本、耗时、成功状态和错误码。

## 3. 处理状态机

```text
pending -> cleaning -> deduplicating -> analyzing -> embedding -> ready
```

- 任一步骤可进入 `failed`，并保存错误码与安全化错误信息。
- 内容重复时 RawItem 标记 `duplicate`，复用已有 Document。
- 重试不得重复生成同版本 Analysis 或 DocumentChunk。
- 网络采集最多重试 3 次并指数退避；确定性校验错误不重试。
- AI 调用最多重试 2 次；结构化输出校验失败允许修复重试 1 次。
- 超出重试次数后记录失败，并支持所有者手动重试。

## 4. 评分与通知

- 四个子分均为 0–100 整数。
- `radar_score = relevance * 0.40 + importance * 0.25 + novelty * 0.20 + impact * 0.15`。
- `radar_score >= notification_threshold` 时幂等创建 Notification。
- Recommendation：85–100 `must_read`；70–84 `read`；50–69 `monitor`；0–49 `archive`。
- 所有评分必须附带简短 `reason`；Pipeline 和 Prompt 必须版本化。

## 5. REST API 范围

### System、Auth 与 User

- `GET /health/live`、`GET /health/ready`
- `POST /auth/register`、`POST /auth/login`、`POST /auth/refresh`、`POST /auth/logout`
- `GET /users/me`、`PATCH /users/me`

### Radars 与 Sources

- Radar：`POST /radars`、`GET /radars`、`GET|PATCH|DELETE /radars/{radar_id}`、`POST /radars/{radar_id}/pause|resume`
- Source：`POST /sources`、`GET /sources`、`GET|PATCH|DELETE /sources/{source_id}`
- 绑定：`POST|DELETE /radars/{radar_id}/sources/{source_id}`
- 采集：`POST /sources/{source_id}/collect`、`GET /sources/{source_id}/runs`、`GET /collection-runs/{run_id}`

### Intelligence、Memory 与 Notifications

- `GET /intelligence`、`GET /intelligence/{analysis_id}`
- `POST /bookmarks`、`GET /bookmarks`、`PATCH|DELETE /bookmarks/{bookmark_id}`
- `POST /memory/search`
- `GET /notifications`、`POST /notifications/{notification_id}/read`、`POST /notifications/read-all`
- 恢复：`POST /collection-runs/{run_id}/retry`、`POST /analyses/{analysis_id}/retry`

## 6. WebSocket

- Endpoint：`/api/v1/ws`，使用有效 Access Token 鉴权。
- Alpha 事件：`collection.updated`、`analysis.completed`、`notification.created`。
- Envelope：`{event_id, event_type, occurred_at, data}`。
- 客户端按 `event_id` 去重；重连后通过 REST 获取最新事实数据。

## 7. 安全底线

- 密码使用 Argon2id；日志禁止输出密码、Token、API Key 或完整正文。
- 自定义 URL 只允许 HTTP/HTTPS，禁止本机、私网、链路本地和云元数据地址。
- 每次重定向重新进行 SSRF 校验，并限制重定向、响应大小、Content-Type 和超时。
- HTML 清洗后不得保留可执行脚本。
- 用户只能访问自己拥有或其 Radar 关联的数据。
- OpenAPI 必须声明认证与错误响应。

## 8. BE-1 工程契约补充

- Python、依赖锁定、Compose、配置、日志和测试规格以 `docs/04-BE1-ENGINEERING-BASELINE.md` 为准。
- 健康检查完整路径为 `/api/v1/health/live` 与 `/api/v1/health/ready`。
- Liveness 不检查外部依赖；Readiness 检查 PostgreSQL 和 Redis。
- Readiness 异常返回 HTTP 503 和 `service_not_ready` 统一错误，不泄露连接信息。
- 每个 API 请求接受或生成 UUID `X-Request-ID`，响应回传该 Header。
